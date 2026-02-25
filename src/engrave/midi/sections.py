"""Section boundary detection and splitting -- stub for TDD RED phase."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SectionBoundary:
    """A detected section boundary in the MIDI file."""

    bar_number: int
    boundary_type: (
        str  # "rehearsal_mark"|"time_sig_change"|"key_sig_change"|"tempo_change"|"fixed_length"
    )
    tick: int


def detect_sections(midi_path: str, min_bars: int = 4, max_bars: int = 8) -> list[SectionBoundary]:
    """Detect section boundaries in a MIDI file."""
    raise NotImplementedError("TDD RED: not yet implemented")
