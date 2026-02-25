"""MIDI diff evaluation using mir_eval for note-level accuracy comparison.

Compares a reference MIDI file against an estimated (transcribed) MIDI file
using mir_eval's transcription metrics: precision, recall, F1, and average
overlap ratio. Both files are loaded through pretty_midi to ensure consistent
pitch and timing representation (per research pitfall #6).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)


@dataclass
class MidiDiffResult:
    """Result of comparing reference and estimated MIDI files.

    Attributes:
        precision: Fraction of estimated notes matching a reference note.
        recall: Fraction of reference notes matched by an estimated note.
        f1: Harmonic mean of precision and recall.
        avg_overlap: Average temporal overlap ratio for matched note pairs.
    """

    precision: float
    recall: float
    f1: float
    avg_overlap: float


def _extract_note_arrays(
    pm: pretty_midi.PrettyMIDI,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract (intervals, pitches_hz) arrays from all non-drum instruments.

    Args:
        pm: A PrettyMIDI object.

    Returns:
        Tuple of (intervals, pitches_hz) where:
        - intervals is an Nx2 array of [onset, offset] times in seconds
        - pitches_hz is an N-length array of frequencies in Hz
    """
    intervals = []
    pitches = []

    for instrument in pm.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            intervals.append([note.start, note.end])
            pitches.append(pretty_midi.note_number_to_hz(note.pitch))

    if not intervals:
        return np.zeros((0, 2)), np.zeros(0)

    return np.array(intervals), np.array(pitches)


def diff_midi(
    reference_path: Path,
    estimated_path: Path,
    onset_tolerance: float = 0.05,
) -> MidiDiffResult:
    """Compare reference and estimated MIDI files using mir_eval.

    Both MIDI files are loaded through pretty_midi to ensure consistent
    pitch/timing representation. Uses ``mir_eval.transcription.
    precision_recall_f1_overlap()`` for note-level evaluation.

    Args:
        reference_path: Path to the ground truth MIDI file.
        estimated_path: Path to the transcribed/estimated MIDI file.
        onset_tolerance: Maximum onset time difference (seconds) for a
            note to be considered a match. Default: 0.05s (50ms).

    Returns:
        MidiDiffResult with precision, recall, F1, and average overlap.
    """
    logger.info(
        "Diffing MIDI: ref=%s, est=%s, tolerance=%s",
        reference_path,
        estimated_path,
        onset_tolerance,
    )

    ref_pm = pretty_midi.PrettyMIDI(str(reference_path))
    est_pm = pretty_midi.PrettyMIDI(str(estimated_path))

    ref_intervals, ref_pitches = _extract_note_arrays(ref_pm)
    est_intervals, est_pitches = _extract_note_arrays(est_pm)

    # Handle edge cases: empty reference or estimated
    if len(ref_intervals) == 0 or len(est_intervals) == 0:
        if len(ref_intervals) == 0 and len(est_intervals) == 0:
            logger.info("Both reference and estimated MIDI are empty.")
        elif len(ref_intervals) == 0:
            logger.warning("Reference MIDI has no notes.")
        else:
            logger.warning("Estimated MIDI has no notes.")
        return MidiDiffResult(precision=0.0, recall=0.0, f1=0.0, avg_overlap=0.0)

    precision, recall, f1, avg_overlap = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches,
        est_intervals,
        est_pitches,
        onset_tolerance=onset_tolerance,
        pitch_tolerance=50.0,  # cents -- default mir_eval value
        offset_ratio=None,  # ignore offsets for initial evaluation
    )

    return MidiDiffResult(
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        avg_overlap=float(avg_overlap),
    )
