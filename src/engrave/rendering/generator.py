"""LilyPond file generators for conductor scores, individual parts, and shared definitions.

Public API
----------
- ``generate_music_definitions`` -- shared ``music-definitions.ly`` content
- ``generate_conductor_score`` -- full conductor score ``.ly`` file
- ``generate_part`` -- individual transposed part ``.ly`` file
- ``restate_dynamics`` -- post-processing pass that restates dynamics after rests
"""

from __future__ import annotations

from itertools import groupby

from engrave.rendering.ensemble import BigBandPreset, InstrumentSpec, StaffGroupType
from engrave.rendering.stylesheet import (
    CONDUCTOR_SCORE_LAYOUT,
    CONDUCTOR_SCORE_PAPER,
    PART_LAYOUT,
    PART_PAPER,
    STUDIO_LAYOUT,
    VERSION_HEADER,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert an instrument name to a filename slug.

    Lowercase, spaces to hyphens. ASCII instrument names only.
    E.g. "Alto Sax 1" -> "alto-sax-1"
    """
    return name.lower().replace(" ", "-")


def _staff_block(instrument: InstrumentSpec, *, indent: str = "    ") -> str:
    """Build a single Staff block for the conductor score.

    Returns the LilyPond source for one staff entry within a StaffGroup.
    Concert pitch -- no transposition applied in the conductor score.
    """
    if instrument.clef == "percussion":
        return (
            f"{indent}\\new DrumStaff \\with {{\n"
            f'{indent}  instrumentName = "{instrument.name}"\n'
            f'{indent}  shortInstrumentName = "{instrument.short_name}"\n'
            f"{indent}}} {{\n"
            f"{indent}  << \\globalMusic \\{instrument.variable_name} >>\n"
            f"{indent}}}\n"
        )

    if instrument.is_grand_staff:
        return (
            f"{indent}\\new PianoStaff \\with {{\n"
            f'{indent}  instrumentName = "{instrument.name}"\n'
            f'{indent}  shortInstrumentName = "{instrument.short_name}"\n'
            f"{indent}}} <<\n"
            f'{indent}  \\new Staff = "{instrument.variable_name}-upper" {{\n'
            f"{indent}    \\clef treble\n"
            f"{indent}    << \\globalMusic \\{instrument.variable_name} >>\n"
            f"{indent}  }}\n"
            f'{indent}  \\new Staff = "{instrument.variable_name}-lower" {{\n'
            f"{indent}    \\clef bass\n"
            f"{indent}    << \\globalMusic \\{instrument.variable_name}Left >>\n"
            f"{indent}  }}\n"
            f"{indent}>>\n"
        )

    clef_cmd = f"\\clef {instrument.clef}" if instrument.clef != "treble" else ""
    clef_line = f"\n{indent}    {clef_cmd}" if clef_cmd else ""
    return (
        f'{indent}\\new Staff = "{instrument.variable_name}" \\with {{\n'
        f'{indent}  instrumentName = "{instrument.name}"\n'
        f'{indent}  shortInstrumentName = "{instrument.short_name}"\n'
        f"{indent}}} {{{clef_line}\n"
        f"{indent}  << \\globalMusic \\{instrument.variable_name} >>\n"
        f"{indent}}}\n"
    )


# ---------------------------------------------------------------------------
# generate_music_definitions
# ---------------------------------------------------------------------------


def generate_music_definitions(
    music_vars: dict[str, str],
    global_music: str,
    chord_symbols: str | None = None,
) -> str:
    """Produce the ``music-definitions.ly`` content.

    Parameters
    ----------
    music_vars:
        Mapping of LilyPond variable names to concert-pitch music content.
    global_music:
        The ``globalMusic`` content (time sig, key, rehearsal marks, etc.).
    chord_symbols:
        Optional ``chordSymbols`` content in ``\\chordmode``.

    Returns
    -------
    str
        A complete LilyPond source string for the shared definitions file.
    """
    lines: list[str] = [VERSION_HEADER, ""]

    # globalMusic
    lines.append(f"globalMusic = {{\n  {global_music}\n}}\n")

    # Chord symbols (optional)
    if chord_symbols is not None:
        lines.append(f"chordSymbols = {chord_symbols}\n")

    # Instrument music variables
    for var_name, content in music_vars.items():
        lines.append(f"{var_name} = {{\n  {content}\n}}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generate_conductor_score
# ---------------------------------------------------------------------------


def generate_conductor_score(
    preset: BigBandPreset,
    music_var_names: list[str],
    has_chords: bool = True,
    title: str = "",
    composer: str = "",
    arranger: str = "",
) -> str:
    """Produce the ``score.ly`` content for a conductor score.

    Parameters
    ----------
    preset:
        The ensemble preset providing instrument specs and grouping.
    music_var_names:
        Variable names for all instruments (used for reference validation).
    has_chords:
        Whether to include a ``ChordNames`` context above the top staff.
    title, composer, arranger:
        Metadata for the header block.

    Returns
    -------
    str
        Complete LilyPond source for the conductor score.
    """
    lines: list[str] = [VERSION_HEADER, ""]

    # Include shared definitions
    lines.append('\\include "music-definitions.ly"\n')

    # Header
    lines.append("\\header {")
    if title:
        lines.append(f'  title = "{title}"')
    if composer:
        lines.append(f'  composer = "{composer}"')
    if arranger:
        lines.append(f'  arranger = "{arranger}"')
    lines.append("  tagline = ##f")
    lines.append("}\n")

    # Paper
    lines.append(CONDUCTOR_SCORE_PAPER)

    # Book and bookOutputName
    lines.append('\\bookOutputName "score"\n')

    # Score block
    lines.append("\\score {")
    lines.append("  <<")

    # Chord names above top staff
    if has_chords:
        lines.append("    \\new ChordNames { \\chordSymbols }")

    # Group instruments by section
    instruments = list(preset.instruments)
    for section, group in groupby(instruments, key=lambda i: i.section):
        group_list = list(group)
        first = group_list[0]

        # Determine systemStartDelimiter
        if first.group_type == StaffGroupType.BRACE:
            delimiter = "SystemStartBrace"
        else:
            delimiter = "SystemStartBracket"

        lines.append(f'    \\new StaffGroup = "{section}" \\with {{')
        lines.append(f"      systemStartDelimiter = #{delimiter}")
        lines.append("    } <<")

        for inst in group_list:
            staff_block = _staff_block(inst, indent="      ")
            lines.append(staff_block)

        lines.append("    >>")

    lines.append("  >>")

    # Layout
    lines.append(CONDUCTOR_SCORE_LAYOUT)

    # MIDI
    lines.append("  \\midi { }")

    lines.append("}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generate_part
# ---------------------------------------------------------------------------


def generate_part(
    instrument: InstrumentSpec,
    preset_name: str = "Big Band",
    has_chords: bool = False,
    chord_var: str = "chordSymbols",
    studio_mode: bool = False,
    title: str = "",
) -> str:
    """Produce a ``part-{slug}.ly`` file for one instrument.

    Parameters
    ----------
    instrument:
        The instrument spec to generate a part for.
    preset_name:
        Name of the ensemble preset (for display).
    has_chords:
        Whether to include chord symbols above the staff.
    chord_var:
        The LilyPond variable name for chord symbols.
    studio_mode:
        If ``True``, use studio layout (bar numbers on every bar).
    title:
        Song title for the header.

    Returns
    -------
    str
        Complete LilyPond source for the individual part.
    """
    slug = _slugify(instrument.name)
    lines: list[str] = [VERSION_HEADER, ""]

    # Include shared definitions
    lines.append('\\include "music-definitions.ly"\n')

    # Header
    lines.append("\\header {")
    if title:
        lines.append(f'  title = "{title}"')
    lines.append(f'  instrument = "{instrument.name}"')
    lines.append("  tagline = ##f")
    lines.append("}\n")

    # Paper
    lines.append(PART_PAPER)

    # Book output name
    lines.append(f'\\bookOutputName "part-{slug}"\n')

    # Build the music expression
    music_ref = f"\\{instrument.variable_name}"

    # Apply transposition if instrument is transposing
    if instrument.is_transposing:
        music_expr = (
            f"\\transpose {instrument.transpose_from} {instrument.transpose_to} {music_ref}"
        )
    else:
        music_expr = music_ref

    # Score block
    lines.append("\\score {")

    if instrument.clef == "percussion":
        # Drums: DrumStaff
        lines.append("  <<")
        if has_chords:
            lines.append(f"    \\new ChordNames {{ \\{chord_var} }}")
        lines.append("    \\new DrumStaff \\with {")
        lines.append(f'      instrumentName = "{instrument.name}"')
        lines.append(f'      shortInstrumentName = "{instrument.short_name}"')
        lines.append("    } {")
        lines.append(f"      \\compressMMRests {{ << \\globalMusic {music_expr} >> }}")
        lines.append("    }")
        lines.append("  >>")
    elif instrument.is_grand_staff:
        # Piano: PianoStaff with chord names
        lines.append("  <<")
        if has_chords:
            lines.append(f"    \\new ChordNames {{ \\{chord_var} }}")
        lines.append("    \\new PianoStaff \\with {")
        lines.append(f'      instrumentName = "{instrument.name}"')
        lines.append(f'      shortInstrumentName = "{instrument.short_name}"')
        lines.append("    } <<")
        lines.append(f'      \\new Staff = "{instrument.variable_name}-upper" {{')
        lines.append("        \\clef treble")
        lines.append(f"        \\compressMMRests {{ << \\globalMusic {music_expr} >> }}")
        lines.append("      }")
        lines.append(f'      \\new Staff = "{instrument.variable_name}-lower" {{')
        lines.append("        \\clef bass")
        lines.append(
            f"        \\compressMMRests {{ << \\globalMusic \\{instrument.variable_name}Left >> }}"
        )
        lines.append("      }")
        lines.append("    >>")
        lines.append("  >>")
    else:
        # Normal staff
        clef_cmd = f"\\clef {instrument.clef}" if instrument.clef != "treble" else ""
        lines.append("  <<")
        if has_chords:
            lines.append(f"    \\new ChordNames {{ \\{chord_var} }}")
        lines.append("    \\new Staff \\with {")
        lines.append(f'      instrumentName = "{instrument.name}"')
        lines.append(f'      shortInstrumentName = "{instrument.short_name}"')
        lines.append("    } {")
        if clef_cmd:
            lines.append(f"      {clef_cmd}")
        lines.append(f"      \\compressMMRests {{ << \\globalMusic {music_expr} >> }}")
        lines.append("    }")
        lines.append("  >>")

    # Layout
    if studio_mode:
        lines.append(STUDIO_LAYOUT)
    else:
        lines.append(PART_LAYOUT)

    lines.append("}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# restate_dynamics (placeholder -- implemented in Task 2)
# ---------------------------------------------------------------------------


def restate_dynamics(lilypond_source: str) -> str:
    """Insert dynamic restatement at entrances following 2+ bars of rest.

    Parameters
    ----------
    lilypond_source:
        A single instrument's LilyPond music content.

    Returns
    -------
    str
        Modified LilyPond source with dynamics restated after multi-bar rests.
    """
    # Full implementation in Task 2
    return lilypond_source
