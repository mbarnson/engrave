"""Tests for LilyPond-to-music21 pitch name conversion."""

import pytest

from engrave.musicxml.pitch_map import ly_key_to_m21, ly_pitch_to_m21


class TestLyPitchToM21:
    """Test ly_pitch_to_m21 conversion from LilyPond pitch names to music21 strings."""

    # --- Naturals ---

    @pytest.mark.parametrize(
        "ly, expected",
        [
            ("c3", "C3"),
            ("d4", "D4"),
            ("e5", "E5"),
            ("f2", "F2"),
            ("g6", "G6"),
            ("a1", "A1"),
            ("b7", "B7"),
        ],
    )
    def test_naturals(self, ly: str, expected: str) -> None:
        assert ly_pitch_to_m21(ly) == expected

    # --- Flats (short form: f suffix) ---

    @pytest.mark.parametrize(
        "ly, expected",
        [
            ("cf4", "C-4"),
            ("df3", "D-3"),
            ("ef5", "E-5"),
            ("gf2", "G-2"),
            ("af6", "A-6"),
            ("bf4", "B-4"),
        ],
    )
    def test_flats_short(self, ly: str, expected: str) -> None:
        assert ly_pitch_to_m21(ly) == expected

    # --- Flats (long form: es suffix) ---

    @pytest.mark.parametrize(
        "ly, expected",
        [
            ("ces4", "C-4"),
            ("des3", "D-3"),
            ("ees5", "E-5"),
            ("fes2", "F-2"),
            ("ges6", "G-6"),
            ("aes1", "A-1"),
            ("bes4", "B-4"),
        ],
    )
    def test_flats_long(self, ly: str, expected: str) -> None:
        assert ly_pitch_to_m21(ly) == expected

    # --- Sharps (short form: s suffix) ---

    @pytest.mark.parametrize(
        "ly, expected",
        [
            ("cs4", "C#4"),
            ("ds3", "D#3"),
            ("fs5", "F#5"),
            ("gs2", "G#2"),
        ],
    )
    def test_sharps_short(self, ly: str, expected: str) -> None:
        assert ly_pitch_to_m21(ly) == expected

    # --- Sharps (long form: is suffix) ---

    @pytest.mark.parametrize(
        "ly, expected",
        [
            ("cis4", "C#4"),
            ("dis3", "D#3"),
            ("eis5", "E#5"),
            ("fis2", "F#2"),
            ("gis6", "G#6"),
            ("ais1", "A#1"),
            ("bis7", "B#7"),
        ],
    )
    def test_sharps_long(self, ly: str, expected: str) -> None:
        assert ly_pitch_to_m21(ly) == expected

    # --- Edge case: 'es' and 'as' ambiguity ---
    # 'es' is E-sharp (eis) short form? No -- in LilyPond 'es' means E-flat.
    # 'as' means A-flat in LilyPond (short for 'aes').

    def test_es_is_e_flat(self) -> None:
        """In LilyPond, 'es4' means E-flat 4 (abbreviation of 'ees')."""
        assert ly_pitch_to_m21("es4") == "E-4"

    def test_as_is_a_flat(self) -> None:
        """In LilyPond, 'as4' means A-flat 4 (abbreviation of 'aes')."""
        assert ly_pitch_to_m21("as4") == "A-4"

    # --- Octave range ---

    @pytest.mark.parametrize("octave", range(0, 9))
    def test_all_octaves(self, octave: int) -> None:
        assert ly_pitch_to_m21(f"c{octave}") == f"C{octave}"

    # --- Error cases ---

    def test_invalid_pitch_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            ly_pitch_to_m21("invalid")

    def test_no_octave_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            ly_pitch_to_m21("bf")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            ly_pitch_to_m21("")

    def test_unknown_accidental_raises(self) -> None:
        with pytest.raises(ValueError):
            ly_pitch_to_m21("cx4")


class TestLyKeyToM21:
    """Test ly_key_to_m21 conversion from LilyPond key strings to music21 Key strings."""

    @pytest.mark.parametrize(
        "ly_key, expected",
        [
            ("c_major", "C"),
            ("g_major", "G"),
            ("d_major", "D"),
            ("bf_major", "B-"),
            ("ef_major", "E-"),
            ("fs_minor", "f#"),
            ("c_minor", "c"),
            ("a_minor", "a"),
            ("g_minor", "g"),
            ("bf_minor", "b-"),
        ],
    )
    def test_key_conversions(self, ly_key: str, expected: str) -> None:
        assert ly_key_to_m21(ly_key) == expected

    def test_invalid_key_raises(self) -> None:
        with pytest.raises(ValueError):
            ly_key_to_m21("invalid")

    def test_missing_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            ly_key_to_m21("c")
