"""MIDI-to-text tokenization for LLM prompts -- stub for TDD RED phase."""

from __future__ import annotations

from engrave.midi.loader import NoteEvent


def tokenize_section_for_prompt(
    notes: list[NoteEvent],
    time_sig: tuple[int, int],
    key: str,
    bars: tuple[int, int],
    ticks_per_beat: int,
) -> str:
    """Convert MIDI notes to LLM-readable text representation."""
    raise NotImplementedError("TDD RED: not yet implemented")
