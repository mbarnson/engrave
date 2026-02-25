"""Section group resolution and style-aware beaming commands.

Provides:
- ``resolve_section_groups`` -- group instruments by section_group field
- ``BeamStyle`` -- enum for swing vs straight beaming
- ``beaming_commands`` -- LilyPond Timing property strings per style
- ``resolve_beam_style`` -- infer beaming style from description/hints
"""

from __future__ import annotations

from enum import Enum

from engrave.rendering.ensemble import InstrumentSpec

# ---------------------------------------------------------------------------
# BeamStyle enum
# ---------------------------------------------------------------------------


class BeamStyle(Enum):
    """Beaming style for LilyPond notation."""

    SWING = "swing"
    STRAIGHT = "straight"


# ---------------------------------------------------------------------------
# Beaming command constants
# ---------------------------------------------------------------------------

SWING_BEAMING = (
    "  \\set Timing.beamExceptions = #'()\n"
    "  \\set Timing.baseMoment = #(ly:make-moment 1/4)\n"
    "  \\set Timing.beatStructure = 1,1,1,1\n"
)

STRAIGHT_BEAMING = (
    "  % Default LilyPond beaming (half-bar grouping in 4/4)\n"
    "  \\unset Timing.beamExceptions\n"
    "  \\unset Timing.baseMoment\n"
    "  \\unset Timing.beatStructure\n"
)


def beaming_commands(beam_style: BeamStyle | str) -> str:
    """Return LilyPond timing commands for the given beaming style.

    Parameters
    ----------
    beam_style:
        A ``BeamStyle`` enum member or string ``"swing"``/``"straight"``.
        Unrecognized values default to swing.

    Returns
    -------
    str
        LilyPond ``\\set Timing`` or ``\\unset Timing`` commands.
    """
    style_value = beam_style.value if isinstance(beam_style, BeamStyle) else str(beam_style).lower()

    if style_value == "straight":
        return STRAIGHT_BEAMING
    # Default to swing for anything unrecognized
    return SWING_BEAMING


# ---------------------------------------------------------------------------
# Section group resolution
# ---------------------------------------------------------------------------


def resolve_section_groups(
    instruments: tuple[InstrumentSpec, ...],
) -> list[list[InstrumentSpec]]:
    """Group instruments by their ``section_group`` field.

    Instruments sharing the same non-None ``section_group`` value are
    collected into a single list.  Instruments with ``section_group=None``
    each become their own single-element group.

    Groups are returned sorted by the minimum ``score_order`` within each
    group.  Instruments within each group are sorted by ``score_order``.

    Parameters
    ----------
    instruments:
        Tuple of instrument specs (typically from a preset).

    Returns
    -------
    list[list[InstrumentSpec]]
        Each inner list is one generation group.
    """
    # Collect grouped instruments
    groups: dict[str, list[InstrumentSpec]] = {}
    ungrouped: list[InstrumentSpec] = []

    for inst in instruments:
        if inst.section_group is None:
            ungrouped.append(inst)
        else:
            groups.setdefault(inst.section_group, []).append(inst)

    # Sort within each named group by score_order
    for group_list in groups.values():
        group_list.sort(key=lambda i: i.score_order)

    # Build result: named groups + ungrouped as individual groups
    result: list[list[InstrumentSpec]] = list(groups.values())
    result.extend([inst] for inst in ungrouped)

    # Sort all groups by the first instrument's score_order
    result.sort(key=lambda g: g[0].score_order)

    return result


# ---------------------------------------------------------------------------
# Beam style resolution
# ---------------------------------------------------------------------------

# Style keywords that indicate straight beaming
_STRAIGHT_KEYWORDS = frozenset(
    {
        "latin",
        "rock",
        "pop",
        "funk",
        "bossa",
        "samba",
        "fusion",
    }
)

# Style keywords that indicate swing beaming
_SWING_KEYWORDS = frozenset(
    {
        "swing",
        "bebop",
        "blues",
        "bop",
        "jazz",
        "ballad",
    }
)


def resolve_beam_style(
    section_description: str | None = None,
    user_hints: str | None = None,
) -> BeamStyle:
    """Infer the appropriate beaming style from description and user hints.

    Parameters
    ----------
    section_description:
        Natural-language style description from audio analysis
        (e.g. ``"medium swing"``).
    user_hints:
        User-provided style hints that take priority over description
        (e.g. ``"latin"``, ``"straight"``).

    Returns
    -------
    BeamStyle
        ``SWING`` or ``STRAIGHT``.  Defaults to ``SWING`` for big band
        when no signal is detected.
    """
    # User hints are authoritative -- check first
    if user_hints is not None:
        hint_lower = user_hints.lower()
        for kw in _STRAIGHT_KEYWORDS:
            if kw in hint_lower:
                return BeamStyle.STRAIGHT
        for kw in _SWING_KEYWORDS:
            if kw in hint_lower:
                return BeamStyle.SWING

    # Fall back to audio description
    if section_description is not None:
        desc_lower = section_description.lower()
        for kw in _STRAIGHT_KEYWORDS:
            if kw in desc_lower:
                return BeamStyle.STRAIGHT
        for kw in _SWING_KEYWORDS:
            if kw in desc_lower:
                return BeamStyle.SWING

    # Default: swing for big band
    return BeamStyle.SWING
