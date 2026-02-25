"""Unit tests for CoherenceState model."""

from __future__ import annotations

from engrave.generation.coherence import CoherenceState


class TestDefaultCoherenceState:
    """Test that default values are sensible."""

    def test_default_coherence_state(self):
        state = CoherenceState()
        assert state.section_index == 0
        assert state.total_sections == 1
        assert state.key_signature == "c \\major"
        assert state.time_signature == "4/4"
        assert state.tempo_bpm == 120
        assert state.dynamic_levels == {}
        assert state.articulation_style == ""
        assert state.rhythmic_density == "moderate"
        assert state.voicing_patterns == []
        assert state.open_ties == {}
        assert state.last_bar_summary == ""
        assert state.generated_summary == ""


class TestToPromptText:
    """Test to_prompt_text serialization."""

    def test_to_prompt_text_includes_key_tempo_time(self):
        state = CoherenceState(
            key_signature="g \\major",
            time_signature="3/4",
            tempo_bpm=140,
        )
        text = state.to_prompt_text()
        assert "g \\major" in text
        assert "3/4" in text
        assert "140" in text

    def test_to_prompt_text_skips_empty_fields(self):
        state = CoherenceState()
        text = state.to_prompt_text()
        # Empty dynamics and voicing should not appear
        assert "dynamics" not in text.lower() or "Current dynamics" not in text
        assert "Voicing" not in text

    def test_to_prompt_text_includes_open_ties(self):
        state = CoherenceState(
            open_ties={"trumpet": ["c''", "e''"]},
        )
        text = state.to_prompt_text()
        assert "ties" in text.lower()
        assert "trumpet" in text

    def test_to_prompt_text_includes_summary(self):
        state = CoherenceState(
            generated_summary="Bars 1-8: trumpet melody in C major, piano comping quarter notes",
        )
        text = state.to_prompt_text()
        assert "trumpet melody" in text


class TestUpdateFromSection:
    """Test update_from_section creates updated state."""

    def test_update_from_section_increments_index(self):
        state = CoherenceState(section_index=0, total_sections=5)
        updated = state.update_from_section(
            section_ly="c''4 d'' e'' f''",
            section_midi_text="bar 1: c4(q) d4(q) e4(q) f4(q)",
        )
        assert updated.section_index == 1

    def test_update_from_section_detects_ties(self):
        state = CoherenceState()
        # LilyPond tie notation: note followed by ~
        section_ly = "% trumpet\nc''4 d'' e'' f''~\n"
        updated = state.update_from_section(
            section_ly=section_ly,
            section_midi_text="bar 1: c4(q) d4(q) e4(q) f4(q)",
        )
        # Should detect f'' as an open tie
        assert len(updated.open_ties) > 0
        # At least one track should have tied pitches
        all_ties = []
        for pitches in updated.open_ties.values():
            all_ties.extend(pitches)
        assert any("f" in t for t in all_ties)

    def test_update_from_section_truncates_summary(self):
        state = CoherenceState(
            generated_summary="A" * 1200,  # Already at limit
        )
        updated = state.update_from_section(
            section_ly="c''4 d'' e'' f''",
            section_midi_text="bar 1: c4(q) d4(q) e4(q) f4(q)",
        )
        # Summary should be capped at ~1200 chars
        assert len(updated.generated_summary) <= 1300


class TestInitialFromAnalysis:
    """Test initial_from_analysis class method."""

    def test_initial_from_analysis(self):
        """Create initial state from a mock analysis object."""

        class MockAnalysis:
            key_signature = "d \\minor"
            time_signature = "6/8"
            tempo_bpm = 96
            total_sections = 8

        state = CoherenceState.initial_from_analysis(MockAnalysis())
        assert state.key_signature == "d \\minor"
        assert state.time_signature == "6/8"
        assert state.tempo_bpm == 96
        assert state.total_sections == 8
        assert state.section_index == 0
