"""Unit tests for AudioDescription and SectionDescription Pydantic models."""

from __future__ import annotations

from engrave.audio.description import AudioDescription, SectionDescription


class TestSectionDescriptionDefaults:
    """SectionDescription validates with sensible defaults."""

    def test_section_description_defaults(self) -> None:
        """SectionDescription() produces valid defaults."""
        s = SectionDescription()
        assert s.label == ""
        assert s.start_bar == 1
        assert s.end_bar == 1
        assert s.key is None
        assert s.active_instruments == []
        assert s.texture == ""
        assert s.dynamics == ""
        assert s.notes is None

    def test_section_notes_nullable(self) -> None:
        """notes field accepts None and non-None values."""
        s_none = SectionDescription(notes=None)
        assert s_none.notes is None

        s_text = SectionDescription(notes="drummer on brushes")
        assert s_text.notes == "drummer on brushes"


class TestAudioDescriptionDefaults:
    """AudioDescription validates with sensible defaults."""

    def test_audio_description_defaults(self) -> None:
        """AudioDescription() produces valid defaults."""
        d = AudioDescription()
        assert d.tempo_bpm == 120
        assert d.tempo_variable is False
        assert d.time_signature == "4/4"
        assert d.key == "C major"
        assert d.instruments == []
        assert d.style_tags == []
        assert d.energy_arc == ""
        assert d.sections == []

    def test_no_confidence_scores(self) -> None:
        """AudioDescription has no confidence field (explicitly rejected)."""
        fields = AudioDescription.model_fields
        assert "confidence" not in fields
        assert "confidence_score" not in fields


class TestAudioDescriptionWithSections:
    """AudioDescription with populated sections validates correctly."""

    def test_audio_description_with_sections(self) -> None:
        """Sections list is properly typed and populated."""
        sections = [
            SectionDescription(
                label="intro",
                start_bar=1,
                end_bar=8,
                key="Bb major",
                active_instruments=["piano"],
                texture="solo piano",
                dynamics="mp",
            ),
            SectionDescription(
                label="verse-1",
                start_bar=9,
                end_bar=24,
                active_instruments=["trumpet", "piano", "bass", "drums"],
                texture="walking bass under trumpet melody",
                dynamics="mf",
                notes="sounds like a Basie arrangement",
            ),
        ]
        d = AudioDescription(
            tempo_bpm=142,
            tempo_variable=False,
            time_signature="4/4",
            key="Bb major",
            instruments=["trumpet", "trombone", "alto sax", "piano", "bass", "drums"],
            style_tags=["swing", "big band", "blues"],
            energy_arc="mp -> mf -> f -> ff -> mf",
            sections=sections,
        )
        assert len(d.sections) == 2
        assert d.sections[0].label == "intro"
        assert d.sections[1].notes == "sounds like a Basie arrangement"
        assert d.key == "Bb major"
        assert d.tempo_bpm == 142


class TestJsonSchema:
    """JSON schema generation and validation roundtrip."""

    def test_model_json_schema_produces_valid_schema(self) -> None:
        """model_json_schema() returns a dict with properties and type keys."""
        schema = AudioDescription.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert schema.get("type") == "object"

    def test_model_validate_json_roundtrip(self) -> None:
        """Serialize to JSON and validate back produces identical model."""
        original = AudioDescription(
            tempo_bpm=142,
            key="Bb major",
            instruments=["trumpet", "piano"],
            style_tags=["swing"],
            sections=[
                SectionDescription(
                    label="intro",
                    start_bar=1,
                    end_bar=8,
                    key="Bb major",
                    texture="solo piano",
                )
            ],
        )
        json_str = original.model_dump_json()
        restored = AudioDescription.model_validate_json(json_str)
        assert restored == original

    def test_model_validate_json_lenient_defaults(self) -> None:
        """Validate JSON with only tempo_bpm -- missing fields get defaults."""
        json_str = '{"tempo_bpm": 142}'
        d = AudioDescription.model_validate_json(json_str)
        assert d.tempo_bpm == 142
        assert d.key == "C major"
        assert d.instruments == []
        assert d.sections == []
