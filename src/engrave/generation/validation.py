"""Post-generation quality validation: compare output vs input MIDI.

Renders the generated LilyPond back to MIDI via the LilyPond compiler,
then compares against the original input MIDI using mir_eval per
instrument part.  Reports per-part confidence scores (F1, precision,
recall) and flags for systematic errors like octave drift.

Metrics per part:
- Note-level F1 score (pitch + onset accuracy)
- Rhythm accuracy (duration matching via offset_ratio)
- Pitch drift detection (systematic octave or transposition errors)
- Missing/extra note count
"""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)


@dataclass
class PartValidation:
    """Quality metrics for a single instrument part."""

    part_name: str
    f1: float
    precision: float
    recall: float
    rhythm_f1: float
    ref_note_count: int
    est_note_count: int
    missing_notes: int
    extra_notes: int
    pitch_drift_semitones: float
    confidence_pct: int  # 0-100 integer for display

    @property
    def needs_review(self) -> bool:
        """True if the part should be flagged for manual review."""
        return self.confidence_pct < 80


@dataclass
class ValidationResult:
    """Aggregate validation result for all parts."""

    parts: list[PartValidation] = field(default_factory=list)
    success: bool = True
    error: str | None = None

    @property
    def overall_confidence_pct(self) -> int:
        """Mean confidence across all parts."""
        if not self.parts:
            return 0
        return int(sum(p.confidence_pct for p in self.parts) / len(self.parts))


def _inject_midi_block(ly_source: str) -> str:
    """Inject ``\\midi { }`` into the score block if not already present.

    The assembler's output only includes ``\\layout { }``.  To get MIDI
    output from LilyPond we need ``\\midi { }`` alongside it.
    """
    if r"\midi" in ly_source:
        return ly_source
    # Insert \midi { } just before the closing of the \score block.
    # The score block ends with "}" at top indentation after \layout { ... }.
    return re.sub(
        r"(\\layout\s*\{[^}]*\})",
        r"\1\n  \\midi { }",
        ly_source,
    )


def _extract_note_arrays_for_instrument(
    instrument: pretty_midi.Instrument,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract (intervals, pitches_hz) arrays for a single instrument."""
    if not instrument.notes:
        return np.zeros((0, 2)), np.zeros(0)
    intervals = [[n.start, n.end] for n in instrument.notes]
    pitches = [pretty_midi.note_number_to_hz(n.pitch) for n in instrument.notes]
    return np.array(intervals), np.array(pitches)


def _detect_pitch_drift(
    ref_pitches_midi: list[int],
    est_pitches_midi: list[int],
) -> float:
    """Detect systematic pitch offset between reference and estimated.

    Computes the median pitch difference (in semitones) between matched
    notes.  A value near +12 or -12 indicates octave drift; near +/-7
    indicates a fifth transposition error, etc.

    Returns 0.0 if insufficient data for comparison.
    """
    if len(ref_pitches_midi) < 4 or len(est_pitches_midi) < 4:
        return 0.0

    # Compare the pitch distributions via histogram binning
    ref_arr = np.array(ref_pitches_midi, dtype=float)
    est_arr = np.array(est_pitches_midi, dtype=float)

    # Use median pitch as a rough proxy for systematic offset
    drift = float(np.median(est_arr) - np.median(ref_arr))
    return round(drift, 1)


def _compute_part_metrics(
    ref_instrument: pretty_midi.Instrument,
    est_instrument: pretty_midi.Instrument,
    part_name: str,
) -> PartValidation:
    """Compute validation metrics for a single part.

    Uses mir_eval transcription metrics for both note-level (onset-only)
    and rhythm (onset+offset) evaluation.
    """
    ref_intervals, ref_pitches = _extract_note_arrays_for_instrument(ref_instrument)
    est_intervals, est_pitches = _extract_note_arrays_for_instrument(est_instrument)

    ref_count = len(ref_intervals)
    est_count = len(est_intervals)

    # Handle empty cases
    if ref_count == 0 and est_count == 0:
        return PartValidation(
            part_name=part_name,
            f1=1.0,
            precision=1.0,
            recall=1.0,
            rhythm_f1=1.0,
            ref_note_count=0,
            est_note_count=0,
            missing_notes=0,
            extra_notes=0,
            pitch_drift_semitones=0.0,
            confidence_pct=100,
        )
    if ref_count == 0 or est_count == 0:
        return PartValidation(
            part_name=part_name,
            f1=0.0,
            precision=0.0,
            recall=0.0,
            rhythm_f1=0.0,
            ref_note_count=ref_count,
            est_note_count=est_count,
            missing_notes=ref_count,
            extra_notes=est_count,
            pitch_drift_semitones=0.0,
            confidence_pct=0,
        )

    # Note-level F1 (onset only, ignore offsets)
    precision, recall, f1, _overlap = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches,
        est_intervals,
        est_pitches,
        onset_tolerance=0.05,
        pitch_tolerance=50.0,
        offset_ratio=None,
    )

    # Rhythm F1 (onset + offset matching)
    _r_prec, _r_rec, r_f1, _r_ov = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches,
        est_intervals,
        est_pitches,
        onset_tolerance=0.05,
        pitch_tolerance=50.0,
        offset_ratio=0.2,
    )

    # Pitch drift detection
    ref_midi_pitches = [n.pitch for n in ref_instrument.notes]
    est_midi_pitches = [n.pitch for n in est_instrument.notes]
    drift = _detect_pitch_drift(ref_midi_pitches, est_midi_pitches)

    # Missing/extra notes (approximate via recall/precision)
    matched_ref = round(float(recall) * ref_count)
    matched_est = round(float(precision) * est_count)
    missing = ref_count - matched_ref
    extra = est_count - matched_est

    # Confidence: weighted blend of F1 (70%) and rhythm F1 (30%),
    # penalized for pitch drift
    raw_confidence = 0.7 * float(f1) + 0.3 * float(r_f1)
    # Penalize drift: each semitone of drift reduces confidence by 5%
    drift_penalty = min(abs(drift) * 0.05, 0.5)
    confidence = max(0.0, raw_confidence - drift_penalty)
    confidence_pct = round(confidence * 100)

    return PartValidation(
        part_name=part_name,
        f1=float(f1),
        precision=float(precision),
        recall=float(recall),
        rhythm_f1=float(r_f1),
        ref_note_count=ref_count,
        est_note_count=est_count,
        missing_notes=missing,
        extra_notes=extra,
        pitch_drift_semitones=drift,
        confidence_pct=confidence_pct,
    )


def _match_instruments(
    ref_pm: pretty_midi.PrettyMIDI,
    est_pm: pretty_midi.PrettyMIDI,
    instrument_names: list[str],
) -> list[tuple[str, pretty_midi.Instrument | None, pretty_midi.Instrument | None]]:
    """Match instruments between reference and estimated MIDI by order.

    Both the original MIDI and the LilyPond-generated MIDI produce
    instruments in the same track order as the instrument_names list.

    Returns list of (name, ref_instrument, est_instrument) tuples.
    """
    # Filter out drums from both
    ref_instruments = [i for i in ref_pm.instruments if not i.is_drum]
    est_instruments = [i for i in est_pm.instruments if not i.is_drum]

    results: list[tuple[str, pretty_midi.Instrument | None, pretty_midi.Instrument | None]] = []

    for idx, name in enumerate(instrument_names):
        ref_inst = ref_instruments[idx] if idx < len(ref_instruments) else None
        est_inst = est_instruments[idx] if idx < len(est_instruments) else None
        results.append((name, ref_inst, est_inst))

    return results


def validate_generation(
    ly_source: str,
    original_midi_path: str,
    instrument_names: list[str],
    compiler: object | None = None,
) -> ValidationResult:
    """Validate generated LilyPond against original MIDI input.

    1. Inject ``\\midi { }`` into the assembled .ly source
    2. Compile via LilyPond to produce a MIDI file
    3. Load both MIDIs via pretty_midi
    4. Compare per-instrument using mir_eval
    5. Return per-part confidence scores

    Args:
        ly_source: Complete assembled LilyPond source string.
        original_midi_path: Path to the original input MIDI file.
        instrument_names: List of instrument names from the pipeline.
        compiler: Optional LilyPondCompiler instance.  If None, creates one.

    Returns:
        ValidationResult with per-part metrics.
    """
    from engrave.lilypond.compiler import LilyPondCompiler

    if compiler is None:
        try:
            compiler = LilyPondCompiler(timeout=30)
        except FileNotFoundError:
            logger.warning("LilyPond not found; skipping validation")
            return ValidationResult(
                success=False,
                error="LilyPond not available for validation",
            )

    # 1. Inject \midi block
    ly_with_midi = _inject_midi_block(ly_source)

    # 2. Compile to get MIDI output
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        compile_result = compiler.compile(ly_with_midi, output_dir=tmp_path)

        if not compile_result.success:
            logger.warning("Validation compile failed: %s", compile_result.stderr[:200])
            return ValidationResult(
                success=False,
                error="LilyPond compilation failed during validation",
            )

        # LilyPond places the .midi file alongside the .pdf
        midi_files = list(tmp_path.glob("*.midi")) + list(tmp_path.glob("*.mid"))
        if not midi_files:
            logger.warning("No MIDI output from LilyPond compilation")
            return ValidationResult(
                success=False,
                error="LilyPond did not produce MIDI output",
            )

        generated_midi_path = midi_files[0]

        # 3. Load both MIDIs
        try:
            ref_pm = pretty_midi.PrettyMIDI(str(original_midi_path))
            est_pm = pretty_midi.PrettyMIDI(str(generated_midi_path))
        except Exception as exc:
            logger.warning("Failed to load MIDI files for validation: %s", exc)
            return ValidationResult(success=False, error=str(exc))

        # 4. Match and compare instruments
        matches = _match_instruments(ref_pm, est_pm, instrument_names)

        parts: list[PartValidation] = []
        for name, ref_inst, est_inst in matches:
            if ref_inst is None and est_inst is None:
                continue
            # Create empty instrument stand-in if one side is missing
            if ref_inst is None:
                ref_inst = pretty_midi.Instrument(program=0)
            if est_inst is None:
                est_inst = pretty_midi.Instrument(program=0)

            part_result = _compute_part_metrics(ref_inst, est_inst, name)
            parts.append(part_result)

        return ValidationResult(parts=parts, success=True)
