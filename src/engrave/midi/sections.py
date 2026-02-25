"""Section boundary detection and splitting from MIDI files.

Detects section boundaries using a priority chain:
1. Rehearsal marks (MIDI marker meta events)
2. Time signature changes
3. Key signature changes
4. Significant tempo changes (>10%)
5. Fixed-length fallback (every max_bars bars)

Sections shorter than min_bars are merged with the previous section.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mido


@dataclass
class SectionBoundary:
    """A detected section boundary in the MIDI file."""

    bar_number: int
    boundary_type: str
    tick: int


def _tick_to_bar(tick: int, ticks_per_bar: int) -> int:
    """Convert a tick position to a 1-based bar number."""
    if ticks_per_bar <= 0:
        return 1
    return (tick // ticks_per_bar) + 1


def _get_ticks_per_bar(ticks_per_beat: int, numerator: int, denominator: int) -> int:
    """Calculate ticks per bar from time signature."""
    beats_per_bar = numerator * (4.0 / denominator)
    return int(ticks_per_beat * beats_per_bar)


def _estimate_total_bars(midi_path: str) -> tuple[int, int, int]:
    """Estimate total bars, ticks per beat, and ticks per bar from MIDI file.

    Returns:
        (total_bars, ticks_per_beat, ticks_per_bar) using the first time signature.
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat
    numerator, denominator = 4, 4  # default

    # Find first time signature
    for track in mid.tracks:
        for msg in track:
            if msg.type == "time_signature":
                numerator = msg.numerator
                denominator = msg.denominator
                break

    ticks_per_bar = _get_ticks_per_bar(tpb, numerator, denominator)

    # Find total duration in ticks
    total_ticks = 0
    for track in mid.tracks:
        track_ticks = 0
        for msg in track:
            track_ticks += msg.time
        total_ticks = max(total_ticks, track_ticks)

    total_bars = max(1, math.ceil(total_ticks / ticks_per_bar)) if ticks_per_bar > 0 else 1
    return total_bars, tpb, ticks_per_bar


def _scan_structural_boundaries(midi_path: str) -> list[SectionBoundary]:
    """Scan MIDI file for structural boundaries from meta events.

    Returns boundaries sorted by priority and tick position.
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat
    numerator, denominator = 4, 4

    # First pass: find initial time sig
    for track in mid.tracks:
        for msg in track:
            if msg.type == "time_signature":
                numerator = msg.numerator
                denominator = msg.denominator
                break

    ticks_per_bar = _get_ticks_per_bar(tpb, numerator, denominator)
    boundaries: list[SectionBoundary] = []
    prev_tempo: float | None = None

    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time

            if abs_time == 0:
                # Skip events at tick 0 (they're the initial state, not boundaries)
                if msg.type == "set_tempo":
                    prev_tempo = msg.tempo
                continue

            if msg.type == "marker":
                bar_num = _tick_to_bar(abs_time, ticks_per_bar)
                boundaries.append(
                    SectionBoundary(
                        bar_number=bar_num,
                        boundary_type="rehearsal_mark",
                        tick=abs_time,
                    )
                )

            elif msg.type == "time_signature":
                bar_num = _tick_to_bar(abs_time, ticks_per_bar)
                boundaries.append(
                    SectionBoundary(
                        bar_number=bar_num,
                        boundary_type="time_sig_change",
                        tick=abs_time,
                    )
                )
                # Update ticks_per_bar for subsequent bar calculations
                ticks_per_bar = _get_ticks_per_bar(tpb, msg.numerator, msg.denominator)

            elif msg.type == "key_signature":
                bar_num = _tick_to_bar(abs_time, ticks_per_bar)
                boundaries.append(
                    SectionBoundary(
                        bar_number=bar_num,
                        boundary_type="key_sig_change",
                        tick=abs_time,
                    )
                )

            elif msg.type == "set_tempo":
                if prev_tempo is not None:
                    # Check for significant tempo change (>10%)
                    change_ratio = abs(msg.tempo - prev_tempo) / prev_tempo
                    if change_ratio > 0.10:
                        bar_num = _tick_to_bar(abs_time, ticks_per_bar)
                        boundaries.append(
                            SectionBoundary(
                                bar_number=bar_num,
                                boundary_type="tempo_change",
                                tick=abs_time,
                            )
                        )
                prev_tempo = msg.tempo

    # Sort by tick position, then by priority
    priority_order = {
        "rehearsal_mark": 0,
        "time_sig_change": 1,
        "key_sig_change": 2,
        "tempo_change": 3,
    }
    boundaries.sort(key=lambda b: (b.tick, priority_order.get(b.boundary_type, 99)))

    # Deduplicate boundaries at the same bar (keep highest priority)
    seen_bars: set[int] = set()
    deduped: list[SectionBoundary] = []
    for b in boundaries:
        if b.bar_number not in seen_bars:
            seen_bars.add(b.bar_number)
            deduped.append(b)

    return deduped


def _merge_short_sections(
    boundaries: list[SectionBoundary], min_bars: int, total_bars: int
) -> list[SectionBoundary]:
    """Remove boundaries that would create sections shorter than min_bars."""
    if not boundaries:
        return boundaries

    merged: list[SectionBoundary] = [boundaries[0]]

    for i in range(1, len(boundaries)):
        gap = boundaries[i].bar_number - merged[-1].bar_number
        if gap >= min_bars:
            merged.append(boundaries[i])
        # Otherwise drop this boundary (section too short, merge with previous)

    return merged


def detect_sections(midi_path: str, min_bars: int = 4, max_bars: int = 8) -> list[SectionBoundary]:
    """Detect section boundaries in a MIDI file.

    Priority chain for boundary detection:
    1. Rehearsal marks from MIDI meta events (marker messages)
    2. Time signature changes
    3. Key signature changes
    4. Significant tempo changes (>10% change)
    5. Fixed-length fallback (every max_bars bars)

    Args:
        midi_path: Path to the MIDI file.
        min_bars: Minimum section length in bars.
        max_bars: Maximum section length / fallback interval.

    Returns:
        List of SectionBoundary objects marking where each section starts.
    """
    total_bars, _tpb, ticks_per_bar = _estimate_total_bars(midi_path)

    # Get structural boundaries from meta events
    structural = _scan_structural_boundaries(midi_path)

    if structural:
        # Ensure bar 1 is always a boundary
        if not any(b.bar_number == 1 for b in structural):
            structural.insert(
                0,
                SectionBoundary(bar_number=1, boundary_type=structural[0].boundary_type, tick=0),
            )

        # Merge short sections
        merged = _merge_short_sections(structural, min_bars, total_bars)

        # Fill gaps larger than max_bars with fixed-length boundaries
        filled: list[SectionBoundary] = []
        for i, boundary in enumerate(merged):
            filled.append(boundary)
            # Check gap to next boundary (or end)
            next_bar = merged[i + 1].bar_number if i + 1 < len(merged) else total_bars + 1
            gap = next_bar - boundary.bar_number
            if gap > max_bars:
                # Insert fixed-length boundaries in the gap
                current = boundary.bar_number + max_bars
                while current < next_bar:
                    tick = (current - 1) * ticks_per_bar
                    filled.append(
                        SectionBoundary(
                            bar_number=current,
                            boundary_type="fixed_length",
                            tick=tick,
                        )
                    )
                    current += max_bars

        return filled

    # No structural boundaries found: use fixed-length fallback
    boundaries: list[SectionBoundary] = []
    current_bar = 1
    while current_bar <= total_bars:
        tick = (current_bar - 1) * ticks_per_bar
        boundaries.append(
            SectionBoundary(
                bar_number=current_bar,
                boundary_type="fixed_length",
                tick=tick,
            )
        )
        current_bar += max_bars

    return boundaries
