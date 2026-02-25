"""Unit tests for post-transcription quality annotation.

Uses programmatically created MIDI files via pretty_midi for deterministic,
reproducible test fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pretty_midi
import pytest

from engrave.audio.quality import (
    INSTRUMENT_RANGES,
    StemQuality,
    annotate_quality,
    get_expected_range,
)

# ---------------------------------------------------------------------------
# Helpers: create MIDI fixtures
# ---------------------------------------------------------------------------


def _create_midi(
    tmp_path: Path,
    name: str,
    notes: list[tuple[int, float, float, int]],
    *,
    is_drum: bool = False,
) -> Path:
    """Create a MIDI file with specified notes.

    Args:
        tmp_path: Temporary directory for the file.
        name: Filename stem.
        notes: List of (pitch, start, end, velocity) tuples.
        is_drum: Whether the instrument is a drum track.

    Returns:
        Path to the created MIDI file.
    """
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    inst = pretty_midi.Instrument(program=0, is_drum=is_drum)
    for pitch, start, end, velocity in notes:
        inst.notes.append(pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end))
    pm.instruments.append(inst)
    midi_path = tmp_path / f"{name}.mid"
    pm.write(str(midi_path))
    return midi_path


# ---------------------------------------------------------------------------
# annotate_quality: basic functionality
# ---------------------------------------------------------------------------


class TestAnnotateQuality:
    """Test annotate_quality() with known MIDI inputs."""

    def test_basic_quality_metrics(self, tmp_path: Path) -> None:
        """Simple MIDI with 4 evenly spaced notes should produce sane metrics."""
        # 4 quarter notes at 120 bpm, 1 bar = 2 sec
        notes = [
            (60, 0.0, 0.5, 80),
            (62, 0.5, 1.0, 85),
            (64, 1.0, 1.5, 80),
            (65, 1.5, 2.0, 75),
        ]
        midi_path = _create_midi(tmp_path, "basic", notes)
        sq = annotate_quality(midi_path, "piano", tempo_bpm=120.0)

        assert sq.stem_name == "piano"
        assert sq.note_count == 4
        assert sq.note_density_per_bar == pytest.approx(4.0, abs=0.5)
        assert sq.pitch_range_violations == 0  # All within (0, 127)
        assert sq.onset_cluster_score == 0.0  # Well-spaced onsets
        assert sq.velocity_variance > 0  # Varied velocities
        assert sq.duration_cv == 0.0  # All same duration

    def test_returns_stem_quality_instance(self, tmp_path: Path) -> None:
        notes = [(60, 0.0, 0.5, 80)]
        midi_path = _create_midi(tmp_path, "single", notes)
        sq = annotate_quality(midi_path, "test")
        assert isinstance(sq, StemQuality)


# ---------------------------------------------------------------------------
# Note density
# ---------------------------------------------------------------------------


class TestNoteDensity:
    """Test note_density_per_bar calculation."""

    def test_density_known_count(self, tmp_path: Path) -> None:
        """8 notes in exactly 2 bars (4 sec at 120 bpm) = 4 notes/bar."""
        notes = [(60, i * 0.5, i * 0.5 + 0.4, 80) for i in range(8)]
        midi_path = _create_midi(tmp_path, "density", notes)
        sq = annotate_quality(midi_path, "piano", tempo_bpm=120.0)
        assert sq.note_density_per_bar == pytest.approx(4.0, abs=0.5)


# ---------------------------------------------------------------------------
# Pitch range violations
# ---------------------------------------------------------------------------


class TestPitchRangeViolations:
    """Test pitch_range_violations counting."""

    def test_notes_outside_range(self, tmp_path: Path) -> None:
        """2 notes below and 1 above a narrow range should be 3 violations."""
        notes = [
            (20, 0.0, 0.5, 80),  # Below range 40-80
            (30, 0.5, 1.0, 80),  # Below range
            (60, 1.0, 1.5, 80),  # In range
            (90, 1.5, 2.0, 80),  # Above range
        ]
        midi_path = _create_midi(tmp_path, "violations", notes)
        sq = annotate_quality(midi_path, "test", expected_range=(40, 80))
        assert sq.pitch_range_violations == 3

    def test_all_notes_in_range(self, tmp_path: Path) -> None:
        """All notes within range should produce 0 violations."""
        notes = [(60, i * 0.5, i * 0.5 + 0.4, 80) for i in range(4)]
        midi_path = _create_midi(tmp_path, "inrange", notes)
        sq = annotate_quality(midi_path, "test", expected_range=(50, 70))
        assert sq.pitch_range_violations == 0


# ---------------------------------------------------------------------------
# Onset cluster score
# ---------------------------------------------------------------------------


class TestOnsetClusterScore:
    """Test onset_cluster_score detection of simultaneous onsets."""

    def test_simultaneous_onsets(self, tmp_path: Path) -> None:
        """Notes starting at exactly the same time should score > 0."""
        notes = [
            (60, 0.0, 0.5, 80),
            (64, 0.0, 0.5, 80),  # Simultaneous with note 1
            (67, 1.0, 1.5, 80),  # Well separated
        ]
        midi_path = _create_midi(tmp_path, "cluster", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.onset_cluster_score > 0

    def test_well_spaced_onsets(self, tmp_path: Path) -> None:
        """Notes 500ms apart should have 0 cluster score."""
        notes = [(60, i * 0.5, i * 0.5 + 0.4, 80) for i in range(4)]
        midi_path = _create_midi(tmp_path, "spaced", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.onset_cluster_score == 0.0

    def test_near_simultaneous_within_threshold(self, tmp_path: Path) -> None:
        """Notes within 10ms should count as clustered."""
        notes = [
            (60, 0.0, 0.5, 80),
            (64, 0.005, 0.5, 80),  # 5ms later -- within 10ms threshold
            (67, 1.0, 1.5, 80),  # Well separated
        ]
        midi_path = _create_midi(tmp_path, "near", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.onset_cluster_score > 0


# ---------------------------------------------------------------------------
# Velocity variance
# ---------------------------------------------------------------------------


class TestVelocityVariance:
    """Test velocity_variance computation."""

    def test_uniform_velocity_low_variance(self, tmp_path: Path) -> None:
        """All notes at same velocity should produce 0 variance."""
        notes = [(60, i * 0.5, i * 0.5 + 0.4, 80) for i in range(4)]
        midi_path = _create_midi(tmp_path, "uniform_vel", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.velocity_variance == pytest.approx(0.0, abs=0.01)

    def test_varied_velocity_higher_variance(self, tmp_path: Path) -> None:
        """Diverse velocities should produce higher variance."""
        notes = [
            (60, 0.0, 0.5, 30),
            (62, 0.5, 1.0, 60),
            (64, 1.0, 1.5, 90),
            (65, 1.5, 2.0, 120),
        ]
        midi_path = _create_midi(tmp_path, "varied_vel", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.velocity_variance > 20  # Large spread


# ---------------------------------------------------------------------------
# Duration CV
# ---------------------------------------------------------------------------


class TestDurationCV:
    """Test duration coefficient of variation."""

    def test_uniform_durations_low_cv(self, tmp_path: Path) -> None:
        """All same-length notes should produce cv near 0."""
        notes = [(60, i * 0.5, i * 0.5 + 0.4, 80) for i in range(4)]
        midi_path = _create_midi(tmp_path, "uniform_dur", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.duration_cv == pytest.approx(0.0, abs=0.05)

    def test_varied_durations_higher_cv(self, tmp_path: Path) -> None:
        """Mixed note lengths should produce nonzero cv."""
        notes = [
            (60, 0.0, 0.1, 80),  # Very short
            (62, 0.5, 1.5, 80),  # Long
            (64, 2.0, 2.2, 80),  # Short
            (65, 3.0, 5.0, 80),  # Very long
        ]
        midi_path = _create_midi(tmp_path, "varied_dur", notes)
        sq = annotate_quality(midi_path, "test")
        assert sq.duration_cv > 0.3


# ---------------------------------------------------------------------------
# Empty MIDI
# ---------------------------------------------------------------------------


class TestEmptyMidi:
    """Test handling of MIDI files with no notes."""

    def test_empty_midi_returns_zero_quality(self, tmp_path: Path) -> None:
        """MIDI with no notes should return zero-valued StemQuality."""
        pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        midi_path = tmp_path / "empty.mid"
        pm.write(str(midi_path))

        sq = annotate_quality(midi_path, "test")
        assert sq.note_count == 0
        assert sq.note_density_per_bar == 0.0
        assert sq.pitch_range_violations == 0
        assert sq.onset_cluster_score == 0.0
        assert sq.velocity_variance == 0.0
        assert sq.duration_cv == 0.0

    def test_drum_only_midi_returns_zero(self, tmp_path: Path) -> None:
        """MIDI with only drum notes should return zero (drums are excluded)."""
        notes = [(36, 0.0, 0.5, 100), (38, 0.5, 1.0, 100)]
        midi_path = _create_midi(tmp_path, "drums_only", notes, is_drum=True)
        sq = annotate_quality(midi_path, "test")
        assert sq.note_count == 0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    """Test StemQuality.to_dict() serialization."""

    def test_to_dict_all_fields(self) -> None:
        sq = StemQuality(
            stem_name="trumpet",
            note_count=42,
            note_density_per_bar=5.25,
            pitch_range_violations=3,
            onset_cluster_score=0.15,
            velocity_variance=12.5,
            duration_cv=0.45,
        )
        d = sq.to_dict()
        assert d == {
            "stem_name": "trumpet",
            "note_count": 42,
            "note_density_per_bar": 5.25,
            "pitch_range_violations": 3,
            "onset_cluster_score": 0.15,
            "velocity_variance": 12.5,
            "duration_cv": 0.45,
        }

    def test_to_dict_roundtrip(self, tmp_path: Path) -> None:
        """to_dict from annotate_quality should produce serializable output."""
        notes = [(60, 0.0, 0.5, 80), (62, 0.5, 1.0, 85)]
        midi_path = _create_midi(tmp_path, "roundtrip", notes)
        sq = annotate_quality(midi_path, "piano")
        d = sq.to_dict()
        # All values should be JSON-serializable basic types
        import json

        json_str = json.dumps(d)
        assert json_str  # No serialization error


# ---------------------------------------------------------------------------
# Instrument range lookup
# ---------------------------------------------------------------------------


class TestGetExpectedRange:
    """Test get_expected_range() lookup."""

    def test_known_instrument(self) -> None:
        assert get_expected_range("piano") == (21, 108)
        assert get_expected_range("trumpet") == (55, 84)
        assert get_expected_range("bass") == (28, 67)

    def test_case_insensitive(self) -> None:
        assert get_expected_range("Piano") == (21, 108)
        assert get_expected_range("TRUMPET") == (55, 84)

    def test_unknown_instrument_returns_full_range(self) -> None:
        assert get_expected_range("theremin") == (0, 127)
        assert get_expected_range("unknown_stem") == (0, 127)


# ---------------------------------------------------------------------------
# Instrument ranges completeness
# ---------------------------------------------------------------------------


class TestInstrumentRanges:
    """Verify INSTRUMENT_RANGES includes the minimum required set."""

    @pytest.mark.parametrize(
        "instrument",
        [
            "piano",
            "bass",
            "guitar",
            "trumpet",
            "trombone",
            "alto_sax",
            "tenor_sax",
            "baritone_sax",
            "flute",
            "clarinet",
            "violin",
            "cello",
            "drums",
        ],
    )
    def test_minimum_instruments_present(self, instrument: str) -> None:
        assert instrument in INSTRUMENT_RANGES

    def test_ranges_are_valid_tuples(self) -> None:
        for name, (low, high) in INSTRUMENT_RANGES.items():
            assert isinstance(low, int), f"{name} low is not int"
            assert isinstance(high, int), f"{name} high is not int"
            assert 0 <= low < high <= 127, f"{name} range invalid: ({low}, {high})"
