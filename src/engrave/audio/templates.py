"""Natural language template rendering for audio descriptions.

Converts structured ``AudioDescription`` / ``SectionDescription`` objects
into readable sentences suitable for injection into the generation prompt's
CONTEXTUAL block.  The generation LLM receives human-readable prose, not
raw JSON.
"""

from __future__ import annotations

from engrave.audio.description import AudioDescription, SectionDescription


def render_track_summary(desc: AudioDescription) -> str:
    """Render track-level metadata as a compact natural language header.

    Example output::

        Swing big band in Bb major, 142 BPM, 4/4 time.
        Instruments: trumpet, trombone, alto sax, piano, bass, drums.
        Energy: mp -> mf -> f -> ff -> mf.
    """
    parts: list[str] = []

    # Style + key + tempo + time signature
    style_prefix = " ".join(desc.style_tags).capitalize() if desc.style_tags else ""
    key_str = f"in {desc.key}" if desc.key else ""
    tempo_str = f"{desc.tempo_bpm} BPM"
    if desc.tempo_variable:
        tempo_str += " (variable)"
    time_str = f"{desc.time_signature} time"

    # Build opening sentence
    opening_parts = [p for p in [style_prefix, key_str] if p]
    if opening_parts:
        opening = ", ".join(opening_parts)
        parts.append(f"{opening}, {tempo_str}, {time_str}.")
    else:
        parts.append(f"{tempo_str}, {time_str}.")

    # Instruments
    if desc.instruments:
        parts.append(f"Instruments: {', '.join(desc.instruments)}.")

    # Energy arc
    if desc.energy_arc:
        parts.append(f"Energy: {desc.energy_arc}.")

    return " ".join(parts)


def render_section_description(section: SectionDescription) -> str:
    """Render a single section annotation as a natural language sentence.

    Only includes fields that have non-empty / non-None values.

    Example output::

        Section: verse-1 (bars 9-24). Key: Bb major.
        Active instruments: trumpet, piano, bass, drums.
        Texture: walking bass under trumpet melody. Dynamics: mf.
    """
    parts: list[str] = []

    # Label and bar range
    label_str = section.label if section.label else "unnamed"
    parts.append(f"Section: {label_str} (bars {section.start_bar}-{section.end_bar}).")

    # Optional fields
    if section.key:
        parts.append(f"Key: {section.key}.")

    if section.active_instruments:
        parts.append(f"Active instruments: {', '.join(section.active_instruments)}.")

    if section.texture:
        parts.append(f"Texture: {section.texture}.")

    if section.dynamics:
        parts.append(f"Dynamics: {section.dynamics}.")

    if section.notes is not None and section.notes:
        parts.append(f"Notes: {section.notes}.")

    return " ".join(parts)


def render_full_description(desc: AudioDescription) -> str:
    """Combine track summary and all section descriptions.

    Returns a multi-line string suitable for the CONTEXTUAL block of the
    three-tier generation prompt.
    """
    lines: list[str] = [render_track_summary(desc)]

    for section in desc.sections:
        lines.append(render_section_description(section))

    return "\n".join(lines)
