"""Tests for section group resolution from ensemble presets.

Covers: resolve_section_groups from engrave.generation.section_groups (ENSM-02).
"""

from __future__ import annotations

import pytest

from engrave.generation.section_groups import resolve_section_groups
from engrave.rendering.ensemble import BIG_BAND, InstrumentSpec, StaffGroupType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def big_band_groups():
    """Resolved section groups for the standard big band preset."""
    return resolve_section_groups(BIG_BAND.instruments)


# ---------------------------------------------------------------------------
# Group count tests
# ---------------------------------------------------------------------------


class TestGroupCounts:
    """Verify resolve_section_groups produces correct group structure."""

    def test_big_band_returns_7_groups(self, big_band_groups) -> None:
        # 3 section groups (saxes, trumpets, trombones) + 4 individual rhythm
        assert len(big_band_groups) == 7

    def test_saxes_group_has_5_instruments(self, big_band_groups) -> None:
        saxes = [g for g in big_band_groups if len(g) == 5]
        assert len(saxes) == 1
        for inst in saxes[0]:
            assert inst.section_group == "saxes"

    def test_trumpets_group_has_4_instruments(self, big_band_groups) -> None:
        trumpets = [g for g in big_band_groups if g[0].section_group == "trumpets"]
        assert len(trumpets) == 1
        assert len(trumpets[0]) == 4

    def test_trombones_group_has_4_instruments(self, big_band_groups) -> None:
        trombones = [g for g in big_band_groups if g[0].section_group == "trombones"]
        assert len(trombones) == 1
        assert len(trombones[0]) == 4

    def test_rhythm_instruments_each_in_own_group(self, big_band_groups) -> None:
        rhythm_groups = [g for g in big_band_groups if g[0].section_group is None]
        assert len(rhythm_groups) == 4
        for g in rhythm_groups:
            assert len(g) == 1


# ---------------------------------------------------------------------------
# Ordering tests
# ---------------------------------------------------------------------------


class TestGroupOrdering:
    """Verify groups are sorted by score_order."""

    def test_groups_sorted_by_score_order(self, big_band_groups) -> None:
        first_orders = [g[0].score_order for g in big_band_groups]
        assert first_orders == sorted(first_orders)

    def test_saxes_internal_order_preserved(self, big_band_groups) -> None:
        saxes = next(g for g in big_band_groups if g[0].section_group == "saxes")
        orders = [inst.score_order for inst in saxes]
        assert orders == sorted(orders)

    def test_saxes_first_is_alto_sax_1(self, big_band_groups) -> None:
        saxes = next(g for g in big_band_groups if g[0].section_group == "saxes")
        assert saxes[0].name == "Alto Sax 1"

    def test_saxes_last_is_baritone_sax(self, big_band_groups) -> None:
        saxes = next(g for g in big_band_groups if g[0].section_group == "saxes")
        assert saxes[-1].name == "Baritone Sax"

    def test_trumpets_internal_order_preserved(self, big_band_groups) -> None:
        trumpets = next(g for g in big_band_groups if g[0].section_group == "trumpets")
        orders = [inst.score_order for inst in trumpets]
        assert orders == sorted(orders)

    def test_trombones_internal_order_preserved(self, big_band_groups) -> None:
        trombones = next(g for g in big_band_groups if g[0].section_group == "trombones")
        orders = [inst.score_order for inst in trombones]
        assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# Edge case: single-instrument preset
# ---------------------------------------------------------------------------


class TestSingleInstrumentPreset:
    """Test resolve_section_groups with minimal instrument tuples."""

    def test_single_ungrouped_instrument_returns_one_group(self) -> None:
        inst = InstrumentSpec(
            name="Solo Trumpet",
            short_name="S.Tpt.",
            variable_name="soloTrumpet",
            transpose_from="c'",
            transpose_to="d'",
            clef="treble",
            section="Brass",
            group_type=StaffGroupType.BRACKET,
            score_order=0,
        )
        groups = resolve_section_groups((inst,))
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_two_ungrouped_instruments_return_two_groups(self) -> None:
        inst_a = InstrumentSpec(
            name="Trumpet",
            short_name="Tpt.",
            variable_name="trumpet",
            transpose_from="c'",
            transpose_to="d'",
            clef="treble",
            section="Brass",
            group_type=StaffGroupType.BRACKET,
            score_order=0,
        )
        inst_b = InstrumentSpec(
            name="Bass",
            short_name="Bass",
            variable_name="bass",
            transpose_from="c'",
            transpose_to="c'",
            clef="bass",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=1,
        )
        groups = resolve_section_groups((inst_a, inst_b))
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Test edge case of empty instrument tuple."""

    def test_empty_instruments_returns_empty_list(self) -> None:
        groups = resolve_section_groups(())
        assert groups == []
