"""Tests for dynamic restatement post-processing.

Covers: restate_dynamics from engrave.rendering.generator.

The dynamic restatement rule: always restate the current dynamic at any
entrance following 2+ bars of rest (ENGR-04).
"""

from __future__ import annotations

from engrave.rendering.generator import restate_dynamics

# ---------------------------------------------------------------------------
# Core restatement tests
# ---------------------------------------------------------------------------


class TestDynamicRestatement:
    """Tests for the restate_dynamics post-processor."""

    def test_dynamic_restated_after_multibar_rest(self) -> None:
        """After 4 bars rest, the dynamic should be restated at the entrance."""
        source = r"c'4\f d' e' f' | R1*4 | g'4 a' b' c''"
        result = restate_dynamics(source)
        # The \f should appear before g'4 (the entrance after the rest)
        assert r"g'4\f" in result or r"\f g'4" in result

    def test_dynamic_restated_after_two_bar_rest(self) -> None:
        """2 bars rest (minimum threshold) should trigger restatement."""
        source = r"c'4\mf d' e' f' | R1*2 | g'4 a' b' c''"
        result = restate_dynamics(source)
        assert r"\mf" in result.split("R1*2")[1]

    def test_no_restatement_after_one_bar_rest(self) -> None:
        """1 bar rest (below threshold) should NOT trigger restatement."""
        source = r"c'4\f d' e' f' | R1 | g'4 a' b' c''"
        result = restate_dynamics(source)
        # Only one \f should exist (the original)
        assert result.count(r"\f") == 1

    def test_tracks_changing_dynamics(self) -> None:
        """After dynamic changes, the LAST active dynamic is restated."""
        source = r"c'4\mf d' e' f' | g'4\ff a' b' c'' | R1*3 | d'4 e' f' g'"
        result = restate_dynamics(source)
        # The restated dynamic should be \ff (the last one before the rest)
        after_rest = result.split("R1*3")[1]
        assert r"\ff" in after_rest

    def test_no_restatement_when_dynamic_already_present(self) -> None:
        """If the entrance already has a dynamic, do not double it."""
        source = r"c'4\f d' e' f' | R1*4 | g'4\pp a' b' c''"
        result = restate_dynamics(source)
        # Should NOT have both \f and \pp at the entrance -- only the original \pp
        after_rest = result.split("R1*4")[1]
        assert after_rest.count(r"\f") == 0
        assert r"\pp" in after_rest

    def test_handles_various_dynamics(self) -> None:
        """Test with a variety of dynamic markings."""
        dynamics = [r"\pp", r"\p", r"\mp", r"\mf", r"\f", r"\ff", r"\sfz", r"\fp"]
        for dyn in dynamics:
            source = f"c'4{dyn} d' e' f' | R1*3 | g'4 a' b' c''"
            result = restate_dynamics(source)
            after_rest = result.split("R1*3")[1]
            # Extract just the dynamic name (e.g. "pp" from "\pp")
            assert dyn in after_rest, f"Dynamic {dyn} not restated after rest"

    def test_no_crash_on_music_without_dynamics(self) -> None:
        """Music with no dynamics at all should return unchanged."""
        source = r"c'4 d' e' f' | R1*4 | g'4 a' b' c''"
        result = restate_dynamics(source)
        assert result == source

    def test_preserves_non_dynamic_content(self) -> None:
        """All non-dynamic content should be preserved exactly."""
        source = r"c'4\f d' e' f' | R1*4 | g'4 a' b' c''"
        result = restate_dynamics(source)
        # Original notes should still be there
        assert "c'4" in result
        assert "d'" in result
        assert "R1*4" in result
        assert "g'4" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDynamicRestatementEdgeCases:
    """Edge case tests for restate_dynamics."""

    def test_multiple_rests_multiple_restatements(self) -> None:
        """Multiple rest sections should each get restatement."""
        source = r"c'4\f d' e' f' | R1*3 | g'4 a' b' c'' | R1*2 | d'4 e' f' g'"
        result = restate_dynamics(source)
        # Both entrances after rests should get \f restated
        parts = result.split("R1*3")
        after_first_rest = parts[1]
        assert r"\f" in after_first_rest.split("R1*2")[0]
        # Second rest section should also restate
        after_second_rest = result.split("R1*2")[1]
        assert r"\f" in after_second_rest

    def test_dynamic_at_very_start(self) -> None:
        """A dynamic at the very start should be tracked for restatement."""
        source = r"\ff c'4 d' e' f' | R1*2 | g'4 a' b' c''"
        result = restate_dynamics(source)
        after_rest = result.split("R1*2")[1]
        assert r"\ff" in after_rest

    def test_empty_string(self) -> None:
        """Empty input should return empty output."""
        assert restate_dynamics("") == ""

    def test_rest_only_no_crash(self) -> None:
        """Input with only rests and no notes should not crash."""
        source = r"R1*8"
        result = restate_dynamics(source)
        assert "R1*8" in result
