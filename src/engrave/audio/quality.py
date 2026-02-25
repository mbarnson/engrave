"""Post-transcription quality annotation.

Computes heuristic quality metrics from transcribed MIDI files to inform
downstream LLM processing about transcription confidence per stem.

The five metrics capture common failure modes of neural transcription:
  - note_density_per_bar: too high = garbage; zero = separation ate the stem
  - pitch_range_violations: notes outside the instrument's physical range
  - onset_cluster_score: simultaneous onsets on a monophonic stem
  - velocity_variance: suspiciously flat dynamics
  - duration_cv: hallucinated grid patterns
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pretty_midi

# ---------------------------------------------------------------------------
# Instrument pitch ranges (MIDI note numbers)
# ---------------------------------------------------------------------------

INSTRUMENT_RANGES: dict[str, tuple[int, int]] = {
    "piano": (21, 108),
    "bass": (28, 67),
    "guitar": (40, 88),
    "trumpet": (55, 84),
    "trombone": (40, 72),
    "alto_sax": (49, 80),
    "tenor_sax": (44, 75),
    "baritone_sax": (36, 69),
    "flute": (60, 96),
    "clarinet": (50, 91),
    "violin": (55, 103),
    "cello": (36, 76),
    "drums": (35, 81),
}


def get_expected_range(stem_name: str) -> tuple[int, int]:
    """Look up the expected MIDI pitch range for a stem/instrument name.

    Args:
        stem_name: Instrument or stem identifier (case-insensitive).

    Returns:
        (lowest_midi_note, highest_midi_note) for known instruments,
        or (0, 127) for unknown instruments.
    """
    return INSTRUMENT_RANGES.get(stem_name.lower(), (0, 127))


# ---------------------------------------------------------------------------
# Quality dataclass
# ---------------------------------------------------------------------------


@dataclass
class StemQuality:
    """Quality metrics for a single transcribed stem.

    Attributes:
        stem_name: Name of the stem/instrument.
        note_count: Total number of notes in the MIDI.
        note_density_per_bar: Notes per bar (estimated from tempo).
        pitch_range_violations: Count of notes outside the instrument's range.
        onset_cluster_score: Fraction of notes within 10ms of another onset (0-1).
        velocity_variance: Standard deviation of note velocities.
        duration_cv: Coefficient of variation of note durations.
    """

    stem_name: str
    note_count: int
    note_density_per_bar: float
    pitch_range_violations: int
    onset_cluster_score: float
    velocity_variance: float
    duration_cv: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage in job metadata."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Quality annotation
# ---------------------------------------------------------------------------

_ONSET_CLUSTER_THRESHOLD_SEC = 0.010  # 10ms


def annotate_quality(
    midi_path: Path,
    stem_name: str,
    tempo_bpm: float = 120.0,
    expected_range: tuple[int, int] = (0, 127),
) -> StemQuality:
    """Compute quality heuristic metrics from a transcribed MIDI file.

    Args:
        midi_path: Path to the MIDI file to analyze.
        stem_name: Name of the stem/instrument for labeling.
        tempo_bpm: Assumed tempo in BPM for bar estimation.
        expected_range: (low, high) MIDI note range for pitch violations.

    Returns:
        StemQuality with five computed heuristic metrics.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))

    # Collect all non-drum notes across all instruments
    notes: list[pretty_midi.Note] = []
    for instrument in pm.instruments:
        if not instrument.is_drum:
            notes.extend(instrument.notes)

    if not notes:
        return StemQuality(
            stem_name=stem_name,
            note_count=0,
            note_density_per_bar=0.0,
            pitch_range_violations=0,
            onset_cluster_score=0.0,
            velocity_variance=0.0,
            duration_cv=0.0,
        )

    note_count = len(notes)

    # --- note_density_per_bar ---
    duration_sec = pm.get_end_time()
    if duration_sec > 0 and tempo_bpm > 0:
        # bars = duration_sec / seconds_per_bar
        # seconds_per_bar = 60 / tempo_bpm * 4  (assuming 4/4)
        seconds_per_bar = 60.0 / tempo_bpm * 4.0
        estimated_bars = duration_sec / seconds_per_bar
        note_density_per_bar = note_count / estimated_bars if estimated_bars > 0 else 0.0
    else:
        note_density_per_bar = 0.0

    # --- pitch_range_violations ---
    low, high = expected_range
    pitch_range_violations = sum(1 for n in notes if n.pitch < low or n.pitch > high)

    # --- onset_cluster_score ---
    onsets = sorted(n.start for n in notes)
    clustered = 0
    for i, onset in enumerate(onsets):
        for j in range(i + 1, len(onsets)):
            if onsets[j] - onset > _ONSET_CLUSTER_THRESHOLD_SEC:
                break
            clustered += 1
            break  # Only need one neighbor within threshold
        else:
            # Check backward neighbor (for the last note in a cluster)
            if i > 0 and onset - onsets[i - 1] <= _ONSET_CLUSTER_THRESHOLD_SEC:
                clustered += 1
    # Actually recompute more carefully: count notes that have at least one
    # neighbor within 10ms
    clustered = 0
    for i, onset in enumerate(onsets):
        has_neighbor = False
        if i > 0 and onset - onsets[i - 1] <= _ONSET_CLUSTER_THRESHOLD_SEC:
            has_neighbor = True
        if i < len(onsets) - 1 and onsets[i + 1] - onset <= _ONSET_CLUSTER_THRESHOLD_SEC:
            has_neighbor = True
        if has_neighbor:
            clustered += 1
    onset_cluster_score = clustered / note_count

    # --- velocity_variance ---
    velocities = np.array([n.velocity for n in notes], dtype=np.float64)
    velocity_variance = float(np.std(velocities))

    # --- duration_cv ---
    durations = np.array([n.end - n.start for n in notes], dtype=np.float64)
    mean_dur = float(np.mean(durations))
    duration_cv = float(np.std(durations) / mean_dur) if mean_dur > 0 else 0.0

    return StemQuality(
        stem_name=stem_name,
        note_count=note_count,
        note_density_per_bar=note_density_per_bar,
        pitch_range_violations=pitch_range_violations,
        onset_cluster_score=onset_cluster_score,
        velocity_variance=velocity_variance,
        duration_cv=duration_cv,
    )
