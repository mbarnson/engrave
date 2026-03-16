"""Unit tests for post-generation quality validation.

Tests the validation module's per-part MIDI comparison using
programmatic MIDI fixtures (pretty_midi) and real mir_eval.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pretty_midi
import pytest

from engrave.generation.validation import (
    PartValidation,
    ValidationResult,
    _compute_part_metrics,
    _detect_pitch_drift,
    _inject_midi_block,
    _match_instruments,
    validate_generation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instrument(
    notes: list[tuple[int, float, float, int]],
    is_drum: bool = False,
    program: int = 0,
) -> pretty_midi.Instrument:
    """Create a pretty_midi Instrument with given notes."""
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for pitch, start, end, vel in notes:
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=start, end=end))
    return inst


def _create_midi_file(
    path: Path,
    instruments: list[pretty_midi.Instrument],
) -> Path:
    """Write a MIDI file with the given instruments."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    for inst in instruments:
        pm.instruments.append(inst)
    pm.write(str(path))
    return path


# ---------------------------------------------------------------------------
# _inject_midi_block
# ---------------------------------------------------------------------------


class TestInjectMidiBlock:
    def test_injects_when_missing(self) -> None:
        ly = r"""
\score {
  << \new Staff \trumpetOne >>
  \layout { }
}
"""
        result = _inject_midi_block(ly)
        assert r"\midi { }" in result
        assert r"\layout" in result

    def test_no_duplicate_when_present(self) -> None:
        ly = r"""
\score {
  << \new Staff \trumpetOne >>
  \layout { }
  \midi { }
}
"""
        result = _inject_midi_block(ly)
        assert result.count(r"\midi") == 1


# ---------------------------------------------------------------------------
# _detect_pitch_drift
# ---------------------------------------------------------------------------


class TestDetectPitchDrift:
    def test_no_drift(self) -> None:
        ref = [60, 62, 64, 65, 67]
        est = [60, 62, 64, 65, 67]
        assert _detect_pitch_drift(ref, est) == 0.0

    def test_octave_drift(self) -> None:
        ref = [60, 62, 64, 65, 67]
        est = [72, 74, 76, 77, 79]  # +12
        drift = _detect_pitch_drift(ref, est)
        assert drift == pytest.approx(12.0, abs=0.5)

    def test_insufficient_data(self) -> None:
        assert _detect_pitch_drift([60, 62], [72, 74]) == 0.0


# ---------------------------------------------------------------------------
# _compute_part_metrics
# ---------------------------------------------------------------------------


class TestComputePartMetrics:
    def test_perfect_match(self) -> None:
        notes = [(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 80), (64, 1.0, 1.5, 80), (65, 1.5, 2.0, 80)]
        ref = _make_instrument(notes)
        est = _make_instrument(notes)

        result = _compute_part_metrics(ref, est, "Trumpet 1")
        assert result.f1 == pytest.approx(1.0, abs=0.01)
        assert result.confidence_pct >= 95
        assert not result.needs_review

    def test_partial_match(self) -> None:
        ref = _make_instrument(
            [(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 80), (64, 1.0, 1.5, 80), (65, 1.5, 2.0, 80)]
        )
        est = _make_instrument([(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 80)])

        result = _compute_part_metrics(ref, est, "Alto Sax")
        assert result.recall < 1.0
        assert result.precision == pytest.approx(1.0, abs=0.01)
        assert result.missing_notes > 0

    def test_both_empty(self) -> None:
        ref = _make_instrument([])
        est = _make_instrument([])
        result = _compute_part_metrics(ref, est, "Silent Part")
        assert result.confidence_pct == 100

    def test_ref_empty_est_has_notes(self) -> None:
        ref = _make_instrument([])
        est = _make_instrument([(60, 0.0, 0.5, 80)])
        result = _compute_part_metrics(ref, est, "Ghost Part")
        assert result.confidence_pct == 0

    def test_octave_drift_reduces_confidence(self) -> None:
        ref = _make_instrument(
            [(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 80), (64, 1.0, 1.5, 80), (65, 1.5, 2.0, 80)]
        )
        # Octave up — pitches don't match at 50 cent tolerance
        est = _make_instrument(
            [(72, 0.0, 0.5, 80), (74, 0.5, 1.0, 80), (76, 1.0, 1.5, 80), (77, 1.5, 2.0, 80)]
        )
        result = _compute_part_metrics(ref, est, "Drifted")
        # F1 should be low (pitch mismatch) AND drift detected
        assert abs(result.pitch_drift_semitones) >= 10
        assert result.confidence_pct < 50


# ---------------------------------------------------------------------------
# _match_instruments
# ---------------------------------------------------------------------------


class TestMatchInstruments:
    def test_basic_matching(self) -> None:
        ref_pm = pretty_midi.PrettyMIDI()
        ref_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)], program=0))
        ref_pm.instruments.append(_make_instrument([(67, 0.0, 0.5, 80)], program=1))

        est_pm = pretty_midi.PrettyMIDI()
        est_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)], program=0))
        est_pm.instruments.append(_make_instrument([(67, 0.0, 0.5, 80)], program=1))

        matches = _match_instruments(ref_pm, est_pm, ["Trumpet", "Bass"])
        assert len(matches) == 2
        assert matches[0][0] == "Trumpet"
        assert matches[1][0] == "Bass"

    def test_drums_excluded(self) -> None:
        ref_pm = pretty_midi.PrettyMIDI()
        ref_pm.instruments.append(_make_instrument([(36, 0.0, 0.5, 80)], is_drum=True))
        ref_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)]))

        est_pm = pretty_midi.PrettyMIDI()
        est_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)]))

        matches = _match_instruments(ref_pm, est_pm, ["Trumpet"])
        assert len(matches) == 1
        # ref should be the non-drum instrument
        assert matches[0][1] is not None
        assert not matches[0][1].is_drum

    def test_missing_estimated_instrument(self) -> None:
        ref_pm = pretty_midi.PrettyMIDI()
        ref_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)]))
        ref_pm.instruments.append(_make_instrument([(67, 0.0, 0.5, 80)]))

        est_pm = pretty_midi.PrettyMIDI()
        est_pm.instruments.append(_make_instrument([(60, 0.0, 0.5, 80)]))

        matches = _match_instruments(ref_pm, est_pm, ["Trumpet", "Bass"])
        assert matches[1][2] is None  # No estimated for Bass


# ---------------------------------------------------------------------------
# PartValidation
# ---------------------------------------------------------------------------


class TestPartValidation:
    def test_needs_review_threshold(self) -> None:
        good = PartValidation(
            part_name="Good",
            f1=0.95,
            precision=0.95,
            recall=0.95,
            rhythm_f1=0.9,
            ref_note_count=100,
            est_note_count=100,
            missing_notes=5,
            extra_notes=5,
            pitch_drift_semitones=0.0,
            confidence_pct=92,
        )
        assert not good.needs_review

        bad = PartValidation(
            part_name="Bad",
            f1=0.5,
            precision=0.5,
            recall=0.5,
            rhythm_f1=0.4,
            ref_note_count=100,
            est_note_count=50,
            missing_notes=50,
            extra_notes=0,
            pitch_drift_semitones=0.0,
            confidence_pct=48,
        )
        assert bad.needs_review


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_overall_confidence(self) -> None:
        result = ValidationResult(
            parts=[
                PartValidation(
                    part_name="A",
                    f1=1.0,
                    precision=1.0,
                    recall=1.0,
                    rhythm_f1=1.0,
                    ref_note_count=10,
                    est_note_count=10,
                    missing_notes=0,
                    extra_notes=0,
                    pitch_drift_semitones=0.0,
                    confidence_pct=100,
                ),
                PartValidation(
                    part_name="B",
                    f1=0.5,
                    precision=0.5,
                    recall=0.5,
                    rhythm_f1=0.4,
                    ref_note_count=10,
                    est_note_count=5,
                    missing_notes=5,
                    extra_notes=0,
                    pitch_drift_semitones=0.0,
                    confidence_pct=48,
                ),
            ],
            success=True,
        )
        assert result.overall_confidence_pct == 74

    def test_empty_parts(self) -> None:
        result = ValidationResult(parts=[], success=True)
        assert result.overall_confidence_pct == 0


# ---------------------------------------------------------------------------
# validate_generation (integration with mock compiler)
# ---------------------------------------------------------------------------


class TestValidateGeneration:
    def test_lilypond_not_found(self) -> None:
        """Gracefully handles missing LilyPond."""
        with patch(
            "engrave.lilypond.compiler.LilyPondCompiler.__init__",
            side_effect=FileNotFoundError("LilyPond not found"),
        ):
            result = validate_generation(
                ly_source='\\version "2.24.4"\n\\score { }',
                original_midi_path="/nonexistent.mid",
                instrument_names=["Trumpet"],
                compiler=None,
            )
        assert not result.success
        assert "not available" in result.error

    def test_compile_failure(self, tmp_path: Path) -> None:
        """Returns error when LilyPond compilation fails."""
        mock_compiler = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stderr = "some error"
        mock_compiler.compile.return_value = mock_result

        ref_midi = _create_midi_file(
            tmp_path / "ref.mid",
            [_make_instrument([(60, 0.0, 0.5, 80)])],
        )

        result = validate_generation(
            ly_source='\\version "2.24.4"\n\\score { \\layout { } }',
            original_midi_path=str(ref_midi),
            instrument_names=["Trumpet"],
            compiler=mock_compiler,
        )
        assert not result.success
        assert "compilation failed" in result.error

    def test_successful_validation(self, tmp_path: Path) -> None:
        """End-to-end validation with mock compiler producing matching MIDI."""
        # Create reference MIDI
        ref_notes = [(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 80)]
        ref_midi = _create_midi_file(
            tmp_path / "ref.mid",
            [_make_instrument(ref_notes)],
        )

        # Create "generated" MIDI (same notes = perfect match)
        gen_midi_path = tmp_path / "output"
        gen_midi_path.mkdir()
        _create_midi_file(
            gen_midi_path / "score.midi",
            [_make_instrument(ref_notes)],
        )

        mock_compiler = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_compiler.compile.return_value = mock_result

        # Patch tempfile to use our prepared directory
        with patch("engrave.generation.validation.tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = lambda s: str(gen_midi_path)
            mock_tmpdir.return_value.__exit__ = lambda s, *a: None

            result = validate_generation(
                ly_source='\\version "2.24.4"\n\\score { \\layout { } }',
                original_midi_path=str(ref_midi),
                instrument_names=["Trumpet"],
                compiler=mock_compiler,
            )

        assert result.success
        assert len(result.parts) == 1
        assert result.parts[0].part_name == "Trumpet"
        assert result.parts[0].f1 == pytest.approx(1.0, abs=0.01)
        assert result.parts[0].confidence_pct >= 95
