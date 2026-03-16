"""Unit tests for engrave.midi.analyzer and pipeline LLM key detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from engrave.generation.key_detection import parse_llm_key_response
from engrave.midi.analyzer import MidiAnalysis, analyze_midi

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestParseKeyResponse:
    """Tests for parse_llm_key_response -- LLM output to LilyPond key format."""

    @pytest.mark.parametrize(
        "response,expected",
        [
            ("Bb major", "bes \\major"),
            ("F# minor", "fis \\minor"),
            ("C major", "c \\major"),
            ("Eb minor", "ees \\minor"),
            ("key: Ab major", "aes \\major"),
            ("Key signature: D minor", "d \\minor"),
            ("key = G major", "g \\major"),
            ("The key is Bb major.", "bes \\major"),
            ("bes \\major", "bes \\major"),
            ("A major", "a \\major"),
            ("Db major", "des \\major"),
            ("F minor", "f \\minor"),
            # LilyPond native format (preferred prompt output)
            ("fis \\minor", "fis \\minor"),
            ("ees \\major", "ees \\major"),
            ("g \\major", "g \\major"),
            ("d \\minor", "d \\minor"),
            ("aes \\major", "aes \\major"),
        ],
    )
    def test_valid_responses(self, response: str, expected: str):
        assert parse_llm_key_response(response) == expected

    @pytest.mark.parametrize(
        "response",
        [
            "",
            "I don't know",
            "42",
            "the tempo is 120",
        ],
    )
    def test_invalid_responses(self, response: str):
        assert parse_llm_key_response(response) is None


class TestAnalyzer:
    """Tests for MIDI musical analysis."""

    def test_analyze_extracts_tempo(self):
        """tempo_changes populated correctly from MIDI."""
        analysis = analyze_midi(str(FIXTURES / "simple_type0.mid"))
        assert isinstance(analysis, MidiAnalysis)
        assert len(analysis.tempo_changes) >= 1
        # First tempo should be ~120 BPM (500000 microseconds per beat)
        bpm, _tick = analysis.tempo_changes[0]
        assert 119.0 <= bpm <= 121.0

    def test_analyze_extracts_time_signature(self):
        """time_signatures populated from MIDI."""
        analysis = analyze_midi(str(FIXTURES / "simple_type0.mid"))
        assert len(analysis.time_signatures) >= 1
        num, denom, _tick = analysis.time_signatures[0]
        assert num == 4
        assert denom == 4

    def test_analyze_extracts_instruments(self):
        """instrument list populated from program_change events."""
        analysis = analyze_midi(str(FIXTURES / "simple_type1.mid"))
        assert len(analysis.instruments) >= 1
        # Should detect at least one instrument
        assert any(isinstance(name, str) and len(name) > 0 for name in analysis.instruments)

    def test_analyze_estimates_key(self):
        """key_signature is a valid LilyPond key string."""
        analysis = analyze_midi(str(FIXTURES / "simple_type0.mid"))
        # Should contain a note name and major/minor
        assert isinstance(analysis.key_signature, str)
        assert "\\major" in analysis.key_signature or "\\minor" in analysis.key_signature

    def test_analyze_total_bars(self):
        """total_bars estimated from duration and time sig."""
        analysis = analyze_midi(str(FIXTURES / "simple_type0.mid"))
        # 4 bars in the fixture
        assert analysis.total_bars >= 3  # Allow for rounding

    def test_analyze_ticks_per_beat(self):
        """ticks_per_beat extracted from MIDI."""
        analysis = analyze_midi(str(FIXTURES / "simple_type0.mid"))
        assert analysis.ticks_per_beat == 480

    def test_analyze_no_metadata_file(self):
        """Analysis works on files with minimal metadata (3/4 time, 100 BPM)."""
        analysis = analyze_midi(str(FIXTURES / "no_metadata.mid"))
        assert len(analysis.tempo_changes) >= 1
        bpm, _ = analysis.tempo_changes[0]
        assert 99.0 <= bpm <= 101.0
        # Time signature: 3/4
        assert len(analysis.time_signatures) >= 1
        num, denom, _ = analysis.time_signatures[0]
        assert num == 3
        assert denom == 4
