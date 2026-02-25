"""MIDI loading and type 0/1 normalization -- stub for TDD RED phase."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NoteEvent:
    """Single note extracted from MIDI."""

    pitch: int
    start_tick: int
    duration_ticks: int
    velocity: int
    channel: int


@dataclass
class MidiTrackInfo:
    """Normalized track with instrument metadata."""

    track_index: int
    channel: int | None
    program: int | None
    instrument_name: str | None
    notes: list[NoteEvent] = field(default_factory=list)
    is_drum: bool = False


def load_midi(path: str) -> tuple[list[MidiTrackInfo], dict]:
    """Load MIDI file and return normalized tracks + global metadata."""
    raise NotImplementedError("TDD RED: not yet implemented")
