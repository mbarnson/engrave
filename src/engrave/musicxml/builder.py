"""JSON-to-music21 builder.

Constructs music21 Note/Rest/Measure/Part/Score hierarchy from
Pydantic notation event models. Bottom-up construction: NoteEvent -> Note ->
Measure -> Part -> Score.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import music21
import music21.articulations as art
import music21.dynamics
import music21.expressions
import music21.key
import music21.meter
import music21.note
import music21.stream
import music21.tempo

from engrave.musicxml.models import MeasureData, NoteEvent, SectionNotation
from engrave.musicxml.pitch_map import ly_key_to_m21, ly_pitch_to_m21

logger = logging.getLogger(__name__)

# Map LilyPond articulation names to music21 articulation classes.
ARTICULATION_MAP: dict[str, type[art.Articulation]] = {
    "accent": art.Accent,
    "marcato": art.StrongAccent,
    "staccato": art.Staccato,
    "staccatissimo": art.Staccatissimo,
    "tenuto": art.Tenuto,
    "portato": art.DetachedLegato,
    "doit": art.Doit,
    "falloff": art.Falloff,
    "scoop": art.Scoop,
    "plop": art.Plop,
}

# Map expression names to music21 expression classes.
EXPRESSION_MAP: dict[str, type[music21.expressions.Expression]] = {
    "fermata": music21.expressions.Fermata,
    "trill": music21.expressions.Trill,
    "turn": music21.expressions.Turn,
    "mordent": music21.expressions.Mordent,
}


def build_note(note_event: NoteEvent) -> music21.note.Note | music21.note.Rest:
    """Convert a single NoteEvent to a music21 Note or Rest.

    Args:
        note_event: Pydantic model for a note/rest event.

    Returns:
        music21 Note or Rest with pitch, duration, articulations, dynamics, expressions.
    """
    if note_event.type == "rest":
        r = music21.note.Rest()
        r.quarterLength = note_event.duration
        return r

    n = music21.note.Note()
    n.pitch = music21.pitch.Pitch(ly_pitch_to_m21(note_event.pitch))
    n.quarterLength = note_event.duration

    # Attach articulations
    for art_name in note_event.articulations or []:
        art_cls = ARTICULATION_MAP.get(art_name)
        if art_cls:
            n.articulations.append(art_cls())
        else:
            logger.warning("Unknown articulation: %s (skipped)", art_name)

    # Attach expressions
    for expr_name in note_event.expressions or []:
        expr_cls = EXPRESSION_MAP.get(expr_name)
        if expr_cls:
            n.expressions.append(expr_cls())
        else:
            logger.warning("Unknown expression: %s (skipped)", expr_name)

    # Attach dynamic as a Dynamic object in the expressions list
    if note_event.dynamic:
        dyn = music21.dynamics.Dynamic(note_event.dynamic)
        n.expressions.append(dyn)

    return n


def build_measure(measure_data: MeasureData) -> music21.stream.Measure:
    """Convert a MeasureData model to a music21 Measure.

    Args:
        measure_data: Pydantic model with measure number and note events.

    Returns:
        music21 Measure with correct number and note/rest elements.
    """
    m = music21.stream.Measure(number=measure_data.number)
    for note_event in measure_data.notes:
        m.append(build_note(note_event))
    return m


def build_part(
    instrument_name: str,
    sections: list[SectionNotation],
    *,
    key: str | None = None,
    time_sig: str | None = None,
    tempo: int | None = None,
) -> music21.stream.Part:
    """Build a music21 Part from one or more section notations for an instrument.

    Key signature, time signature, and tempo are inserted into the first measure.
    Subsequent sections' measures are appended in order.

    Args:
        instrument_name: Display name for the part (e.g. "Trumpet 1").
        sections: List of SectionNotation objects for this instrument.
        key: LilyPond-style key string (e.g. "bf_major"). Used for first measure.
        time_sig: Time signature string (e.g. "4/4"). Used for first measure.
        tempo: Tempo in BPM. Used for first measure.

    Returns:
        music21 Part with all measures from all sections.
    """
    part = music21.stream.Part()
    part.partName = instrument_name

    first_measure_done = False

    for section in sections:
        for measure_data in section.measures:
            m = build_measure(measure_data)

            if not first_measure_done:
                # Insert key signature, time signature, and tempo in the first measure
                if key:
                    m21_key = ly_key_to_m21(key)
                    if m21_key[0].isupper():
                        # Major key
                        m.insert(0, music21.key.Key(m21_key))
                    else:
                        # Minor key
                        m.insert(0, music21.key.Key(m21_key, "minor"))

                if time_sig:
                    m.insert(0, music21.meter.TimeSignature(time_sig))

                if tempo:
                    m.insert(0, music21.tempo.MetronomeMark(number=tempo))

                first_measure_done = True

            part.append(m)

    return part


def build_score(
    *,
    all_sections: list[SectionNotation],
    instruments: dict[str, str],
    key: str | None = None,
    time_sig: str | None = None,
    tempo: int | None = None,
) -> music21.stream.Score:
    """Assemble all section notation data into a complete music21 Score.

    Groups sections by instrument identifier, builds one Part per instrument,
    and returns a Score with all Parts.

    Args:
        all_sections: All SectionNotation objects from all sections of the piece.
        instruments: Mapping of instrument identifier -> display name
            (e.g. {"trumpet_1": "Trumpet 1", "alto_sax": "Alto Sax"}).
        key: Default key for the score (LilyPond-style).
        time_sig: Default time signature for the score.
        tempo: Default tempo in BPM.

    Returns:
        music21 Score with one Part per instrument.
    """
    score = music21.stream.Score()

    # Group sections by instrument
    sections_by_instrument: dict[str, list[SectionNotation]] = defaultdict(list)
    for section in all_sections:
        sections_by_instrument[section.instrument].append(section)

    # Build one Part per instrument, preserving the instruments dict order
    for inst_id, display_name in instruments.items():
        inst_sections = sections_by_instrument.get(inst_id, [])
        if inst_sections:
            part = build_part(display_name, inst_sections, key=key, time_sig=time_sig, tempo=tempo)
            score.insert(0, part)

    return score
