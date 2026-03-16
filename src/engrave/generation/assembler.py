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
from engrave.rendering.stylesheet import CONDUCTOR_SCORE_LAYOUT, CONDUCTOR_SCORE_PAPER

# Regex matching a LilyPond command mangled with staccato dots, e.g.
# ``\time-.``, ``\ke-.y``, ``\se-.t``.  This pattern never appears in valid
# LilyPond: staccato attaches to notes (``c4-.``), not to commands.
# The negative lookahead excludes dynamic markings followed by staccato
# (``\f-.``, ``\ff-.`` etc.) which are valid after ENSM-03 processing.
_MANGLED_CMD_RE = re.compile(r"\\(?!(?:fff|ff|f|mf|mp|ppp|pp|p)-\.)[a-zA-Z]+-\.")

# Clean global-level commands that belong in the ``global`` block, not
# inside individual instrument variables.
_CLEAN_GLOBAL_RE = re.compile(r"^\s*\\(time|key|tempo|clef|set)\s")

# A line containing only ``{`` or ``}`` is a LLM artifact from echoing
# variable wrappers.  The assembler provides the outer braces for each
# variable, so bare braces inside the content are always artifacts.
_BARE_OPEN_BRACE_RE = re.compile(r"^\s*\{\s*$")
_BARE_CLOSE_BRACE_RE = re.compile(r"^\s*\}\s*$")

# Line containing only dynamics and/or articulations with no actual notes
# or rests — orphaned LLM artifact.  Matches lines like ``\f-.f-.``,
# ``-.\f``, ``-.``, etc.
_ORPHANED_ARTIC_RE = re.compile(r"^\s*(?:-\.|\\(?:fff|ff|f|mf|mp|ppp|pp|p)(?![a-zA-Z])|\s)+\s*$")

# Dynamic marking regex — ordered longest-first so alternation matches
# ``\fff`` before ``\ff`` before ``\f``.  Negative lookahead prevents
# matching command prefixes like ``\fermata`` or ``\partial``.
_DYN_RE = re.compile(r"\\(fff|ff|f|mf|mp|ppp|pp|p)(?![a-zA-Z])")


def _clef_for_instrument(instrument_name: str) -> str | None:
    """Return LilyPond clef name for *instrument_name*, or ``None`` for default treble."""
    name = instrument_name.lower().strip()
    if "drum" in name or "percussion" in name:
        return "percussion"
    if "trombone" in name:
        return "bass"
    if name == "bass" or "bass guitar" in name or "double bass" in name:
        return "bass"
    if "bari" in name:
        return "bass"
    if "cello" in name or "bassoon" in name or "tuba" in name:
        return "bass"
    return None


def _deduplicate_dynamics(content: str) -> str:
    """Remove consecutive identical dynamic markings from instrument content.

    MIDI transcription emits dynamics on nearly every note.  Notation
    convention only marks dynamics when the level *changes*.  This strips
    redundant consecutive dynamics while preserving the first occurrence
    and any actual level changes.
    """
    current_dynamic: str | None = None
    result: list[str] = []
    last_end = 0

    for match in _DYN_RE.finditer(content):
        dynamic = match.group(0)  # e.g. ``\\ff``
        if dynamic == current_dynamic:
            # Same as previous — strip it
            result.append(content[last_end : match.start()])
            last_end = match.end()
        else:
            # Different dynamic — keep it, update state
            current_dynamic = dynamic
            result.append(content[last_end : match.end()])
            last_end = match.end()

    result.append(content[last_end:])
    return "".join(result)


def _clean_articulation_clusters(content: str) -> str:
    """Fix garbled articulation/dynamic sequences from LLM output.

    The LLM sometimes produces invalid sequences like:

    - ``-.-.`` (duplicate staccato)
    - ``\\f-.f-.`` (dynamic + staccato + orphaned f + staccato)
    - ``-.\\f-.`` (staccato + dynamic + redundant staccato)
    - ``-.f-.`` (staccato + orphaned f-dynamic + staccato)

    Order of substitutions matters — complex patterns before simpler ones.
    """
    # \dynamic-.f-. → \dynamic  (e.g. \f-.f-. → \f)
    content = re.sub(r"(\\(?:fff|ff|f|mf|mp|ppp|pp|p))(?![a-zA-Z])-\.f-\.", r"\1", content)
    # -.\dynamic-. → -.\dynamic  (redundant staccato after dynamic)
    content = re.sub(r"(-\.)(\\(?:fff|ff|f|mf|mp|ppp|pp|p))(?![a-zA-Z])-\.", r"\1\2", content)
    # -.f-. → -.  (orphaned f-dynamic without backslash + staccato)
    content = re.sub(r"(-\.)f-\.", r"\1", content)
    # -.-. → -.  (duplicate consecutive staccato)
    content = re.sub(r"(-\.){2,}", "-.", content)
    return content


def _sanitize_music_content(content: str) -> str:
    """Strip LLM artifacts from instrument music content.

    Five categories of artifacts are removed:

    1. **Mangled commands** -- LLMs echo ``\\time``, ``\\key``, ``\\tempo``,
       ``\\set``, ``\\dynamicUp`` etc. with staccato dots injected
       (``\\time-. 4/4``, ``\\se-.t Sta-.f-.f-..mid-.i...``).
    2. **Misplaced global commands** -- clean ``\\time 4/4``, ``\\key g \\minor``
       etc. that belong in the global block, not in instrument variables.
    3. **Bare braces** -- a lone ``{`` or ``}`` line from the LLM echoing
       variable wrapper syntax.
    4. **Garbled articulation clusters** -- doubled staccato ``-.-.``,
       orphaned dynamics ``-.f-.``, etc.
    5. **Orphaned articulation lines** -- lines containing only dynamics
       and/or staccato with no actual notes or rests.
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
        if _BARE_CLOSE_BRACE_RE.match(line):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    # Fix garbled articulation/dynamic clusters
    result = _clean_articulation_clusters(result)
    # Strip orphaned articulation-only lines (no notes or rests)
    lines = result.split("\n")
    result = "\n".join(line for line in lines if not _ORPHANED_ARTIC_RE.match(line))
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
        # Strip redundant consecutive dynamics (MIDI velocity flooding)
        combined = _deduplicate_dynamics(combined)
        variable_declarations.append(f"{var_name} = {{\n  {combined}\n}}")

    variables_block = "\n\n".join(variable_declarations)

    # Build staff lines with clef assignments and \global reference
    staff_lines = []
    for var_name, inst_name in zip(var_names, instrument_names, strict=True):
        clef = _clef_for_instrument(inst_name)
        clef_cmd = f"\\clef {clef} " if clef else ""
        staff_lines.append(
            f'    \\new Staff \\with {{ instrumentName = "{inst_name}" }}'
            f" {{ {clef_cmd}\\global \\{var_name} }}"
        )
    staves_block = "\n".join(staff_lines)

    # Metadata comments
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    num_sections = len(section_sources)

    # Indent layout block inside \score
    layout_indented = "\n".join(
        f"  {line}" if line.strip() else "" for line in CONDUCTOR_SCORE_LAYOUT.splitlines()
    ).rstrip()

    assembled = (
        f'\\version "2.24.0"\n'
        f"\n"
        f"% Generated by Engrave - concert pitch\n"
        f"% Assembled from {num_sections} section(s)\n"
        f"% Generated: {timestamp}\n"
        f"\n"
        f"\\header {{\n"
        f'  tagline = "Generated by Engrave"\n'
        f"}}\n"
        f"\n"
        f"{CONDUCTOR_SCORE_PAPER}\n"
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
        f"{layout_indented}\n"
        f"}}\n"
    )

    return assembled
