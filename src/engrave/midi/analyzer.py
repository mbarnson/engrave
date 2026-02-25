"""Musical property analysis from MIDI using pretty_midi.

Extracts key signature, tempo, time signature, instrument list,
and estimates total bar count from MIDI files.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)

# Krumhansl-Kessler key profiles for major and minor keys
# Used for key estimation from chroma vectors
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Pitch class names in LilyPond format (sharps only for now)
_PITCH_NAMES = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]


@dataclass
class MidiAnalysis:
    """Musical analysis results from a MIDI file."""

    key_signature: str = "c \\major"
    time_signatures: list[tuple[int, int, int]] = field(default_factory=list)
    tempo_changes: list[tuple[float, int]] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    total_bars: int = 0
    ticks_per_beat: int = 480


def _estimate_key(pm: pretty_midi.PrettyMIDI) -> str:
    """Estimate key signature from MIDI using Krumhansl-Kessler profiles.

    Computes chroma vector from all notes, correlates with major and minor
    profiles for each pitch class, returns the best match as a LilyPond key string.
    """
    # Get chroma (12-element array of pitch class energy)
    chroma = pm.get_chroma()
    if chroma.size == 0:
        return "c \\major"

    # Sum across time to get total energy per pitch class
    chroma_sum = chroma.sum(axis=1)
    if chroma_sum.sum() == 0:
        return "c \\major"

    # Normalize
    chroma_norm = chroma_sum / chroma_sum.sum()

    best_corr = -2.0
    best_key = "c"
    best_mode = "\\major"

    for shift in range(12):
        # Rotate chroma to test each root
        rotated = np.roll(chroma_norm, -shift)

        # Correlate with major profile
        major_corr = float(np.corrcoef(rotated, _MAJOR_PROFILE)[0, 1])
        if major_corr > best_corr:
            best_corr = major_corr
            best_key = _PITCH_NAMES[shift]
            best_mode = "\\major"

        # Correlate with minor profile
        minor_corr = float(np.corrcoef(rotated, _MINOR_PROFILE)[0, 1])
        if minor_corr > best_corr:
            best_corr = minor_corr
            best_key = _PITCH_NAMES[shift]
            best_mode = "\\minor"

    return f"{best_key} {best_mode}"


def analyze_midi(path: str) -> MidiAnalysis:
    """Extract musical properties from a MIDI file using pretty_midi.

    Args:
        path: Path to the MIDI file.

    Returns:
        MidiAnalysis with key, tempo, time signature, instruments, and bar count.
    """
    pm = pretty_midi.PrettyMIDI(path)

    # Extract tempo changes
    tempo_change_times, tempi = pm.get_tempo_changes()
    tempo_changes: list[tuple[float, int]] = []
    for bpm, time_sec in zip(tempi, tempo_change_times, strict=True):
        # Convert seconds to approximate tick position
        tick = int(pm.time_to_tick(time_sec))
        tempo_changes.append((float(bpm), tick))

    # If no tempo changes detected, use default
    if not tempo_changes:
        tempo_changes = [(120.0, 0)]

    # Extract time signatures
    time_signatures: list[tuple[int, int, int]] = []
    for ts in pm.time_signature_changes:
        tick = int(pm.time_to_tick(ts.time))
        time_signatures.append((ts.numerator, ts.denominator, tick))

    # Default time signature if none found
    if not time_signatures:
        time_signatures = [(4, 4, 0)]

    # Extract instrument names
    instruments: list[str] = []
    for inst in pm.instruments:
        if inst.is_drum:
            instruments.append("Drums")
        elif inst.name:
            instruments.append(inst.name)
        else:
            instruments.append(pretty_midi.program_to_instrument_name(inst.program))

    # Estimate key
    key_signature = _estimate_key(pm)

    # Estimate total bars from duration and first time signature
    total_duration = pm.get_end_time()
    first_ts_num, first_ts_denom, _ = time_signatures[0]
    # Beats per bar = numerator, beat unit = denominator
    # Duration of one bar in seconds
    first_tempo = tempo_changes[0][0]
    seconds_per_beat = 60.0 / first_tempo
    # Duration of one bar: numerator beats * (4/denominator) quarter-note equivalents
    beats_per_bar = first_ts_num * (4.0 / first_ts_denom)
    bar_duration = beats_per_bar * seconds_per_beat
    total_bars = max(1, math.ceil(total_duration / bar_duration)) if bar_duration > 0 else 1

    return MidiAnalysis(
        key_signature=key_signature,
        time_signatures=time_signatures,
        tempo_changes=tempo_changes,
        instruments=instruments,
        total_bars=total_bars,
        ticks_per_beat=pm.resolution,
    )
