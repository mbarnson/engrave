"""Musical property analysis from MIDI -- stub for TDD RED phase."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MidiAnalysis:
    """Musical analysis results from a MIDI file."""

    key_signature: str = "c \\major"
    time_signatures: list[tuple[int, int, int]] = field(default_factory=list)
    tempo_changes: list[tuple[float, int]] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    total_bars: int = 0
    ticks_per_beat: int = 480


def analyze_midi(path: str) -> MidiAnalysis:
    """Use pretty_midi to extract musical properties from a MIDI file."""
    raise NotImplementedError("TDD RED: not yet implemented")
