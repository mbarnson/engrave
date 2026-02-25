"""Pydantic models for JSON notation events.

Validates LLM-generated structured JSON notation events before
conversion to music21 objects for MusicXML export.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator, model_validator

# LilyPond pitch regex: note letter + optional accidental + octave digit.
# Accidental patterns ordered longest-first to prevent partial matches.
_LY_PITCH_RE = re.compile(
    r"^[a-g](?:ees|aes|bes|ces|des|fes|ges|ais|bis|cis|dis|eis|fis|gis|es|as|is|ef|af|bf|cf|df|gf|cs|ds|fs|gs|f|s)?\d$"
)


class NoteEvent(BaseModel):
    """A single note or rest event within a measure.

    Attributes:
        pitch: LilyPond-style pitch name with octave (e.g. "bf4"). None for rests.
        type: "rest" for rests, None for pitched notes.
        beat: Beat position within the measure (1-based).
        duration: Duration in quarter-note lengths (quarterLength).
        articulations: Optional list of articulation names (e.g. ["accent", "staccato"]).
        expressions: Optional list of expression names (e.g. ["fermata"]).
        dynamic: Optional dynamic marking (e.g. "f", "pp", "mf").
    """

    pitch: str | None = None
    type: str | None = None
    beat: float
    duration: float
    articulations: list[str] | None = None
    expressions: list[str] | None = None
    dynamic: str | None = None

    @field_validator("pitch")
    @classmethod
    def validate_pitch(cls, v: str | None) -> str | None:
        if v is not None and not _LY_PITCH_RE.match(v):
            raise ValueError(f"Invalid LilyPond pitch: {v!r}")
        return v

    @model_validator(mode="after")
    def validate_rest_pitch_exclusion(self) -> NoteEvent:
        """Rests must not have a pitch; pitched notes must not be typed as rest."""
        if self.type == "rest" and self.pitch is not None:
            raise ValueError("Rest notes must not have a pitch")
        return self


class MeasureData(BaseModel):
    """One measure of notation for a single instrument.

    Attributes:
        number: Measure number (1-based).
        notes: List of note/rest events in this measure.
    """

    number: int
    notes: list[NoteEvent]


class SectionNotation(BaseModel):
    """One instrument's notation for one section of the score.

    Attributes:
        instrument: Instrument identifier (e.g. "trumpet_1", "alto_sax").
        key: Optional LilyPond-style key (e.g. "bf_major", "fs_minor").
        time_signature: Optional time signature string (e.g. "4/4", "6/8").
        measures: List of measures in this section.
    """

    instrument: str
    key: str | None = None
    time_signature: str | None = None
    measures: list[MeasureData]
