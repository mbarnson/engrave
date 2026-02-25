"""Unit tests for natural language template rendering of audio descriptions."""

from __future__ import annotations

from engrave.audio.description import AudioDescription, SectionDescription
from engrave.audio.templates import (
    render_full_description,
    render_section_description,
    render_track_summary,
)


class TestRenderTrackSummary:
    """Tests for render_track_summary()."""

    def test_render_track_summary_full(self) -> None:
        """AudioDescription with all fields populated renders a complete summary."""
        desc = AudioDescription(
            tempo_bpm=142,
            tempo_variable=False,
            time_signature="4/4",
            key="Bb major",
            instruments=["trumpet", "trombone", "alto sax", "piano", "bass", "drums"],
            style_tags=["swing", "big band"],
            energy_arc="mp -> mf -> f -> ff -> mf",
        )
        result = render_track_summary(desc)
        assert "Bb major" in result
        assert "142 BPM" in result
        assert "4/4 time" in result
        assert "trumpet" in result
        assert "drums" in result
        assert "mp -> mf -> f -> ff -> mf" in result
        assert "Swing big band" in result

    def test_render_track_summary_minimal(self) -> None:
        """AudioDescription with defaults renders a minimal but valid sentence."""
        desc = AudioDescription()
        result = render_track_summary(desc)
        assert "120 BPM" in result
        assert "4/4 time" in result
        # No instruments or energy with defaults
        assert "Instruments:" not in result
        assert "Energy:" not in result

    def test_render_track_summary_variable_tempo(self) -> None:
        """Variable tempo flag is reflected in the summary."""
        desc = AudioDescription(tempo_bpm=80, tempo_variable=True)
        result = render_track_summary(desc)
        assert "(variable)" in result


class TestRenderSectionDescription:
    """Tests for render_section_description()."""

    def test_render_section_description_full(self) -> None:
        """SectionDescription with all fields renders all fields."""
        section = SectionDescription(
            label="verse-1",
            start_bar=9,
            end_bar=24,
            key="Bb major",
            active_instruments=["trumpet", "piano", "bass", "drums"],
            texture="walking bass under trumpet melody",
            dynamics="mf",
            notes="sounds like a Basie arrangement",
        )
        result = render_section_description(section)
        assert "verse-1" in result
        assert "bars 9-24" in result
        assert "Bb major" in result
        assert "trumpet" in result
        assert "walking bass under trumpet melody" in result
        assert "Dynamics: mf" in result
        assert "Notes: sounds like a Basie arrangement" in result

    def test_render_section_description_skips_empty(self) -> None:
        """SectionDescription with empty fields omits them from output."""
        section = SectionDescription(
            label="intro",
            start_bar=1,
            end_bar=8,
        )
        result = render_section_description(section)
        assert "intro" in result
        assert "bars 1-8" in result
        # Empty fields should not appear
        assert "Key:" not in result
        assert "Active instruments:" not in result
        assert "Texture:" not in result
        assert "Dynamics:" not in result
        assert "Notes:" not in result

    def test_render_section_description_includes_notes(self) -> None:
        """SectionDescription with notes includes the notes field."""
        section = SectionDescription(
            label="bridge",
            start_bar=33,
            end_bar=40,
            notes="drummer on brushes",
        )
        result = render_section_description(section)
        assert "Notes: drummer on brushes" in result

    def test_render_section_description_omits_none_notes(self) -> None:
        """SectionDescription with notes=None does not include Notes:."""
        section = SectionDescription(
            label="chorus",
            start_bar=25,
            end_bar=32,
            notes=None,
        )
        result = render_section_description(section)
        assert "Notes:" not in result


class TestRenderFullDescription:
    """Tests for render_full_description()."""

    def test_render_full_description_combines(self) -> None:
        """AudioDescription with 2 sections renders track summary + both sections."""
        desc = AudioDescription(
            tempo_bpm=142,
            key="Bb major",
            instruments=["trumpet", "piano"],
            style_tags=["swing"],
            sections=[
                SectionDescription(
                    label="intro",
                    start_bar=1,
                    end_bar=8,
                    texture="solo piano",
                    dynamics="mp",
                ),
                SectionDescription(
                    label="verse-1",
                    start_bar=9,
                    end_bar=24,
                    texture="full ensemble",
                    dynamics="mf",
                ),
            ],
        )
        result = render_full_description(desc)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # track summary + 2 sections
        assert "142 BPM" in lines[0]
        assert "intro" in lines[1]
        assert "verse-1" in lines[2]

    def test_render_full_description_empty_sections(self) -> None:
        """AudioDescription with no sections renders only track summary."""
        desc = AudioDescription(tempo_bpm=120, key="C major")
        result = render_full_description(desc)
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert "120 BPM" in lines[0]
