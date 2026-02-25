"""Big band ensemble preset encoding all 17 instruments per SCORING_GUIDE.md.

The BigBandPreset data model drives every downstream rendering decision:
score ordering, transposition, bracketing, chord symbol placement, and
staff sizing.  All music is stored internally in concert pitch; transposition
is applied at render time via LilyPond's ``\\transpose`` command.

Transposition convention
------------------------
``transpose_from`` / ``transpose_to`` use LilyPond absolute pitch names.
``\\transpose <from> <to>`` means "concert pitches written as *from* should
be rendered as *to* in the output".  For example, Bb trumpet uses
``\\transpose c' d'`` -- concert middle-C becomes written D above middle-C.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StaffGroupType(Enum):
    """How instruments are grouped in the conductor score."""

    BRACKET = "bracket"  # Saxes, Trumpets, Trombones
    BRACE = "brace"  # Rhythm section
    GRAND_STAFF = "grand_staff"  # Piano (two staves)


# ---------------------------------------------------------------------------
# InstrumentSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstrumentSpec:
    """Immutable specification for a single instrument in the ensemble.

    Parameters
    ----------
    name : str
        Full display name, e.g. ``"Alto Sax 1"``.
    short_name : str
        Abbreviated name for score system starts, e.g. ``"A.Sx. 1"``.
    variable_name : str
        camelCase identifier used as a LilyPond variable name.
    transpose_from : str
        LilyPond pitch -- the *concert* reference (always ``"c'"``).
    transpose_to : str
        LilyPond pitch -- the *written* result after transposition.
    clef : str
        One of ``"treble"``, ``"bass"``, ``"percussion"``.
    section : str
        Section grouping: ``"Saxophones"``, ``"Trumpets"``,
        ``"Trombones"``, or ``"Rhythm"``.
    group_type : StaffGroupType
        Bracket/brace style for the conductor score.
    score_order : int
        Vertical position (0 = top) in the conductor score.
    has_chord_symbols : bool
        ``True`` for rhythm section instruments that display chord symbols.
    is_transposing : bool
        ``True`` when ``transpose_from != transpose_to``.
    is_grand_staff : bool
        ``True`` only for piano (two-staff ``PianoStaff``).
    section_group : str | None
        Joint generation group name (e.g. ``"saxes"``, ``"trumpets"``,
        ``"trombones"``).  ``None`` means ungrouped (individual generation).
    """

    name: str
    short_name: str
    variable_name: str
    transpose_from: str
    transpose_to: str
    clef: str
    section: str
    group_type: StaffGroupType
    score_order: int
    has_chord_symbols: bool = False
    is_transposing: bool = False
    is_grand_staff: bool = False
    section_group: str | None = None


# ---------------------------------------------------------------------------
# BigBandPreset
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BigBandPreset:
    """Frozen container for a complete ensemble configuration.

    Attributes
    ----------
    instruments : tuple[InstrumentSpec, ...]
        All instruments in score order (index 0 = top of score).
    name : str
        Human-readable preset name, default ``"Big Band"``.
    """

    instruments: tuple[InstrumentSpec, ...]
    name: str = "Big Band"


# ---------------------------------------------------------------------------
# Module-level constant: the standard big band
# ---------------------------------------------------------------------------

BIG_BAND = BigBandPreset(
    instruments=(
        # ── Saxophones (Eb / Bb family, treble clef) ──────────────────
        InstrumentSpec(
            name="Alto Sax 1",
            short_name="A.Sx. 1",
            variable_name="altoSaxOne",
            transpose_from="c'",
            transpose_to="a'",  # Eb: up M6
            clef="treble",
            section="Saxophones",
            group_type=StaffGroupType.BRACKET,
            score_order=0,
            is_transposing=True,
            section_group="saxes",
        ),
        InstrumentSpec(
            name="Alto Sax 2",
            short_name="A.Sx. 2",
            variable_name="altoSaxTwo",
            transpose_from="c'",
            transpose_to="a'",  # Eb: up M6
            clef="treble",
            section="Saxophones",
            group_type=StaffGroupType.BRACKET,
            score_order=1,
            is_transposing=True,
            section_group="saxes",
        ),
        InstrumentSpec(
            name="Tenor Sax 1",
            short_name="T.Sx. 1",
            variable_name="tenorSaxOne",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Saxophones",
            group_type=StaffGroupType.BRACKET,
            score_order=2,
            is_transposing=True,
            section_group="saxes",
        ),
        InstrumentSpec(
            name="Tenor Sax 2",
            short_name="T.Sx. 2",
            variable_name="tenorSaxTwo",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Saxophones",
            group_type=StaffGroupType.BRACKET,
            score_order=3,
            is_transposing=True,
            section_group="saxes",
        ),
        InstrumentSpec(
            name="Baritone Sax",
            short_name="B.Sx.",
            variable_name="baritoneSax",
            transpose_from="c'",
            transpose_to="a",  # Eb: octave lower than alto (A below middle C)
            clef="treble",
            section="Saxophones",
            group_type=StaffGroupType.BRACKET,
            score_order=4,
            is_transposing=True,
            section_group="saxes",
        ),
        # ── Trumpets (Bb, treble clef) ────────────────────────────────
        InstrumentSpec(
            name="Trumpet 1",
            short_name="Tpt. 1",
            variable_name="trumpetOne",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Trumpets",
            group_type=StaffGroupType.BRACKET,
            score_order=5,
            is_transposing=True,
            section_group="trumpets",
        ),
        InstrumentSpec(
            name="Trumpet 2",
            short_name="Tpt. 2",
            variable_name="trumpetTwo",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Trumpets",
            group_type=StaffGroupType.BRACKET,
            score_order=6,
            is_transposing=True,
            section_group="trumpets",
        ),
        InstrumentSpec(
            name="Trumpet 3",
            short_name="Tpt. 3",
            variable_name="trumpetThree",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Trumpets",
            group_type=StaffGroupType.BRACKET,
            score_order=7,
            is_transposing=True,
            section_group="trumpets",
        ),
        InstrumentSpec(
            name="Trumpet 4",
            short_name="Tpt. 4",
            variable_name="trumpetFour",
            transpose_from="c'",
            transpose_to="d'",  # Bb: up M2
            clef="treble",
            section="Trumpets",
            group_type=StaffGroupType.BRACKET,
            score_order=8,
            is_transposing=True,
            section_group="trumpets",
        ),
        # ── Trombones (C, bass clef) ──────────────────────────────────
        InstrumentSpec(
            name="Trombone 1",
            short_name="Tbn. 1",
            variable_name="tromboneOne",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="bass",
            section="Trombones",
            group_type=StaffGroupType.BRACKET,
            score_order=9,
            section_group="trombones",
        ),
        InstrumentSpec(
            name="Trombone 2",
            short_name="Tbn. 2",
            variable_name="tromboneTwo",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="bass",
            section="Trombones",
            group_type=StaffGroupType.BRACKET,
            score_order=10,
            section_group="trombones",
        ),
        InstrumentSpec(
            name="Trombone 3",
            short_name="Tbn. 3",
            variable_name="tromboneThree",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="bass",
            section="Trombones",
            group_type=StaffGroupType.BRACKET,
            score_order=11,
            section_group="trombones",
        ),
        InstrumentSpec(
            name="Bass Trombone",
            short_name="B.Tbn.",
            variable_name="bassTrombone",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="bass",
            section="Trombones",
            group_type=StaffGroupType.BRACKET,
            score_order=12,
            section_group="trombones",
        ),
        # ── Rhythm Section (C, various clefs) ─────────────────────────
        InstrumentSpec(
            name="Piano",
            short_name="Pno.",
            variable_name="piano",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="treble",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=13,
            has_chord_symbols=True,
            is_grand_staff=True,
        ),
        InstrumentSpec(
            name="Guitar",
            short_name="Gtr.",
            variable_name="guitar",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch
            clef="treble",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=14,
            has_chord_symbols=True,
        ),
        InstrumentSpec(
            name="Bass",
            short_name="Bass",
            variable_name="bass",
            transpose_from="c'",
            transpose_to="c'",  # Concert pitch (sounds 8vb)
            clef="bass",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=15,
            has_chord_symbols=True,
        ),
        InstrumentSpec(
            name="Drums",
            short_name="Dr.",
            variable_name="drums",
            transpose_from="c'",
            transpose_to="c'",  # Non-pitched
            clef="percussion",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=16,
        ),
    ),
)
