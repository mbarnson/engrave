"""Metadata extraction from LilyPond source fragments.

Programmatically extracts musical metadata (key signature, time signature, tempo,
instrument, clef, note density, dynamics, articulations, chord symbols) from
LilyPond source text. No LLM-generated analysis -- all extraction is deterministic.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Note name formatting
# ---------------------------------------------------------------------------

# LilyPond note name to display name mapping
_NOTE_NAMES: dict[str, str] = {
    "c": "C",
    "d": "D",
    "e": "E",
    "f": "F",
    "g": "G",
    "a": "A",
    "b": "B",
    "cis": "C#",
    "dis": "D#",
    "eis": "E#",
    "fis": "F#",
    "gis": "G#",
    "ais": "A#",
    "bis": "B#",
    "ces": "Cb",
    "des": "Db",
    "ees": "Eb",
    "fes": "Fb",
    "ges": "Gb",
    "aes": "Ab",
    "bes": "Bb",
}

# Dynamic ordering from softest to loudest
_DYNAMIC_ORDER: list[str] = ["ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"]
_DYNAMIC_RANK: dict[str, int] = {d: i for i, d in enumerate(_DYNAMIC_ORDER)}

# Articulation patterns (shorthand and named)
_ARTICULATION_SHORTHAND = re.compile(r"(?<!\\)-([>.\-^!])")
_ARTICULATION_NAMED = re.compile(r"\\(accent|staccato|tenuto|marcato)(?!\w)")


def _format_note_name(ly_note: str) -> str:
    """Convert a LilyPond note name to display format.

    Examples:
        "c" -> "C", "fis" -> "F#", "bes" -> "Bb"
    """
    return _NOTE_NAMES.get(ly_note.lower(), ly_note.upper())


def _format_key(note: str, mode: str) -> str:
    """Format a key signature for display.

    Args:
        note: LilyPond note name (e.g., "c", "fis", "bes").
        mode: Key mode ("major" or "minor").

    Returns:
        Formatted key string (e.g., "C major", "F# minor", "Bb major").
    """
    display_note = _format_note_name(note)
    return f"{display_note} {mode}"


# ---------------------------------------------------------------------------
# Individual field extractors
# ---------------------------------------------------------------------------


def _extract_key_signature(ly_fragment: str) -> str | None:
    r"""Extract key signature from \key <note> \<mode>."""
    match = re.search(r"\\key\s+(\w+)\s*\\(major|minor)", ly_fragment)
    if match:
        return _format_key(match.group(1), match.group(2))
    return None


def _extract_time_signature(ly_fragment: str) -> str | None:
    r"""Extract time signature from \time <num>/<denom>."""
    match = re.search(r"\\time\s+(\d+/\d+)", ly_fragment)
    if match:
        return match.group(1)
    return None


def _extract_tempo(ly_fragment: str) -> str | None:
    r"""Extract tempo marking from \tempo command.

    Handles:
    - \tempo "Allegro" 4 = 120
    - \tempo "Andante"
    - \tempo 4 = 96
    """
    # Try string + metronome: \tempo "Name" 4 = 120
    match = re.search(r'\\tempo\s+"([^"]+)"', ly_fragment)
    if match:
        return match.group(1)

    # Try metronome only: \tempo 4 = 96
    match = re.search(r"\\tempo\s+(\d+)\s*=\s*(\d+)", ly_fragment)
    if match:
        return f"q={match.group(2)}"

    return None


def _extract_instrument(ly_fragment: str, header_metadata: dict | None = None) -> str | None:
    r"""Extract instrument name.

    Checks (in order):
    1. header_metadata["mutopiainstrument"]
    2. \set Staff.instrumentName = "..."
    3. instrumentName = "..."
    """
    if header_metadata:
        inst = header_metadata.get("mutopiainstrument")
        if inst:
            return inst

    # \set Staff.instrumentName = "..."
    match = re.search(r'\\set\s+Staff\.instrumentName\s*=\s*"([^"]*)"', ly_fragment)
    if match:
        return match.group(1)

    # instrumentName = "..."
    match = re.search(r'instrumentName\s*=\s*"([^"]*)"', ly_fragment)
    if match:
        return match.group(1)

    return None


def _extract_clef(ly_fragment: str) -> str | None:
    r"""Extract clef from \clef <name>."""
    match = re.search(r"\\clef\s+(\w+)", ly_fragment)
    if match:
        return match.group(1)
    return None


def _count_notes(ly_fragment: str) -> int:
    """Count note tokens in a LilyPond fragment.

    Notes are identified as: letter (a-g) optionally followed by accidentals
    (is/es/isis/eses) and optional octave marks (',) and optional duration.
    Excludes notes inside strings and comments.
    """
    # Pattern matches LilyPond note tokens: a-g with optional accidentals
    # followed by optional octave marks and duration
    note_pattern = re.compile(
        r"(?<![a-zA-Z])"  # not preceded by a letter
        r"[a-g]"  # base note
        r"(?:(?:is)+|(?:es)+)?"  # optional accidentals
        r"[',]*"  # optional octave
        r"\d*"  # optional duration
        r"\.?"  # optional dot
    )

    # Remove comments and strings first
    cleaned = re.sub(r"%\{.*?\}%", "", ly_fragment, flags=re.DOTALL)
    cleaned = re.sub(r"%[^\n]*", "", cleaned)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)

    # Remove LilyPond commands (backslash words) to avoid matching note letters
    # within command names like \mark, \major, etc.
    cleaned = re.sub(r"\\[a-zA-Z]+", " ", cleaned)

    return len(note_pattern.findall(cleaned))


def _calculate_note_density(ly_fragment: str, bar_count: int) -> float | None:
    """Calculate note density as notes per bar.

    Args:
        ly_fragment: LilyPond source fragment.
        bar_count: Number of bars in the fragment.

    Returns:
        Notes per bar, or None if bar_count is 0.
    """
    if bar_count <= 0:
        return None
    note_count = _count_notes(ly_fragment)
    return round(note_count / bar_count, 1)


def _extract_dynamic_range(ly_fragment: str) -> str | None:
    r"""Extract dynamic range from dynamic markings.

    Finds all dynamics (ppp, pp, p, mp, mf, f, ff, fff) via \<dynamic>
    and shorthand notation, returns "min-max" format (e.g., "p-f").
    If only one dynamic found, returns just that (e.g., "mf").
    """
    # Match \pp, \ff, etc. (backslash + dynamic letters)
    dynamic_pattern = re.compile(r"\\(ppp|pp|p|mp|mf|f|ff|fff)(?!\w)")
    matches = dynamic_pattern.findall(ly_fragment)

    if not matches:
        return None

    # Find min and max by rank
    ranked = [(d, _DYNAMIC_RANK.get(d, -1)) for d in matches if d in _DYNAMIC_RANK]
    if not ranked:
        return None

    min_dyn = min(ranked, key=lambda x: x[1])[0]
    max_dyn = max(ranked, key=lambda x: x[1])[0]

    if min_dyn == max_dyn:
        return min_dyn
    return f"{min_dyn}-{max_dyn}"


def _count_articulations(ly_fragment: str) -> int:
    """Count articulation marks in a LilyPond fragment.

    Counts both shorthand (->  -.  --  -^  -!) and named
    (\\accent, \\staccato, \\tenuto, \\marcato) articulations.
    """
    shorthand_count = len(_ARTICULATION_SHORTHAND.findall(ly_fragment))
    named_count = len(_ARTICULATION_NAMED.findall(ly_fragment))
    return shorthand_count + named_count


def _detect_chord_symbols(ly_fragment: str) -> bool:
    r"""Detect presence of chord symbols (\chordmode or \chords)."""
    return bool(re.search(r"\\chord(?:mode|s)(?!\w)", ly_fragment))


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def extract_metadata(
    ly_fragment: str,
    bar_start: int,
    bar_end: int,
    header_metadata: dict | None = None,
) -> dict:
    """Extract all metadata fields from a LilyPond fragment.

    Programmatically extracts musical properties from the source text.
    No LLM involvement -- all extraction is deterministic regex-based.

    Args:
        ly_fragment: LilyPond source fragment.
        bar_start: Starting bar number of this fragment.
        bar_end: Ending bar number of this fragment.
        header_metadata: Optional pre-extracted header metadata dict
            (e.g., from Mutopia headers).

    Returns:
        Dict with keys: key_signature, time_signature, tempo, instrument,
        clef, note_density, dynamic_range, articulation_count,
        has_chord_symbols, bar_start, bar_end.
    """
    bar_count = bar_end - bar_start + 1

    return {
        "key_signature": _extract_key_signature(ly_fragment),
        "time_signature": _extract_time_signature(ly_fragment),
        "tempo": _extract_tempo(ly_fragment),
        "instrument": _extract_instrument(ly_fragment, header_metadata),
        "clef": _extract_clef(ly_fragment),
        "note_density": _calculate_note_density(ly_fragment, bar_count),
        "dynamic_range": _extract_dynamic_range(ly_fragment),
        "articulation_count": _count_articulations(ly_fragment),
        "has_chord_symbols": _detect_chord_symbols(ly_fragment),
        "bar_start": bar_start,
        "bar_end": bar_end,
    }
