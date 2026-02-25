"""Tests for conductor score LilyPond generation.

Covers: generate_conductor_score and generate_music_definitions from
engrave.rendering.generator.
"""

from __future__ import annotations

from engrave.rendering.ensemble import BIG_BAND

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _var_names() -> list[str]:
    """Return all variable names from BIG_BAND in score order."""
    return [inst.variable_name for inst in BIG_BAND.instruments]


def _generate_score() -> str:
    """Generate a conductor score string using defaults."""
    from engrave.rendering.generator import generate_conductor_score

    return generate_conductor_score(preset=BIG_BAND, music_var_names=_var_names())


def _generate_definitions() -> str:
    """Generate a music-definitions string for testing."""
    from engrave.rendering.generator import generate_music_definitions

    music_vars = {
        "altoSaxOne": "c'4 d' e' f'",
        "trumpetOne": "g'4 a' b' c''",
    }
    global_music = r"\time 4/4 s1*8"
    chord_symbols = r"\chordmode { c1:maj7 }"
    return generate_music_definitions(
        music_vars=music_vars,
        global_music=global_music,
        chord_symbols=chord_symbols,
    )


# ---------------------------------------------------------------------------
# generate_music_definitions tests
# ---------------------------------------------------------------------------


class TestMusicDefinitions:
    """Tests for the shared music-definitions.ly output."""

    def test_definitions_has_version_header(self) -> None:
        output = _generate_definitions()
        assert output.startswith('\\version "2.24.4"')

    def test_definitions_has_global_music(self) -> None:
        output = _generate_definitions()
        assert "globalMusic" in output

    def test_definitions_has_instrument_variables(self) -> None:
        output = _generate_definitions()
        assert "altoSaxOne" in output
        assert "trumpetOne" in output

    def test_definitions_has_chord_symbols(self) -> None:
        output = _generate_definitions()
        assert "chordSymbols" in output

    def test_definitions_no_chords_when_none(self) -> None:
        from engrave.rendering.generator import generate_music_definitions

        output = generate_music_definitions(
            music_vars={"altoSaxOne": "c'4"},
            global_music=r"\time 4/4 s1",
            chord_symbols=None,
        )
        assert "chordSymbols" not in output


# ---------------------------------------------------------------------------
# generate_conductor_score tests
# ---------------------------------------------------------------------------


class TestConductorScore:
    """Tests for the conductor score .ly output."""

    def test_conductor_score_has_version_header(self) -> None:
        output = _generate_score()
        assert output.startswith('\\version "2.24.4"')

    def test_conductor_score_has_staff_groups(self) -> None:
        output = _generate_score()
        assert '\\new StaffGroup = "Saxophones"' in output
        assert '\\new StaffGroup = "Trumpets"' in output
        assert '\\new StaffGroup = "Trombones"' in output
        assert '\\new StaffGroup = "Rhythm"' in output

    def test_conductor_score_uses_tabloid_landscape(self) -> None:
        output = _generate_score()
        assert "paper-width = 431.8\\mm" in output
        assert "paper-height = 279.4\\mm" in output

    def test_conductor_score_has_all_instruments(self) -> None:
        output = _generate_score()
        for inst in BIG_BAND.instruments:
            assert f"\\{inst.variable_name}" in output, (
                f"Missing instrument variable reference: {inst.variable_name}"
            )

    def test_conductor_score_concert_pitch(self) -> None:
        output = _generate_score()
        assert "\\transpose" not in output

    def test_conductor_score_has_chord_names(self) -> None:
        output = _generate_score()
        assert "\\new ChordNames" in output

    def test_conductor_score_has_remove_empty_staves(self) -> None:
        output = _generate_score()
        assert "\\RemoveEmptyStaves" in output

    def test_conductor_score_has_book_output_name(self) -> None:
        output = _generate_score()
        assert '\\bookOutputName "score"' in output

    def test_conductor_score_has_midi_block(self) -> None:
        output = _generate_score()
        assert "\\midi" in output

    def test_conductor_score_has_include_definitions(self) -> None:
        output = _generate_score()
        assert '\\include "music-definitions.ly"' in output

    def test_conductor_score_staff_size_14(self) -> None:
        output = _generate_score()
        assert "layout-set-staff-size 14" in output

    def test_conductor_score_piano_grand_staff(self) -> None:
        output = _generate_score()
        assert "PianoStaff" in output

    def test_conductor_score_drums_staff(self) -> None:
        output = _generate_score()
        assert "DrumStaff" in output


# ---------------------------------------------------------------------------
# Conductor score beaming tests
# ---------------------------------------------------------------------------


class TestConductorScoreBeaming:
    """Tests for beaming command injection in conductor scores."""

    def test_default_beam_style_includes_swing_beaming(self) -> None:
        output = _generate_score()
        assert "beamExceptions" in output
        assert "baseMoment" in output
        assert "beatStructure" in output

    def test_explicit_swing_includes_swing_beaming(self) -> None:
        from engrave.rendering.generator import generate_conductor_score

        output = generate_conductor_score(
            preset=BIG_BAND,
            music_var_names=_var_names(),
            beam_style="swing",
        )
        assert "\\set Timing.beamExceptions" in output

    def test_explicit_straight_includes_unset_commands(self) -> None:
        from engrave.rendering.generator import generate_conductor_score

        output = generate_conductor_score(
            preset=BIG_BAND,
            music_var_names=_var_names(),
            beam_style="straight",
        )
        assert "\\unset Timing.beamExceptions" in output
        assert "\\unset Timing.baseMoment" in output
        assert "\\unset Timing.beatStructure" in output

    def test_straight_does_not_include_set_timing(self) -> None:
        from engrave.rendering.generator import generate_conductor_score

        output = generate_conductor_score(
            preset=BIG_BAND,
            music_var_names=_var_names(),
            beam_style="straight",
        )
        assert "\\set Timing" not in output

    def test_beaming_appears_in_score_block(self) -> None:
        output = _generate_score()
        score_idx = output.index("\\score")
        beam_idx = output.index("beamExceptions")
        assert beam_idx > score_idx
