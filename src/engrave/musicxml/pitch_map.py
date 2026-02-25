"""LilyPond-to-music21 pitch name conversion.

Converts LilyPond pitch names (bf4, fis5, ees3) to music21 pitch strings (B-4, F#5, E-3)
and LilyPond key strings (bf_major, fs_minor) to music21 key strings (B-, f#).
"""

from __future__ import annotations

import re

# Static lookup: LilyPond note name (without octave) -> music21 pitch name.
# Order matters for regex: longest accidental patterns must be listed first to prevent
# partial matches (e.g. 'ees' before 'es', 'aes' before 'as').
#
# LilyPond special cases:
#   - 'es' = E-flat (abbreviation of 'ees'), NOT E-sharp
#   - 'as' = A-flat (abbreviation of 'aes'), NOT A-sharp
_LY_NOTE_TO_M21: dict[str, str] = {
    # Naturals
    "c": "C",
    "d": "D",
    "e": "E",
    "f": "F",
    "g": "G",
    "a": "A",
    "b": "B",
    # Flats -- short form (f suffix, except 'es' and 'as' which are LilyPond special)
    "cf": "C-",
    "df": "D-",
    "ef": "E-",
    "gf": "G-",
    "af": "A-",
    "bf": "B-",
    # Flats -- long form (es suffix)
    "ces": "C-",
    "des": "D-",
    "ees": "E-",
    "fes": "F-",
    "ges": "G-",
    "aes": "A-",
    "bes": "B-",
    # LilyPond special abbreviations for E-flat and A-flat
    "es": "E-",
    "as": "A-",
    # Sharps -- short form (s suffix)
    "cs": "C#",
    "ds": "D#",
    "fs": "F#",
    "gs": "G#",
    # Sharps -- long form (is suffix)
    "cis": "C#",
    "dis": "D#",
    "eis": "E#",
    "fis": "F#",
    "gis": "G#",
    "ais": "A#",
    "bis": "B#",
}

# Build regex from the lookup keys, ordered longest-first to prevent partial matches.
_accidentals_pattern = "|".join(
    sorted(
        (k[1:] for k in _LY_NOTE_TO_M21 if len(k) > 1),
        key=len,
        reverse=True,
    )
)
_LY_PITCH_RE = re.compile(rf"^([a-g](?:{_accidentals_pattern})?)(\d)$")


def ly_pitch_to_m21(ly_pitch: str) -> str:
    """Convert LilyPond-style pitch (e.g. 'bf4') to music21 pitch string (e.g. 'B-4').

    Args:
        ly_pitch: LilyPond pitch name with octave digit, e.g. "bf4", "fis5", "c3".

    Returns:
        music21-compatible pitch string, e.g. "B-4", "F#5", "C3".

    Raises:
        ValueError: If the pitch name is not recognized.
    """
    match = _LY_PITCH_RE.match(ly_pitch)
    if not match:
        raise ValueError(f"Cannot parse LilyPond pitch: {ly_pitch!r}")

    note_name, octave = match.group(1), match.group(2)
    m21_name = _LY_NOTE_TO_M21.get(note_name)
    if m21_name is None:
        raise ValueError(f"Unknown LilyPond note name: {note_name!r}")

    return f"{m21_name}{octave}"


def ly_key_to_m21(ly_key: str) -> str:
    """Convert LilyPond key string (e.g. 'bf_major') to music21 Key string (e.g. 'B-').

    Major keys return uppercase (e.g. 'B-', 'G', 'D').
    Minor keys return lowercase (e.g. 'f#', 'c', 'a').

    Args:
        ly_key: Key string in format '{note}_{mode}', e.g. 'bf_major', 'fs_minor'.

    Returns:
        music21-compatible key string.

    Raises:
        ValueError: If the key string cannot be parsed.
    """
    parts = ly_key.split("_", maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse LilyPond key: {ly_key!r} (expected 'note_mode' format)")

    note_name, mode = parts
    m21_name = _LY_NOTE_TO_M21.get(note_name)
    if m21_name is None:
        raise ValueError(f"Unknown note name in key: {note_name!r}")

    if mode == "major":
        return m21_name  # Already uppercase from lookup
    elif mode == "minor":
        return m21_name.lower()  # Lowercase for minor
    else:
        raise ValueError(f"Unknown key mode: {mode!r} (expected 'major' or 'minor')")
