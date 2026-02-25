"""Unit tests for BigBandPreset ensemble data model.

Verifies: ENSM-01 -- Big band ensemble preset with 17 instruments,
correct transpositions, clefs, score order, section assignments.
"""

from __future__ import annotations

import re

import pytest

# ---------- helpers --------------------------------------------------------- #

EXPECTED_ORDER = [
    "Alto Sax 1",
    "Alto Sax 2",
    "Tenor Sax 1",
    "Tenor Sax 2",
    "Baritone Sax",
    "Trumpet 1",
    "Trumpet 2",
    "Trumpet 3",
    "Trumpet 4",
    "Trombone 1",
    "Trombone 2",
    "Trombone 3",
    "Bass Trombone",
    "Piano",
    "Guitar",
    "Bass",
    "Drums",
]

# camelCase pattern: starts lowercase letter, then letters/digits, no spaces
CAMEL_CASE_RE = re.compile(r"^[a-z][a-zA-Z0-9]+$")


# ---------- fixtures -------------------------------------------------------- #


@pytest.fixture()
def preset():
    from engrave.rendering.ensemble import BIG_BAND

    return BIG_BAND


@pytest.fixture()
def instruments(preset):
    return preset.instruments


@pytest.fixture()
def by_name(instruments):
    return {i.name: i for i in instruments}


# ---------- count ----------------------------------------------------------- #


def test_big_band_preset_has_17_instruments(instruments):
    assert len(instruments) == 17


# ---------- score order ----------------------------------------------------- #


def test_score_order_matches_scoring_guide(instruments):
    names = [i.name for i in instruments]
    assert names == EXPECTED_ORDER


def test_score_order_values_are_0_through_16(instruments):
    orders = [i.score_order for i in instruments]
    assert orders == list(range(17))


# ---------- transposition intervals ----------------------------------------- #


@pytest.mark.parametrize(
    "name, expected_from, expected_to",
    [
        ("Alto Sax 1", "c'", "a'"),
        ("Alto Sax 2", "c'", "a'"),
        ("Tenor Sax 1", "c'", "d'"),
        ("Tenor Sax 2", "c'", "d'"),
        ("Baritone Sax", "c'", "a"),
        ("Trumpet 1", "c'", "d'"),
        ("Trumpet 2", "c'", "d'"),
        ("Trumpet 3", "c'", "d'"),
        ("Trumpet 4", "c'", "d'"),
        ("Trombone 1", "c'", "c'"),
        ("Trombone 2", "c'", "c'"),
        ("Trombone 3", "c'", "c'"),
        ("Bass Trombone", "c'", "c'"),
        ("Piano", "c'", "c'"),
        ("Guitar", "c'", "c'"),
        ("Bass", "c'", "c'"),
        ("Drums", "c'", "c'"),
    ],
)
def test_transposition_intervals(by_name, name, expected_from, expected_to):
    inst = by_name[name]
    assert inst.transpose_from == expected_from, (
        f"{name} transpose_from: got {inst.transpose_from!r}, expected {expected_from!r}"
    )
    assert inst.transpose_to == expected_to, (
        f"{name} transpose_to: got {inst.transpose_to!r}, expected {expected_to!r}"
    )


# ---------- section assignments --------------------------------------------- #


@pytest.mark.parametrize(
    "name, expected_section",
    [
        ("Alto Sax 1", "Saxophones"),
        ("Alto Sax 2", "Saxophones"),
        ("Tenor Sax 1", "Saxophones"),
        ("Tenor Sax 2", "Saxophones"),
        ("Baritone Sax", "Saxophones"),
        ("Trumpet 1", "Trumpets"),
        ("Trumpet 2", "Trumpets"),
        ("Trumpet 3", "Trumpets"),
        ("Trumpet 4", "Trumpets"),
        ("Trombone 1", "Trombones"),
        ("Trombone 2", "Trombones"),
        ("Trombone 3", "Trombones"),
        ("Bass Trombone", "Trombones"),
        ("Piano", "Rhythm"),
        ("Guitar", "Rhythm"),
        ("Bass", "Rhythm"),
        ("Drums", "Rhythm"),
    ],
)
def test_section_assignments(by_name, name, expected_section):
    assert by_name[name].section == expected_section


# ---------- staff group types ----------------------------------------------- #


def test_staff_group_types(by_name):
    from engrave.rendering.ensemble import StaffGroupType

    # Bracket sections
    for name in ["Alto Sax 1", "Trumpet 1", "Trombone 1"]:
        assert by_name[name].group_type == StaffGroupType.BRACKET, f"{name} should be BRACKET"

    # Brace for Rhythm
    for name in ["Piano", "Guitar", "Bass", "Drums"]:
        assert by_name[name].group_type == StaffGroupType.BRACE, f"{name} should be BRACE"


# ---------- chord symbols --------------------------------------------------- #


def test_chord_symbol_instruments(by_name):
    chord_instruments = {n for n, i in by_name.items() if i.has_chord_symbols}
    assert chord_instruments == {"Piano", "Guitar", "Bass"}


def test_non_chord_instruments_no_chord_symbols(by_name):
    non_chord = {n for n, i in by_name.items() if not i.has_chord_symbols}
    # 17 total - 3 chord = 14
    assert len(non_chord) == 14


# ---------- clefs ----------------------------------------------------------- #


@pytest.mark.parametrize(
    "name, expected_clef",
    [
        ("Alto Sax 1", "treble"),
        ("Alto Sax 2", "treble"),
        ("Tenor Sax 1", "treble"),
        ("Tenor Sax 2", "treble"),
        ("Baritone Sax", "treble"),
        ("Trumpet 1", "treble"),
        ("Trumpet 2", "treble"),
        ("Trumpet 3", "treble"),
        ("Trumpet 4", "treble"),
        ("Trombone 1", "bass"),
        ("Trombone 2", "bass"),
        ("Trombone 3", "bass"),
        ("Bass Trombone", "bass"),
        ("Piano", "treble"),
        ("Guitar", "treble"),
        ("Bass", "bass"),
        ("Drums", "percussion"),
    ],
)
def test_clefs(by_name, name, expected_clef):
    assert by_name[name].clef == expected_clef, (
        f"{name} clef: got {by_name[name].clef!r}, expected {expected_clef!r}"
    )


# ---------- variable names -------------------------------------------------- #


def test_instrument_variable_names(instruments):
    for inst in instruments:
        assert CAMEL_CASE_RE.match(inst.variable_name), (
            f"{inst.name} variable_name {inst.variable_name!r} is not valid camelCase"
        )
        # No spaces
        assert " " not in inst.variable_name


def test_variable_names_are_unique(instruments):
    names = [i.variable_name for i in instruments]
    assert len(names) == len(set(names)), "Variable names must be unique"


# ---------- is_transposing flag --------------------------------------------- #


def test_transposing_instruments_flagged(by_name):
    transposing = {
        "Alto Sax 1",
        "Alto Sax 2",
        "Tenor Sax 1",
        "Tenor Sax 2",
        "Baritone Sax",
        "Trumpet 1",
        "Trumpet 2",
        "Trumpet 3",
        "Trumpet 4",
    }
    for name, inst in by_name.items():
        if name in transposing:
            assert inst.is_transposing, f"{name} should be transposing"
        else:
            assert not inst.is_transposing, f"{name} should NOT be transposing"


# ---------- is_grand_staff flag --------------------------------------------- #


def test_piano_is_grand_staff(by_name):
    assert by_name["Piano"].is_grand_staff is True


def test_non_piano_not_grand_staff(by_name):
    for name, inst in by_name.items():
        if name != "Piano":
            assert inst.is_grand_staff is False, f"{name} should not be grand staff"


# ---------- frozen dataclasses ---------------------------------------------- #


def test_preset_is_frozen(preset):
    with pytest.raises(AttributeError):
        preset.name = "Jazz Combo"


def test_instrument_is_frozen(instruments):
    with pytest.raises(AttributeError):
        instruments[0].name = "Soprano Sax"


# ---------- preset metadata ------------------------------------------------- #


def test_preset_name(preset):
    assert preset.name == "Big Band"
