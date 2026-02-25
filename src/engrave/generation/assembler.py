"""Section assembly into a single complete LilyPond file.

Merges per-section LilyPond output into one self-contained .ly file
with continuous instrument variables, a single \\version header, global
settings, and one \\score block.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from engrave.generation.templates import sanitize_var_name
from engrave.midi.analyzer import MidiAnalysis

# Regex matching a LilyPond command mangled with staccato dots, e.g.
# ``\time-.``, ``\ke-.y``, ``\se-.t``.  This pattern never appears in valid
# LilyPond: staccato attaches to notes (``c4-.``), not to commands.
_MANGLED_CMD_RE = re.compile(r"\\[a-zA-Z]+-\.")

# Clean global-level commands that belong in the ``global`` block, not
# inside individual instrument variables.
_CLEAN_GLOBAL_RE = re.compile(r"^\s*\\(time|key|tempo|clef|set)\s")

# A line containing only ``{`` is a LLM artifact from echoing variable
# wrappers.  Stripping only ``{`` (not ``}``) is safe because the
# assembler provides the outer braces for each variable.
_BARE_OPEN_BRACE_RE = re.compile(r"^\s*\{\s*$")


def _sanitize_music_content(content: str) -> str:
    """Strip LLM artifacts from instrument music content.

    Three categories of artifacts are removed:

    1. **Mangled commands** -- LLMs echo ``\\time``, ``\\key``, ``\\tempo``,
       ``\\set``, ``\\dynamicUp`` etc. with staccato dots injected
       (``\\time-. 4/4``, ``\\se-.t Sta-.f-.f-..mid-.i...``).
    2. **Misplaced global commands** -- clean ``\\time 4/4``, ``\\key g \\minor``
       etc. that belong in the global block, not in instrument variables.
    3. **Bare opening braces** -- a lone ``{`` line from the LLM echoing
       variable wrapper syntax.
    """
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        if _MANGLED_CMD_RE.search(line):
            continue
        if _CLEAN_GLOBAL_RE.match(line):
            continue
        if _BARE_OPEN_BRACE_RE.match(line):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return result if result else "R1"


def _extract_variable_content(section_source: str, var_name: str) -> str:
    """Extract the music content for a given variable from section source.

    Looks for ``varName = { ... }`` blocks and returns the inner content.

    Args:
        section_source: LilyPond source for one section.
        var_name: Variable name to extract.

    Returns:
        Music content string (may be empty if variable not found).
    """
    # Match varName = { ... } allowing nested braces
    pattern = re.compile(
        rf"^{re.escape(var_name)}\s*=\s*\{{(.*?)\n\}}",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(section_source)
    if match:
        return match.group(1).strip()
    return ""


def assemble_sections(
    section_sources: list[str],
    instrument_names: list[str],
    analysis: MidiAnalysis,
) -> str:
    """Assemble section outputs into a complete, self-contained .ly file.

    1. Generate a single \\version header and global settings block
    2. For each instrument, concatenate music content from all sections
    3. Build a single \\score block with one \\new Staff per instrument
    4. Include tempo, key, and time signature in the global context

    Args:
        section_sources: List of compiled LilyPond source strings, one per section.
        instrument_names: List of instrument names.
        analysis: MidiAnalysis with key, tempo, time signature info.

    Returns:
        Complete, self-contained .ly file string.
    """
    var_names = [sanitize_var_name(name) for name in instrument_names]

    # Extract key, time sig, tempo from analysis
    key_sig = analysis.key_signature

    if analysis.time_signatures:
        ts_num, ts_denom, _ = analysis.time_signatures[0]
        time_sig_str = f"{ts_num}/{ts_denom}"
    else:
        time_sig_str = "4/4"

    tempo_bpm = int(analysis.tempo_changes[0][0]) if analysis.tempo_changes else 120

    # Concatenate music content per instrument across all sections
    instrument_music: dict[str, list[str]] = {vn: [] for vn in var_names}

    for section_source in section_sources:
        for var_name in var_names:
            content = _extract_variable_content(section_source, var_name)
            if content:
                content = _sanitize_music_content(content)
                instrument_music[var_name].append(content)

    # Build variable declarations with concatenated music
    variable_declarations: list[str] = []
    for var_name in var_names:
        parts = instrument_music[var_name]
        # Join with newline; handle tie continuity (if section ends with ~)
        combined = "\n  ".join(parts) if parts else "R1"
        variable_declarations.append(f"{var_name} = {{\n  {combined}\n}}")

    variables_block = "\n\n".join(variable_declarations)

    # Build staff lines
    staff_lines = []
    for var_name, inst_name in zip(var_names, instrument_names, strict=True):
        staff_lines.append(
            f'    \\new Staff \\with {{ instrumentName = "{inst_name}" }} \\{var_name}'
        )
    staves_block = "\n".join(staff_lines)

    # Metadata comments
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    num_sections = len(section_sources)

    assembled = (
        f'\\version "2.24.4"\n'
        f"\n"
        f"% Generated by Engrave - concert pitch\n"
        f"% Assembled from {num_sections} section(s)\n"
        f"% Generated: {timestamp}\n"
        f"\n"
        f"\\header {{\n"
        f'  tagline = "Generated by Engrave"\n'
        f"}}\n"
        f"\n"
        f"global = {{\n"
        f"  \\key {key_sig}\n"
        f"  \\time {time_sig_str}\n"
        f"  \\tempo 4 = {tempo_bpm}\n"
        f"}}\n"
        f"\n"
        f"{variables_block}\n"
        f"\n"
        f"\\score {{\n"
        f"  <<\n"
        f"{staves_block}\n"
        f"  >>\n"
        f"  \\layout {{ }}\n"
        f"}}\n"
    )

    return assembled
