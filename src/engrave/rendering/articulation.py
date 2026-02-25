"""Articulation post-processor for jazz notation conventions.

Two-level transform applied after LLM generation:

1. **Token Scanner** (ENSM-03): ``apply_articulation_defaults()`` walks LilyPond
   tokens and applies Tim Davies jazz articulation defaults -- unmarked quarter
   notes get staccato, unmarked eighths stay long, staccato+accent resolves to
   accent only.

2. **Rhythmic Aligner** (ENSM-05): ``apply_section_consistency()`` compares
   articulations across all parts in a section group at each (bar, beat)
   coordinate and strips redundant marks when all sounding parts agree.

Processing pipeline order::

    LLM output -> apply_articulation_defaults() -> apply_section_consistency() -> final LilyPond
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Duration number -> beat count in 4/4 time.
DURATION_BEATS: dict[int, float] = {
    1: 4.0,
    2: 2.0,
    4: 1.0,
    8: 0.5,
    16: 0.25,
    32: 0.125,
}

#: Articulation shorthand marks eligible for ENSM-05 omission.
OMISSION_ELIGIBLE: frozenset[str] = frozenset({"staccato", "accent", "tenuto", "marcato"})

#: Shorthand -> name mapping for eligible marks.
_SHORTHAND_TO_NAME: dict[str, str] = {
    "-.": "staccato",
    "->": "accent",
    "--": "tenuto",
    "-^": "marcato",
}

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# LilyPond note token: pitch + accidentals + octave marks + optional duration + articulations.
# Captures: (pitch)(duration-with-optional-dot)(articulations)
# Accidentals ordered longest-first to prevent partial matches (eses before es).
_NOTE_TOKEN_RE = re.compile(
    r"([a-g](?:isis|eses|is|es)?[',]*)"  # group 1: pitch
    r"(\d+\.?)?"  # group 2: duration (optional; sticky)
    r"((?:-[.>^_!-])*)"  # group 3: articulation shorthands
)

# Rest token: r followed by optional duration.
_REST_TOKEN_RE = re.compile(
    r"(r)(\d+\.?)?"  # group 1: 'r', group 2: duration (optional)
)

# Dynamic pattern (for the section consistency pass -- never strip these).
_DYNAMIC_RE = re.compile(r"\\(?:ppp|pp|p|mp|mf|f|ff|fff|fp|sfz|sff|sp|spp|rfz)")

# Articulation shorthand pattern for individual match.
_ARTIC_SHORTHAND_RE = re.compile(r"-[.>^_!-]")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BeatEvent:
    """An articulation event at a specific rhythmic position."""

    bar: int
    beat: float  # 1.0, 1.5, 2.0, etc.
    articulations: list[str] = field(default_factory=list)
    is_rest: bool = False


# ---------------------------------------------------------------------------
# Helper: duration to beats
# ---------------------------------------------------------------------------


def _duration_to_beats(dur_num: int, dotted: bool) -> float:
    """Convert LilyPond duration number to beat count."""
    beats = DURATION_BEATS.get(dur_num, 1.0)
    if dotted:
        beats *= 1.5
    return beats


def _parse_duration(dur_str: str | None) -> tuple[int | None, bool]:
    """Parse a duration string like '4', '4.' into (number, dotted)."""
    if not dur_str:
        return None, False
    if dur_str.endswith("."):
        return int(dur_str[:-1]), True
    return int(dur_str), False


def _parse_articulations(artic_str: str) -> list[str]:
    """Parse articulation string into list of individual shorthands."""
    return _ARTIC_SHORTHAND_RE.findall(artic_str)


# ---------------------------------------------------------------------------
# ENSM-03: Token Scanner -- apply_articulation_defaults
# ---------------------------------------------------------------------------


def apply_articulation_defaults(ly_source: str) -> tuple[str, list[dict]]:
    """Apply ENSM-03 jazz articulation defaults to LilyPond source.

    Rules:
    1. Unmarked quarter notes (duration ``4``) get staccato (``-.``)
    2. Unmarked eighth notes (duration ``8``) stay unmarked (long default)
    3. Staccato+accent resolves to accent only; logged as telemetry
    4. Swing assumed unless "Straight 8s" (handled by beaming, not here)

    Parameters
    ----------
    ly_source:
        A single instrument's LilyPond music content.

    Returns
    -------
    tuple[str, list[dict]]
        Modified LilyPond source and list of resolution telemetry records.
    """
    if not ly_source:
        return ly_source, []

    telemetry: list[dict] = []
    result_parts: list[str] = []
    pos = 0
    current_duration: int = 4  # default sticky duration
    current_bar = 1
    current_beat = 1.0
    beats_per_bar = 4.0  # 4/4 time default

    while pos < len(ly_source):
        # Try rest first (before note, since 'r' is not in [a-g])
        rest_match = _REST_TOKEN_RE.match(ly_source, pos)
        if (
            rest_match
            and rest_match.group(0).startswith("r")
            and (pos == 0 or not ly_source[pos - 1].isalpha())
        ):
            dur_str = rest_match.group(2)
            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                beats = _duration_to_beats(dur_num, dotted)
            else:
                beats = _duration_to_beats(current_duration, False)

            result_parts.append(rest_match.group(0))
            pos = rest_match.end()

            # Advance beat position
            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        # Try note token
        note_match = _NOTE_TOKEN_RE.match(ly_source, pos)
        if note_match and note_match.group(1):
            pitch = note_match.group(1)

            # Verify this looks like a real pitch (first char must be a-g)
            if pitch[0] not in "abcdefg":
                result_parts.append(ly_source[pos])
                pos += 1
                continue

            dur_str = note_match.group(2)
            artic_str = note_match.group(3) or ""

            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                effective_duration = dur_num
                effective_dotted = dotted
            else:
                effective_duration = current_duration
                effective_dotted = False

            articulations = _parse_articulations(artic_str)

            # Rule 3: Staccato + accent resolution
            has_staccato = "-." in articulations
            has_accent = "->" in articulations
            new_artic_str = artic_str

            if has_staccato and has_accent:
                # Remove staccato, keep accent
                new_artics = [a for a in articulations if a != "-."]
                new_artic_str = "".join(new_artics)
                telemetry.append(
                    {
                        "bar": current_bar,
                        "beat": current_beat,
                        "original": artic_str,
                        "resolved": new_artic_str,
                    }
                )
            elif not articulations and effective_duration == 4:
                # Rule 1: Unmarked quarter notes get staccato
                new_artic_str = "-."
            # Rule 2: Unmarked eighths stay unmarked (implicit -- no action)
            # Other durations (half, whole, 16th, 32nd) also stay unmarked

            # Rebuild the token
            result_parts.append(pitch)
            if dur_str:
                result_parts.append(dur_str)
            result_parts.append(new_artic_str)

            pos = note_match.end()

            # Advance beat position
            beats = _duration_to_beats(effective_duration, effective_dotted)
            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        # No pattern matched -- copy character as-is
        result_parts.append(ly_source[pos])
        pos += 1

    return "".join(result_parts), telemetry


# ---------------------------------------------------------------------------
# Beat map construction
# ---------------------------------------------------------------------------


def build_beat_map(
    ly_source: str,
    time_sig: tuple[int, int] = (4, 4),
) -> dict[tuple[int, float], BeatEvent]:
    """Parse LilyPond source into (bar, beat) -> BeatEvent mapping.

    Parameters
    ----------
    ly_source:
        A single instrument's LilyPond music content.
    time_sig:
        Time signature as (numerator, denominator). Default 4/4.

    Returns
    -------
    dict[tuple[int, float], BeatEvent]
        Mapping from (bar_number, beat_position) to BeatEvent.
    """
    beats_per_bar = time_sig[0] * (4.0 / time_sig[1])
    beat_map: dict[tuple[int, float], BeatEvent] = {}
    pos = 0
    current_duration: int = 4
    current_bar = 1
    current_beat = 1.0

    while pos < len(ly_source):
        # Try rest
        rest_match = _REST_TOKEN_RE.match(ly_source, pos)
        if (
            rest_match
            and rest_match.group(0).startswith("r")
            and (pos == 0 or not ly_source[pos - 1].isalpha())
        ):
            dur_str = rest_match.group(2)
            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                beats = _duration_to_beats(dur_num, dotted)
            else:
                beats = _duration_to_beats(current_duration, False)

            beat_map[(current_bar, current_beat)] = BeatEvent(
                bar=current_bar,
                beat=current_beat,
                articulations=[],
                is_rest=True,
            )
            pos = rest_match.end()

            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        # Try note
        note_match = _NOTE_TOKEN_RE.match(ly_source, pos)
        if note_match and note_match.group(1):
            pitch = note_match.group(1)
            if pitch[0] not in "abcdefg":
                pos += 1
                continue

            dur_str = note_match.group(2)
            artic_str = note_match.group(3) or ""

            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                effective_duration = dur_num
                effective_dotted = dotted
            else:
                effective_duration = current_duration
                effective_dotted = False

            articulations = _parse_articulations(artic_str)

            beat_map[(current_bar, current_beat)] = BeatEvent(
                bar=current_bar,
                beat=current_beat,
                articulations=articulations,
                is_rest=False,
            )
            pos = note_match.end()

            beats = _duration_to_beats(effective_duration, effective_dotted)
            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        pos += 1

    return beat_map


# ---------------------------------------------------------------------------
# ENSM-05: Rhythmic Aligner -- apply_section_consistency
# ---------------------------------------------------------------------------


def apply_section_consistency(
    part_sources: dict[str, str],
    time_sig: tuple[int, int] = (4, 4),
) -> dict[str, str]:
    """Strip articulations where all sounding parts in a section group agree.

    Parameters
    ----------
    part_sources:
        Dict of ``{variable_name: ly_content}`` for all parts in a section group.
    time_sig:
        Time signature as (numerator, denominator). Default 4/4.

    Returns
    -------
    dict[str, str]
        Modified dict with redundant articulations stripped.
    """
    if len(part_sources) < 2:
        return dict(part_sources)

    # Build beat maps for all parts
    beat_maps: dict[str, dict[tuple[int, float], BeatEvent]] = {}
    for name, source in part_sources.items():
        beat_maps[name] = build_beat_map(source, time_sig)

    # Collect all (bar, beat) coordinates across all parts
    all_coords: set[tuple[int, float]] = set()
    for bmap in beat_maps.values():
        all_coords.update(bmap.keys())

    # Determine which coordinates have articulations to strip
    coords_to_strip: dict[tuple[int, float], set[str]] = {}

    for coord in sorted(all_coords):
        # Collect articulations from sounding parts only
        sounding_articulations: list[list[str]] = []
        sounding_names: list[str] = []

        for name, bmap in beat_maps.items():
            event = bmap.get(coord)
            if event is None:
                continue
            if event.is_rest:
                continue
            sounding_names.append(name)
            sounding_articulations.append(event.articulations)

        # Need at least 2 sounding parts to compare
        if len(sounding_articulations) < 2:
            continue

        # Check if all sounding parts have identical articulations
        first = sorted(sounding_articulations[0])
        all_same = all(sorted(arts) == first for arts in sounding_articulations[1:])

        if not all_same:
            continue

        # Determine which marks are eligible for omission
        eligible_marks: set[str] = set()
        for mark in first:
            mark_name = _SHORTHAND_TO_NAME.get(mark)
            if mark_name and mark_name in OMISSION_ELIGIBLE:
                eligible_marks.add(mark)

        if eligible_marks:
            coords_to_strip[coord] = eligible_marks

    # Apply stripping to each part's source
    result: dict[str, str] = {}
    for name, source in part_sources.items():
        bmap = beat_maps[name]
        result[name] = _strip_articulations_at_coords(source, bmap, coords_to_strip, time_sig)

    return result


def _strip_articulations_at_coords(
    ly_source: str,
    beat_map: dict[tuple[int, float], BeatEvent],
    coords_to_strip: dict[tuple[int, float], set[str]],
    time_sig: tuple[int, int] = (4, 4),
) -> str:
    """Strip specific articulation marks from notes at given (bar, beat) coordinates.

    Re-walks the source to find notes at matching positions, then removes
    the eligible articulation shorthands from those notes.
    """
    if not coords_to_strip:
        return ly_source

    beats_per_bar = time_sig[0] * (4.0 / time_sig[1])
    result_parts: list[str] = []
    pos = 0
    current_duration: int = 4
    current_bar = 1
    current_beat = 1.0

    while pos < len(ly_source):
        # Try rest
        rest_match = _REST_TOKEN_RE.match(ly_source, pos)
        if (
            rest_match
            and rest_match.group(0).startswith("r")
            and (pos == 0 or not ly_source[pos - 1].isalpha())
        ):
            dur_str = rest_match.group(2)
            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                beats = _duration_to_beats(dur_num, dotted)
            else:
                beats = _duration_to_beats(current_duration, False)

            result_parts.append(rest_match.group(0))
            pos = rest_match.end()

            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        # Try note
        note_match = _NOTE_TOKEN_RE.match(ly_source, pos)
        if note_match and note_match.group(1):
            pitch = note_match.group(1)
            if pitch[0] not in "abcdefg":
                result_parts.append(ly_source[pos])
                pos += 1
                continue

            dur_str = note_match.group(2)
            artic_str = note_match.group(3) or ""

            dur_num, dotted = _parse_duration(dur_str)
            if dur_num is not None:
                current_duration = dur_num
                effective_duration = dur_num
                effective_dotted = dotted
            else:
                effective_duration = current_duration
                effective_dotted = False

            coord = (current_bar, current_beat)
            marks_to_strip = coords_to_strip.get(coord, set())

            if marks_to_strip and artic_str:
                # Strip eligible marks
                remaining = []
                for mark in _parse_articulations(artic_str):
                    if mark not in marks_to_strip:
                        remaining.append(mark)
                new_artic = "".join(remaining)
            else:
                new_artic = artic_str

            # Also check for and preserve dynamics that follow articulations
            after_pos = note_match.end()
            dyn_match = _DYNAMIC_RE.match(ly_source, after_pos)
            dyn_str = ""
            if dyn_match:
                dyn_str = dyn_match.group(0)
                after_pos = dyn_match.end()

            result_parts.append(pitch)
            if dur_str:
                result_parts.append(dur_str)
            result_parts.append(new_artic)
            if dyn_str:
                result_parts.append(dyn_str)
                pos = after_pos
            else:
                pos = note_match.end()

            beats = _duration_to_beats(effective_duration, effective_dotted)
            current_beat += beats
            while current_beat > beats_per_bar + 1.0 - 1e-9:
                current_beat -= beats_per_bar
                current_bar += 1

            continue

        # No pattern matched -- copy character as-is
        result_parts.append(ly_source[pos])
        pos += 1

    return "".join(result_parts)
