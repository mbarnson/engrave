"""Tests for JSON-to-music21 builder."""

import music21
import pytest

from engrave.musicxml.builder import (
    ARTICULATION_MAP,
    EXPRESSION_MAP,
    build_measure,
    build_note,
    build_part,
    build_score,
)
from engrave.musicxml.models import MeasureData, NoteEvent, SectionNotation


class TestBuildNote:
    """Test build_note: NoteEvent -> music21 Note/Rest."""

    def test_pitched_note(self) -> None:
        event = NoteEvent(pitch="bf4", beat=1.0, duration=1.0)
        note = build_note(event)
        assert isinstance(note, music21.note.Note)
        assert note.pitch.nameWithOctave == "B-4"
        assert note.quarterLength == 1.0

    def test_rest(self) -> None:
        event = NoteEvent(type="rest", beat=1.0, duration=4.0)
        rest = build_note(event)
        assert isinstance(rest, music21.note.Rest)
        assert rest.quarterLength == 4.0

    def test_half_note_duration(self) -> None:
        event = NoteEvent(pitch="c4", beat=1.0, duration=2.0)
        note = build_note(event)
        assert note.quarterLength == 2.0

    def test_eighth_note_duration(self) -> None:
        event = NoteEvent(pitch="d5", beat=2.5, duration=0.5)
        note = build_note(event)
        assert note.quarterLength == 0.5

    def test_accent_articulation(self) -> None:
        event = NoteEvent(pitch="ef5", beat=1.0, duration=1.0, articulations=["accent"])
        note = build_note(event)
        art_types = [type(a) for a in note.articulations]
        assert music21.articulations.Accent in art_types

    def test_staccato_articulation(self) -> None:
        event = NoteEvent(pitch="c4", beat=1.0, duration=1.0, articulations=["staccato"])
        note = build_note(event)
        art_types = [type(a) for a in note.articulations]
        assert music21.articulations.Staccato in art_types

    def test_marcato_articulation(self) -> None:
        event = NoteEvent(pitch="c4", beat=1.0, duration=1.0, articulations=["marcato"])
        note = build_note(event)
        art_types = [type(a) for a in note.articulations]
        assert music21.articulations.StrongAccent in art_types

    def test_multiple_articulations(self) -> None:
        event = NoteEvent(pitch="f4", beat=1.0, duration=1.0, articulations=["accent", "staccato"])
        note = build_note(event)
        art_types = [type(a) for a in note.articulations]
        assert music21.articulations.Accent in art_types
        assert music21.articulations.Staccato in art_types

    def test_dynamic_attached(self) -> None:
        event = NoteEvent(pitch="g4", beat=1.0, duration=1.0, dynamic="f")
        note = build_note(event)
        # Dynamic attached to note's expressions list
        dyn_exprs = [e for e in note.expressions if isinstance(e, music21.dynamics.Dynamic)]
        assert len(dyn_exprs) == 1, "Dynamic 'f' not found on note"
        assert dyn_exprs[0].value == "f"

    def test_fermata_expression(self) -> None:
        event = NoteEvent(pitch="a4", beat=1.0, duration=2.0, expressions=["fermata"])
        note = build_note(event)
        expr_types = [
            type(e) for e in note.expressions if not isinstance(e, music21.dynamics.Dynamic)
        ]
        assert music21.expressions.Fermata in expr_types

    def test_trill_expression(self) -> None:
        event = NoteEvent(pitch="b4", beat=1.0, duration=1.0, expressions=["trill"])
        note = build_note(event)
        expr_types = [
            type(e) for e in note.expressions if not isinstance(e, music21.dynamics.Dynamic)
        ]
        assert music21.expressions.Trill in expr_types

    def test_unknown_articulation_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown articulation names should log a warning, not crash."""
        event = NoteEvent(pitch="c4", beat=1.0, duration=1.0, articulations=["unknown_art"])
        note = build_note(event)
        assert isinstance(note, music21.note.Note)
        assert "unknown_art" in caplog.text

    def test_unknown_expression_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown expression names should log a warning, not crash."""
        event = NoteEvent(pitch="c4", beat=1.0, duration=1.0, expressions=["unknown_expr"])
        note = build_note(event)
        assert isinstance(note, music21.note.Note)
        assert "unknown_expr" in caplog.text

    def test_no_articulations_or_expressions(self) -> None:
        event = NoteEvent(pitch="c4", beat=1.0, duration=1.0)
        note = build_note(event)
        # Filter out any default articulations music21 might add
        assert len(note.expressions) == 0


class TestBuildMeasure:
    """Test build_measure: MeasureData -> music21 Measure."""

    def test_measure_number(self) -> None:
        data = MeasureData(
            number=5,
            notes=[NoteEvent(pitch="c4", beat=1.0, duration=4.0)],
        )
        measure = build_measure(data)
        assert isinstance(measure, music21.stream.Measure)
        assert measure.number == 5

    def test_measure_notes_count(self) -> None:
        data = MeasureData(
            number=1,
            notes=[
                NoteEvent(pitch="c4", beat=1.0, duration=1.0),
                NoteEvent(pitch="d4", beat=2.0, duration=1.0),
                NoteEvent(pitch="e4", beat=3.0, duration=1.0),
                NoteEvent(pitch="f4", beat=4.0, duration=1.0),
            ],
        )
        measure = build_measure(data)
        notes = list(measure.notesAndRests)
        assert len(notes) == 4

    def test_measure_with_rest(self) -> None:
        data = MeasureData(
            number=18,
            notes=[NoteEvent(type="rest", beat=1.0, duration=4.0)],
        )
        measure = build_measure(data)
        notes = list(measure.notesAndRests)
        assert len(notes) == 1
        assert isinstance(notes[0], music21.note.Rest)


class TestBuildPart:
    """Test build_part: instrument sections -> music21 Part."""

    def test_part_name(self) -> None:
        sections = [
            SectionNotation(
                instrument="trumpet_1",
                key="bf_major",
                time_signature="4/4",
                measures=[
                    MeasureData(
                        number=1,
                        notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)],
                    ),
                ],
            ),
        ]
        part = build_part("Trumpet 1", sections, key="bf_major", time_sig="4/4", tempo=120)
        assert isinstance(part, music21.stream.Part)
        assert part.partName == "Trumpet 1"

    def test_part_has_key_signature(self) -> None:
        sections = [
            SectionNotation(
                instrument="trumpet_1",
                key="bf_major",
                time_signature="4/4",
                measures=[
                    MeasureData(
                        number=1,
                        notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)],
                    ),
                ],
            ),
        ]
        part = build_part("Trumpet 1", sections, key="bf_major", time_sig="4/4", tempo=120)
        key_sigs = list(part.recurse().getElementsByClass(music21.key.Key))
        assert len(key_sigs) >= 1

    def test_part_has_time_signature(self) -> None:
        sections = [
            SectionNotation(
                instrument="trumpet_1",
                key="bf_major",
                time_signature="4/4",
                measures=[
                    MeasureData(
                        number=1,
                        notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)],
                    ),
                ],
            ),
        ]
        part = build_part("Trumpet 1", sections, key="bf_major", time_sig="4/4", tempo=120)
        time_sigs = list(part.recurse().getElementsByClass(music21.meter.TimeSignature))
        assert len(time_sigs) >= 1

    def test_part_has_tempo(self) -> None:
        sections = [
            SectionNotation(
                instrument="trumpet_1",
                key="bf_major",
                time_signature="4/4",
                measures=[
                    MeasureData(
                        number=1,
                        notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)],
                    ),
                ],
            ),
        ]
        part = build_part("Trumpet 1", sections, key="bf_major", time_sig="4/4", tempo=120)
        tempos = list(part.recurse().getElementsByClass(music21.tempo.MetronomeMark))
        assert len(tempos) >= 1
        assert tempos[0].number == 120

    def test_part_measure_count(self) -> None:
        sections = [
            SectionNotation(
                instrument="trumpet_1",
                measures=[
                    MeasureData(number=1, notes=[NoteEvent(pitch="c4", beat=1.0, duration=4.0)]),
                    MeasureData(number=2, notes=[NoteEvent(pitch="d4", beat=1.0, duration=4.0)]),
                    MeasureData(number=3, notes=[NoteEvent(pitch="e4", beat=1.0, duration=4.0)]),
                ],
            ),
        ]
        part = build_part("Trumpet 1", sections, key="c_major", time_sig="4/4", tempo=100)
        measures = list(part.getElementsByClass(music21.stream.Measure))
        assert len(measures) == 3


class TestBuildScore:
    """Test build_score: all section JSON -> music21 Score."""

    def _make_section(self, instrument: str, num_measures: int = 2) -> SectionNotation:
        return SectionNotation(
            instrument=instrument,
            key="bf_major",
            time_signature="4/4",
            measures=[
                MeasureData(
                    number=i + 1,
                    notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)],
                )
                for i in range(num_measures)
            ],
        )

    def test_score_type(self) -> None:
        sections = [self._make_section("trumpet_1")]
        score = build_score(
            all_sections=sections,
            instruments={"trumpet_1": "Trumpet 1"},
            key="bf_major",
            time_sig="4/4",
            tempo=120,
        )
        assert isinstance(score, music21.stream.Score)

    def test_score_part_count(self) -> None:
        sections = [
            self._make_section("trumpet_1"),
            self._make_section("alto_sax"),
        ]
        score = build_score(
            all_sections=sections,
            instruments={"trumpet_1": "Trumpet 1", "alto_sax": "Alto Sax"},
            key="bf_major",
            time_sig="4/4",
            tempo=120,
        )
        parts = list(score.parts)
        assert len(parts) == 2

    def test_score_part_names(self) -> None:
        sections = [
            self._make_section("trumpet_1"),
            self._make_section("alto_sax"),
        ]
        score = build_score(
            all_sections=sections,
            instruments={"trumpet_1": "Trumpet 1", "alto_sax": "Alto Sax"},
            key="bf_major",
            time_sig="4/4",
            tempo=120,
        )
        names = [p.partName for p in score.parts]
        assert "Trumpet 1" in names
        assert "Alto Sax" in names

    def test_score_multiple_sections_same_instrument(self) -> None:
        """Multiple sections for the same instrument should merge into one Part."""
        section1 = SectionNotation(
            instrument="trumpet_1",
            key="bf_major",
            time_signature="4/4",
            measures=[
                MeasureData(number=1, notes=[NoteEvent(pitch="bf4", beat=1.0, duration=4.0)]),
                MeasureData(number=2, notes=[NoteEvent(pitch="c5", beat=1.0, duration=4.0)]),
            ],
        )
        section2 = SectionNotation(
            instrument="trumpet_1",
            key="bf_major",
            time_signature="4/4",
            measures=[
                MeasureData(number=3, notes=[NoteEvent(pitch="d5", beat=1.0, duration=4.0)]),
                MeasureData(number=4, notes=[NoteEvent(pitch="ef5", beat=1.0, duration=4.0)]),
            ],
        )
        score = build_score(
            all_sections=[section1, section2],
            instruments={"trumpet_1": "Trumpet 1"},
            key="bf_major",
            time_sig="4/4",
            tempo=120,
        )
        parts = list(score.parts)
        assert len(parts) == 1
        measures = list(parts[0].getElementsByClass(music21.stream.Measure))
        assert len(measures) == 4


class TestArticulationMap:
    """Verify ARTICULATION_MAP covers all specified articulations."""

    @pytest.mark.parametrize(
        "name",
        [
            "accent",
            "marcato",
            "staccato",
            "staccatissimo",
            "tenuto",
            "portato",
            "doit",
            "falloff",
            "scoop",
            "plop",
        ],
    )
    def test_articulation_in_map(self, name: str) -> None:
        assert name in ARTICULATION_MAP
        assert issubclass(ARTICULATION_MAP[name], music21.articulations.Articulation)


class TestExpressionMap:
    """Verify EXPRESSION_MAP covers all specified expressions."""

    @pytest.mark.parametrize(
        "name",
        ["fermata", "trill", "turn", "mordent"],
    )
    def test_expression_in_map(self, name: str) -> None:
        assert name in EXPRESSION_MAP
