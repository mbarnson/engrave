"""Unit tests for benchmark MIDI diff evaluator.

Uses programmatic MIDI fixtures created with pretty_midi and tests both
mocked mir_eval (for argument verification) and real mir_eval (for
integration validation -- it's a pure Python library safe to use in tests).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pretty_midi
import pytest

from engrave.benchmark.evaluator import MidiDiffResult, diff_midi


def _create_midi_with_notes(
    path: Path,
    notes: list[tuple[int, float, float, int]],
    is_drum: bool = False,
) -> Path:
    """Create a MIDI file with the given notes.

    Args:
        path: Output MIDI file path.
        notes: List of (pitch, start, end, velocity) tuples.
        is_drum: Whether this instrument is a drum kit.

    Returns:
        Path to the created MIDI file.
    """
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0, is_drum=is_drum)
    for pitch, start, end, velocity in notes:
        note = pretty_midi.Note(
            velocity=velocity,
            pitch=pitch,
            start=start,
            end=end,
        )
        instrument.notes.append(note)
    pm.instruments.append(instrument)
    pm.write(str(path))
    return path


@pytest.fixture
def reference_midi(tmp_path: Path) -> Path:
    """Reference MIDI with 4 quarter notes: C4, D4, E4, F4."""
    return _create_midi_with_notes(
        tmp_path / "reference.mid",
        [
            (60, 0.0, 0.5, 80),  # C4
            (62, 0.5, 1.0, 80),  # D4
            (64, 1.0, 1.5, 80),  # E4
            (65, 1.5, 2.0, 80),  # F4
        ],
    )


@pytest.fixture
def perfect_estimated_midi(tmp_path: Path) -> Path:
    """Estimated MIDI matching reference exactly."""
    return _create_midi_with_notes(
        tmp_path / "perfect_est.mid",
        [
            (60, 0.0, 0.5, 80),
            (62, 0.5, 1.0, 80),
            (64, 1.0, 1.5, 80),
            (65, 1.5, 2.0, 80),
        ],
    )


@pytest.fixture
def partial_estimated_midi(tmp_path: Path) -> Path:
    """Estimated MIDI with only 2 of 4 reference notes."""
    return _create_midi_with_notes(
        tmp_path / "partial_est.mid",
        [
            (60, 0.0, 0.5, 80),  # C4 - matches
            (62, 0.5, 1.0, 80),  # D4 - matches
        ],
    )


@pytest.fixture
def phantom_estimated_midi(tmp_path: Path) -> Path:
    """Estimated MIDI with all reference notes plus phantom extras."""
    return _create_midi_with_notes(
        tmp_path / "phantom_est.mid",
        [
            (60, 0.0, 0.5, 80),  # C4 - matches
            (62, 0.5, 1.0, 80),  # D4 - matches
            (64, 1.0, 1.5, 80),  # E4 - matches
            (65, 1.5, 2.0, 80),  # F4 - matches
            (67, 2.0, 2.5, 80),  # G4 - phantom
            (69, 2.5, 3.0, 80),  # A4 - phantom
        ],
    )


@pytest.fixture
def empty_midi(tmp_path: Path) -> Path:
    """MIDI file with no notes."""
    return _create_midi_with_notes(tmp_path / "empty.mid", [])


class TestDiffMidiWithRealMirEval:
    """Integration tests using real mir_eval (pure Python, safe in tests)."""

    def test_perfect_match_gives_f1_one(
        self, reference_midi: Path, perfect_estimated_midi: Path
    ) -> None:
        """Perfect match between reference and estimated gives F1 = 1.0."""
        result = diff_midi(reference_midi, perfect_estimated_midi)

        assert isinstance(result, MidiDiffResult)
        assert result.f1 == pytest.approx(1.0, abs=0.01)
        assert result.precision == pytest.approx(1.0, abs=0.01)
        assert result.recall == pytest.approx(1.0, abs=0.01)

    def test_partial_match_recall_below_one(
        self, reference_midi: Path, partial_estimated_midi: Path
    ) -> None:
        """Partial match: precision high (estimated notes are correct), recall low."""
        result = diff_midi(reference_midi, partial_estimated_midi)

        # 2 of 2 estimated notes match -> precision ~ 1.0
        assert result.precision == pytest.approx(1.0, abs=0.01)
        # 2 of 4 reference notes matched -> recall ~ 0.5
        assert result.recall == pytest.approx(0.5, abs=0.01)
        # F1 should be between precision and recall
        assert 0.0 < result.f1 < 1.0

    def test_phantom_notes_precision_below_one(
        self, reference_midi: Path, phantom_estimated_midi: Path
    ) -> None:
        """Extra phantom notes: recall high (all ref matched), precision lower."""
        result = diff_midi(reference_midi, phantom_estimated_midi)

        # All 4 reference notes found -> recall ~ 1.0
        assert result.recall == pytest.approx(1.0, abs=0.01)
        # 4 of 6 estimated notes match -> precision ~ 0.67
        assert result.precision < 1.0
        assert result.precision > 0.5

    def test_empty_reference_returns_zeros(
        self, empty_midi: Path, perfect_estimated_midi: Path
    ) -> None:
        """Empty reference MIDI returns all zeros."""
        result = diff_midi(empty_midi, perfect_estimated_midi)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.avg_overlap == 0.0

    def test_empty_estimated_returns_zeros(self, reference_midi: Path, empty_midi: Path) -> None:
        """Empty estimated MIDI returns all zeros."""
        result = diff_midi(reference_midi, empty_midi)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_both_empty_returns_zeros(self, empty_midi: Path, tmp_path: Path) -> None:
        """Both empty MIDI files return all zeros."""
        empty2 = _create_midi_with_notes(tmp_path / "empty2.mid", [])
        result = diff_midi(empty_midi, empty2)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_custom_onset_tolerance(self, reference_midi: Path, tmp_path: Path) -> None:
        """Onset tolerance affects matching: tight tolerance can miss notes."""
        # Create estimated with slightly shifted onsets (30ms off)
        shifted = _create_midi_with_notes(
            tmp_path / "shifted.mid",
            [
                (60, 0.03, 0.53, 80),
                (62, 0.53, 1.03, 80),
                (64, 1.03, 1.53, 80),
                (65, 1.53, 2.03, 80),
            ],
        )

        # 50ms tolerance should match all
        result_wide = diff_midi(reference_midi, shifted, onset_tolerance=0.05)
        assert result_wide.f1 == pytest.approx(1.0, abs=0.01)

        # 10ms tolerance should miss notes shifted by 30ms
        result_tight = diff_midi(reference_midi, shifted, onset_tolerance=0.01)
        assert result_tight.f1 < 1.0

    def test_drum_notes_excluded(self, reference_midi: Path, tmp_path: Path) -> None:
        """Drum instruments are excluded from evaluation."""
        drum_midi = _create_midi_with_notes(
            tmp_path / "drums.mid",
            [(36, 0.0, 0.5, 80), (38, 0.5, 1.0, 80)],
            is_drum=True,
        )

        # Drums-only estimated vs pitched reference -> zeros (no pitched notes)
        result = diff_midi(reference_midi, drum_midi)
        assert result.precision == 0.0
        assert result.recall == 0.0


class TestDiffMidiMocked:
    """Tests with mocked mir_eval to verify correct argument passing."""

    def test_passes_correct_args_to_mir_eval(
        self, reference_midi: Path, perfect_estimated_midi: Path
    ) -> None:
        """Verify correct arrays and parameters passed to mir_eval."""
        with patch(
            "engrave.benchmark.evaluator.mir_eval.transcription.precision_recall_f1_overlap"
        ) as mock_eval:
            mock_eval.return_value = (0.9, 0.8, 0.85, 0.7)

            result = diff_midi(
                reference_midi,
                perfect_estimated_midi,
                onset_tolerance=0.1,
            )

            mock_eval.assert_called_once()
            call_kwargs = mock_eval.call_args
            # Verify onset_tolerance passed through
            assert call_kwargs.kwargs["onset_tolerance"] == 0.1
            # Verify intervals shape (N x 2)
            ref_intervals = call_kwargs.args[0]
            assert ref_intervals.shape[1] == 2
            assert ref_intervals.shape[0] == 4  # 4 reference notes
            # Verify result unpacking
            assert result.precision == 0.9
            assert result.recall == 0.8
            assert result.f1 == 0.85
            assert result.avg_overlap == 0.7


class TestMidiDiffResult:
    """Tests for MidiDiffResult dataclass."""

    def test_fields_accessible(self) -> None:
        """All fields are accessible on the dataclass."""
        result = MidiDiffResult(precision=0.9, recall=0.8, f1=0.85, avg_overlap=0.7)
        assert result.precision == 0.9
        assert result.recall == 0.8
        assert result.f1 == 0.85
        assert result.avg_overlap == 0.7
