"""Pydantic models for structured audio descriptions.

Two-tier schema: track-level metadata + per-section annotations.
Populated by audio LMs (Gemini 3 Flash, Qwen3-Omni) via the Describer protocol.

No confidence scores -- disagreement between systems is the signal.
Section boundaries come from MIDI analysis (``midi/sections.py``), NOT
from audio LM timestamps.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SectionDescription(BaseModel):
    """Audio LM annotations for a single section.

    Fields capture musical *character* (texture, dynamics, style) rather
    than note-level accuracy.  The ``notes`` field is a nullable catch-all
    for observations that don't fit other fields (e.g. "sounds like a Basie
    arrangement", "drummer on brushes").
    """

    label: str = ""
    """Section label, e.g. ``"intro"``, ``"verse-1"``, ``"chorus-1"``."""

    start_bar: int = 1
    """First bar of the section (1-based)."""

    end_bar: int = 1
    """Last bar of the section (inclusive, 1-based)."""

    key: str | None = None
    """Key of this section if it differs from track level, e.g. ``"Bb major"``."""

    active_instruments: list[str] = Field(default_factory=list)
    """Instruments playing in this section."""

    texture: str = ""
    """Musical texture descriptor, e.g. ``"solo piano"``, ``"full ensemble block chords"``."""

    dynamics: str = ""
    """Dynamics level or arc, e.g. ``"mf"``, ``"building from mp to f"``."""

    notes: str | None = None
    """Nullable free-text catch-all for stray observations."""


class AudioDescription(BaseModel):
    """Two-tier structured description produced by an audio LM.

    Track-level metadata provides global context (tempo, key, style).
    Per-section annotations label pre-existing section boundaries with
    musical character information.
    """

    tempo_bpm: int = 120
    """Estimated tempo in beats per minute."""

    tempo_variable: bool = False
    """True if tempo changes are detected across the recording."""

    time_signature: str = "4/4"
    """Time signature as a string, e.g. ``"4/4"``, ``"3/4"``, ``"6/8"``."""

    key: str = "C major"
    """Overall key (root + mode), e.g. ``"Bb major"``, ``"G minor"``."""

    instruments: list[str] = Field(default_factory=list)
    """All instruments detected in the recording."""

    style_tags: list[str] = Field(default_factory=list)
    """Style/genre tags, e.g. ``["swing", "big band", "blues"]``."""

    energy_arc: str = ""
    """Overall dynamic arc, e.g. ``"mp -> mf -> f -> ff -> mf"``."""

    sections: list[SectionDescription] = Field(default_factory=list)
    """Per-section annotations from the audio LM."""
