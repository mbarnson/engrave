"""Tests for beaming command generation and beam style resolution.

Covers: beaming_commands, BeamStyle, resolve_beam_style from
engrave.generation.section_groups (ENGR-05).
"""

from __future__ import annotations

from engrave.generation.section_groups import (
    STRAIGHT_BEAMING,
    SWING_BEAMING,
    BeamStyle,
    beaming_commands,
    resolve_beam_style,
)

# ---------------------------------------------------------------------------
# beaming_commands tests
# ---------------------------------------------------------------------------


class TestBeamingCommands:
    """Tests for LilyPond beaming command output."""

    def test_swing_string_returns_timing_properties(self) -> None:
        result = beaming_commands("swing")
        assert "beamExceptions" in result
        assert "baseMoment" in result
        assert "beatStructure" in result

    def test_swing_uses_set_not_unset(self) -> None:
        result = beaming_commands("swing")
        assert "\\set Timing" in result
        assert "\\unset" not in result

    def test_swing_beat_structure_is_quarter_note(self) -> None:
        result = beaming_commands("swing")
        assert "ly:make-moment 1/4" in result
        assert "beatStructure = 1,1,1,1" in result

    def test_straight_string_returns_unset_commands(self) -> None:
        result = beaming_commands("straight")
        assert "\\unset Timing.beamExceptions" in result
        assert "\\unset Timing.baseMoment" in result
        assert "\\unset Timing.beatStructure" in result

    def test_straight_uses_unset_not_set(self) -> None:
        result = beaming_commands("straight")
        assert "\\set Timing" not in result

    def test_swing_enum_works(self) -> None:
        result = beaming_commands(BeamStyle.SWING)
        assert result == SWING_BEAMING

    def test_straight_enum_works(self) -> None:
        result = beaming_commands(BeamStyle.STRAIGHT)
        assert result == STRAIGHT_BEAMING

    def test_unrecognized_defaults_to_swing(self) -> None:
        result = beaming_commands("unknown_style")
        assert result == SWING_BEAMING

    def test_swing_matches_constant(self) -> None:
        assert beaming_commands("swing") == SWING_BEAMING

    def test_straight_matches_constant(self) -> None:
        assert beaming_commands("straight") == STRAIGHT_BEAMING


# ---------------------------------------------------------------------------
# resolve_beam_style tests
# ---------------------------------------------------------------------------


class TestResolveBeamStyle:
    """Tests for beam style inference from description and hints."""

    def test_default_is_swing(self) -> None:
        assert resolve_beam_style() == BeamStyle.SWING

    def test_no_hints_no_description_returns_swing(self) -> None:
        assert resolve_beam_style(None, None) == BeamStyle.SWING

    def test_swing_description_returns_swing(self) -> None:
        assert resolve_beam_style("medium swing tempo") == BeamStyle.SWING

    def test_latin_hint_returns_straight(self) -> None:
        assert resolve_beam_style(user_hints="latin") == BeamStyle.STRAIGHT

    def test_rock_hint_returns_straight(self) -> None:
        assert resolve_beam_style(user_hints="rock") == BeamStyle.STRAIGHT

    def test_pop_hint_returns_straight(self) -> None:
        assert resolve_beam_style(user_hints="pop") == BeamStyle.STRAIGHT

    def test_funk_hint_returns_straight(self) -> None:
        assert resolve_beam_style(user_hints="funk") == BeamStyle.STRAIGHT

    def test_bossa_hint_returns_straight(self) -> None:
        assert resolve_beam_style(user_hints="bossa nova") == BeamStyle.STRAIGHT

    def test_bebop_hint_returns_swing(self) -> None:
        assert resolve_beam_style(user_hints="bebop") == BeamStyle.SWING

    def test_blues_hint_returns_swing(self) -> None:
        assert resolve_beam_style(user_hints="blues") == BeamStyle.SWING

    def test_user_hints_override_description(self) -> None:
        # Description says swing, but user says latin -- user wins
        result = resolve_beam_style(
            section_description="medium swing",
            user_hints="latin feel",
        )
        assert result == BeamStyle.STRAIGHT

    def test_description_latin_returns_straight(self) -> None:
        assert resolve_beam_style("latin groove") == BeamStyle.STRAIGHT

    def test_case_insensitive_hints(self) -> None:
        assert resolve_beam_style(user_hints="LATIN") == BeamStyle.STRAIGHT

    def test_case_insensitive_description(self) -> None:
        assert resolve_beam_style("SWING feel") == BeamStyle.SWING
