"""Tests for Pydantic notation event models."""

import pytest
from pydantic import ValidationError

from engrave.musicxml.models import MeasureData, NoteEvent, SectionNotation


class TestNoteEvent:
    """Test NoteEvent validation and construction."""

    def test_valid_pitched_note(self) -> None:
        note = NoteEvent(pitch="bf4", beat=1.0, duration=1.0)
        assert note.pitch == "bf4"
        assert note.beat == 1.0
        assert note.duration == 1.0
        assert note.type is None
        assert note.articulations is None
        assert note.expressions is None
        assert note.dynamic is None

    def test_valid_rest(self) -> None:
        rest = NoteEvent(type="rest", beat=1.0, duration=4.0)
        assert rest.type == "rest"
        assert rest.pitch is None
        assert rest.duration == 4.0

    def test_note_with_articulations(self) -> None:
        note = NoteEvent(
            pitch="d5",
            beat=2.0,
            duration=0.5,
            articulations=["accent", "staccato"],
        )
        assert note.articulations == ["accent", "staccato"]

    def test_note_with_dynamic(self) -> None:
        note = NoteEvent(pitch="ef5", beat=1.0, duration=1.0, dynamic="f")
        assert note.dynamic == "f"

    def test_note_with_expressions(self) -> None:
        note = NoteEvent(pitch="c4", beat=1.0, duration=2.0, expressions=["fermata"])
        assert note.expressions == ["fermata"]

    def test_note_with_all_fields(self) -> None:
        note = NoteEvent(
            pitch="fis5",
            beat=1.0,
            duration=1.0,
            articulations=["marcato"],
            expressions=["trill"],
            dynamic="ff",
        )
        assert note.pitch == "fis5"
        assert note.articulations == ["marcato"]
        assert note.expressions == ["trill"]
        assert note.dynamic == "ff"

    # --- Validation errors ---

    def test_missing_beat_raises(self) -> None:
        with pytest.raises(ValidationError):
            NoteEvent(pitch="c4", duration=1.0)  # type: ignore[call-arg]

    def test_missing_duration_raises(self) -> None:
        with pytest.raises(ValidationError):
            NoteEvent(pitch="c4", beat=1.0)  # type: ignore[call-arg]

    def test_invalid_pitch_format_raises(self) -> None:
        with pytest.raises(ValidationError, match="Invalid LilyPond pitch"):
            NoteEvent(pitch="invalid", beat=1.0, duration=1.0)

    def test_rest_with_pitch_raises(self) -> None:
        """Rest notes must not have a pitch."""
        with pytest.raises(ValidationError, match=r"[Rr]est"):
            NoteEvent(type="rest", pitch="c4", beat=1.0, duration=1.0)

    def test_pitched_note_without_type_is_valid(self) -> None:
        """Pitched notes should not require a type field."""
        note = NoteEvent(pitch="g5", beat=1.0, duration=2.0)
        assert note.type is None

    def test_natural_pitch_valid(self) -> None:
        note = NoteEvent(pitch="c4", beat=1.0, duration=1.0)
        assert note.pitch == "c4"

    def test_sharp_pitch_valid(self) -> None:
        note = NoteEvent(pitch="fis5", beat=1.0, duration=1.0)
        assert note.pitch == "fis5"

    def test_flat_pitch_valid(self) -> None:
        note = NoteEvent(pitch="ees3", beat=1.0, duration=1.0)
        assert note.pitch == "ees3"

    def test_pitch_no_octave_raises(self) -> None:
        with pytest.raises(ValidationError):
            NoteEvent(pitch="bf", beat=1.0, duration=1.0)


class TestMeasureData:
    """Test MeasureData model."""

    def test_valid_measure(self) -> None:
        measure = MeasureData(
            number=1,
            notes=[
                NoteEvent(pitch="c4", beat=1.0, duration=1.0),
                NoteEvent(pitch="d4", beat=2.0, duration=1.0),
            ],
        )
        assert measure.number == 1
        assert len(measure.notes) == 2

    def test_empty_notes_valid(self) -> None:
        measure = MeasureData(number=5, notes=[])
        assert measure.notes == []

    def test_missing_number_raises(self) -> None:
        with pytest.raises(ValidationError):
            MeasureData(notes=[])  # type: ignore[call-arg]

    def test_measure_with_rest(self) -> None:
        measure = MeasureData(
            number=18,
            notes=[NoteEvent(type="rest", beat=1.0, duration=4.0)],
        )
        assert measure.notes[0].type == "rest"


class TestSectionNotation:
    """Test SectionNotation model."""

    def test_valid_section(self) -> None:
        section = SectionNotation(
            instrument="trumpet_1",
            key="bf_major",
            time_signature="4/4",
            measures=[
                MeasureData(
                    number=17,
                    notes=[
                        NoteEvent(
                            pitch="bf4",
                            beat=1.0,
                            duration=1.0,
                            articulations=["marcato"],
                            dynamic="f",
                        ),
                        NoteEvent(pitch="d5", beat=2.0, duration=0.5),
                    ],
                ),
            ],
        )
        assert section.instrument == "trumpet_1"
        assert section.key == "bf_major"
        assert section.time_signature == "4/4"
        assert len(section.measures) == 1

    def test_minimal_section(self) -> None:
        section = SectionNotation(
            instrument="piano",
            measures=[],
        )
        assert section.key is None
        assert section.time_signature is None

    def test_missing_instrument_raises(self) -> None:
        with pytest.raises(ValidationError):
            SectionNotation(measures=[])  # type: ignore[call-arg]

    def test_json_roundtrip(self) -> None:
        """Model can serialize to dict and back."""
        section = SectionNotation(
            instrument="alto_sax",
            key="ef_major",
            time_signature="4/4",
            measures=[
                MeasureData(
                    number=1,
                    notes=[
                        NoteEvent(pitch="ef4", beat=1.0, duration=2.0, dynamic="mf"),
                        NoteEvent(type="rest", beat=3.0, duration=2.0),
                    ],
                ),
            ],
        )
        data = section.model_dump()
        restored = SectionNotation.model_validate(data)
        assert restored == section
