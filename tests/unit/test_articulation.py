"""Tests for articulation post-processor (ENSM-03 defaults + ENSM-05 omission).

Covers:
- ENSM-03 Rule 1: Unmarked quarter notes get staccato
- ENSM-03 Rule 2: Unmarked eighth notes stay unmarked (long default)
- ENSM-03 Rule 3: Staccato+accent resolves to accent only (with telemetry)
- ENSM-03 Rule 4: Swing assumed (no-op here; beaming handles it)
- ENSM-05: Section consistency omission when all sounding parts agree
- ENSM-05: Rests excluded from comparison
- ENSM-05: Dynamics never stripped
"""

from __future__ import annotations

from engrave.rendering.articulation import (
    apply_articulation_defaults,
    apply_section_consistency,
    build_beat_map,
)

# ---------------------------------------------------------------------------
# ENSM-03: Token Scanner -- Articulation Defaults
# ---------------------------------------------------------------------------


class TestApplyArticulationDefaults:
    """ENSM-03: apply_articulation_defaults() rules."""

    # Rule 1: Unmarked quarter notes get staccato
    def test_quarter_note_default_staccato(self) -> None:
        result, _ = apply_articulation_defaults("c'4")
        assert result == "c'4-."

    def test_multiple_quarters_get_staccato(self) -> None:
        result, _ = apply_articulation_defaults("c'4 d'4 e'4")
        assert result == "c'4-. d'4-. e'4-."

    def test_dotted_quarter_gets_staccato(self) -> None:
        """Dotted quarter is still quarter-note family."""
        result, _ = apply_articulation_defaults("c'4.")
        assert result == "c'4.-."

    # Rule 2: Unmarked eighth notes stay unmarked
    def test_eighth_note_no_mark(self) -> None:
        result, _ = apply_articulation_defaults("d'8")
        assert result == "d'8"

    def test_multiple_eighths_no_mark(self) -> None:
        result, _ = apply_articulation_defaults("d'8 e'8 f'8")
        assert result == "d'8 e'8 f'8"

    # Rule 3: Staccato + accent resolves to accent only
    def test_staccato_accent_resolution(self) -> None:
        result, telemetry = apply_articulation_defaults("e'4-.->")
        assert result == "e'4->"
        assert len(telemetry) == 1
        assert telemetry[0]["original"] == "-.->", telemetry
        assert telemetry[0]["resolved"] == "->"

    def test_staccato_accent_reverse_order(self) -> None:
        """->-. should also resolve to -> only."""
        result, telemetry = apply_articulation_defaults("e'4->-.")
        assert result == "e'4->"
        assert len(telemetry) == 1

    def test_staccato_accent_telemetry_has_bar_beat(self) -> None:
        _result, telemetry = apply_articulation_defaults("c'4 e'4-.->")
        assert len(telemetry) == 1
        assert "bar" in telemetry[0]
        assert "beat" in telemetry[0]

    # Already-marked notes should not be modified
    def test_already_staccato_no_double(self) -> None:
        result, _ = apply_articulation_defaults("e'4-.")
        assert result == "e'4-."

    def test_already_accent_no_change(self) -> None:
        result, _ = apply_articulation_defaults("f'4->")
        assert result == "f'4->"

    def test_already_tenuto_no_change(self) -> None:
        result, _ = apply_articulation_defaults("g'4--")
        assert result == "g'4--"

    def test_already_marcato_no_change(self) -> None:
        result, _ = apply_articulation_defaults("a'4-^")
        assert result == "a'4-^"

    # Staccato + marcato should NOT resolve (only staccato+accent per spec)
    def test_staccato_marcato_kept(self) -> None:
        """Staccato+marcato is kept as-is (only staccato+accent resolves)."""
        result, telemetry = apply_articulation_defaults("a'4-.-^")
        assert result == "a'4-.-^"
        assert len(telemetry) == 0

    # Rests pass through unchanged
    def test_rest_unchanged(self) -> None:
        result, _ = apply_articulation_defaults("r4")
        assert result == "r4"

    def test_rest_with_duration_unchanged(self) -> None:
        result, _ = apply_articulation_defaults("r8")
        assert result == "r8"

    # Sticky duration tracking
    def test_sticky_duration_quarter(self) -> None:
        """Notes without explicit duration inherit previous duration."""
        result, _ = apply_articulation_defaults("c'4 d' e'")
        assert result == "c'4-. d'-. e'-."

    def test_sticky_duration_eighth(self) -> None:
        result, _ = apply_articulation_defaults("c'8 d' e'")
        assert result == "c'8 d' e'"

    # Half notes and whole notes should NOT get staccato (only quarters)
    def test_half_note_no_staccato(self) -> None:
        result, _ = apply_articulation_defaults("c'2")
        assert result == "c'2"

    def test_whole_note_no_staccato(self) -> None:
        result, _ = apply_articulation_defaults("c'1")
        assert result == "c'1"

    # Accidentals
    def test_sharp_note_quarter_staccato(self) -> None:
        result, _ = apply_articulation_defaults("cis'4")
        assert result == "cis'4-."

    def test_flat_note_quarter_staccato(self) -> None:
        result, _ = apply_articulation_defaults("bes'4")
        assert result == "bes'4-."

    def test_double_sharp_quarter_staccato(self) -> None:
        result, _ = apply_articulation_defaults("cisis'4")
        assert result == "cisis'4-."

    def test_double_flat_quarter_staccato(self) -> None:
        result, _ = apply_articulation_defaults("beses'4")
        assert result == "beses'4-."

    # Mixed content
    def test_mixed_quarter_eighth(self) -> None:
        result, _ = apply_articulation_defaults("c'4 d'8 e'4")
        assert result == "c'4-. d'8 e'4-."

    # Sixteenth notes (not quarter, no staccato)
    def test_sixteenth_no_staccato(self) -> None:
        result, _ = apply_articulation_defaults("c'16")
        assert result == "c'16"

    # Empty input
    def test_empty_string(self) -> None:
        result, telemetry = apply_articulation_defaults("")
        assert result == ""
        assert telemetry == []

    # Octave marks
    def test_various_octave_marks(self) -> None:
        result, _ = apply_articulation_defaults("c''4 d,4 e,,4")
        assert result == "c''4-. d,4-. e,,4-."


# ---------------------------------------------------------------------------
# Beat Map Construction
# ---------------------------------------------------------------------------


class TestBuildBeatMap:
    """build_beat_map helper tests."""

    def test_single_quarter(self) -> None:
        bmap = build_beat_map("c'4")
        assert (1, 1.0) in bmap
        assert bmap[(1, 1.0)].is_rest is False

    def test_four_quarters_fill_bar(self) -> None:
        bmap = build_beat_map("c'4 d'4 e'4 f'4")
        assert (1, 1.0) in bmap
        assert (1, 2.0) in bmap
        assert (1, 3.0) in bmap
        assert (1, 4.0) in bmap

    def test_bar_boundary(self) -> None:
        """Fifth quarter note should be in bar 2."""
        bmap = build_beat_map("c'4 d'4 e'4 f'4 g'4")
        assert (2, 1.0) in bmap

    def test_eighth_notes(self) -> None:
        bmap = build_beat_map("c'8 d'8")
        assert (1, 1.0) in bmap
        assert (1, 1.5) in bmap

    def test_rest_flagged(self) -> None:
        bmap = build_beat_map("r4")
        assert (1, 1.0) in bmap
        assert bmap[(1, 1.0)].is_rest is True

    def test_dotted_quarter_duration(self) -> None:
        """Dotted quarter = 1.5 beats."""
        bmap = build_beat_map("c'4. d'8")
        assert (1, 1.0) in bmap
        # d'8 should be at beat 2.5 (1.0 + 1.5)
        assert (1, 2.5) in bmap

    def test_articulation_captured(self) -> None:
        bmap = build_beat_map("c'4-.")
        assert bmap[(1, 1.0)].articulations == ["-."]

    def test_multiple_articulations(self) -> None:
        bmap = build_beat_map("c'4-.->")
        arts = bmap[(1, 1.0)].articulations
        assert "-." in arts
        assert "->" in arts


# ---------------------------------------------------------------------------
# ENSM-05: Section Consistency Rule (Rhythmic Aligner)
# ---------------------------------------------------------------------------


class TestApplySectionConsistency:
    """ENSM-05: apply_section_consistency() section omission rule."""

    def test_all_parts_same_articulation_stripped(self) -> None:
        """When all sounding parts have same articulation, strip from all."""
        parts = {
            "trumpet_i": "c'4-. d'4-. e'4-. f'4-.",
            "trumpet_ii": "c'4-. d'4-. e'4-. f'4-.",
            "trumpet_iii": "c'4-. d'4-. e'4-. f'4-.",
            "trumpet_iv": "c'4-. d'4-. e'4-. f'4-.",
        }
        result = apply_section_consistency(parts)
        for name in parts:
            assert "-." not in result[name], f"{name} still has staccato"

    def test_different_articulations_kept(self) -> None:
        """When parts differ at a beat, keep all markings."""
        parts = {
            "trumpet_i": "c'4-.",
            "trumpet_ii": "c'4->",
        }
        result = apply_section_consistency(parts)
        assert "-." in result["trumpet_i"]
        assert "->" in result["trumpet_ii"]

    def test_rests_excluded_from_comparison(self) -> None:
        """Resting parts are excluded. Sounding parts' matching articulations are stripped."""
        parts = {
            "trumpet_i": "c'4-.",
            "trumpet_ii": "c'4-.",
            "trumpet_iii": "c'4-.",
            "trumpet_iv": "r4",
        }
        result = apply_section_consistency(parts)
        # Sounding parts (i-iii) agree on staccato, should be stripped
        assert "-." not in result["trumpet_i"]
        assert "-." not in result["trumpet_ii"]
        assert "-." not in result["trumpet_iii"]
        # Rest should remain as-is
        assert result["trumpet_iv"] == "r4"

    def test_dynamics_never_stripped(self) -> None:
        r"""Dynamics (\f, \p etc.) are never stripped even if identical."""
        parts = {
            "trumpet_i": r"c'4\f",
            "trumpet_ii": r"c'4\f",
        }
        result = apply_section_consistency(parts)
        assert r"\f" in result["trumpet_i"]
        assert r"\f" in result["trumpet_ii"]

    def test_mixed_articulation_and_dynamics(self) -> None:
        r"""Staccato stripped but dynamics kept when both are identical."""
        parts = {
            "trumpet_i": r"c'4-.\f",
            "trumpet_ii": r"c'4-.\f",
        }
        result = apply_section_consistency(parts)
        # Staccato stripped
        assert "-." not in result["trumpet_i"]
        # Dynamics kept
        assert r"\f" in result["trumpet_i"]
        assert r"\f" in result["trumpet_ii"]

    def test_single_sounding_part_no_strip(self) -> None:
        """With only one sounding part (others rest), nothing to compare -- keep markings."""
        parts = {
            "trumpet_i": "c'4-.",
            "trumpet_ii": "r4",
            "trumpet_iii": "r4",
        }
        result = apply_section_consistency(parts)
        assert "-." in result["trumpet_i"]

    def test_accent_eligible_for_omission(self) -> None:
        """Accent is in the omission-eligible allowlist."""
        parts = {
            "trombone_i": "c'4->",
            "trombone_ii": "c'4->",
        }
        result = apply_section_consistency(parts)
        assert "->" not in result["trombone_i"]
        assert "->" not in result["trombone_ii"]

    def test_tenuto_eligible_for_omission(self) -> None:
        parts = {
            "trombone_i": "c'4--",
            "trombone_ii": "c'4--",
        }
        result = apply_section_consistency(parts)
        assert "--" not in result["trombone_i"]

    def test_marcato_eligible_for_omission(self) -> None:
        parts = {
            "trombone_i": "c'4-^",
            "trombone_ii": "c'4-^",
        }
        result = apply_section_consistency(parts)
        assert "-^" not in result["trombone_i"]

    def test_multi_bar_consistency(self) -> None:
        """Omission works across multiple bars."""
        parts = {
            "sax_i": "c'4-. d'4-. e'4-. f'4-. g'4-. a'4-. b'4-. c''4-.",
            "sax_ii": "c'4-. d'4-. e'4-. f'4-. g'4-. a'4-. b'4-. c''4-.",
        }
        result = apply_section_consistency(parts)
        assert "-." not in result["sax_i"]
        assert "-." not in result["sax_ii"]

    def test_partial_bar_difference_keeps_all(self) -> None:
        """If one beat differs, all markings at that beat are kept -- but other beats unaffected."""
        parts = {
            "sax_i": "c'4-. d'4->",
            "sax_ii": "c'4-. d'4-.",
        }
        result = apply_section_consistency(parts)
        # Beat 1: both have staccato -> strip
        # Beat 2: differ (accent vs staccato) -> keep both
        # After stripping staccato from beat 1, sax_i has "c'4 d'4->"
        # and sax_ii has "c'4 d'4-."
        assert "->" in result["sax_i"]
        assert "-." in result["sax_ii"]

    def test_custom_time_signature(self) -> None:
        """3/4 time: bar is 3 beats."""
        parts = {
            "trumpet_i": "c'4-. d'4-. e'4-. f'4-.",
            "trumpet_ii": "c'4-. d'4-. e'4-. f'4-.",
        }
        result = apply_section_consistency(parts, time_sig=(3, 4))
        # All should be stripped (all sounding parts agree at every beat)
        assert "-." not in result["trumpet_i"]
