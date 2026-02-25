"""Unit tests for structured failure logging."""

from __future__ import annotations

import json
from pathlib import Path

from engrave.generation.failure_log import FailureRecord, load_failure_log, log_failure


class TestLogFailure:
    """Test failure record writing."""

    def test_log_failure_creates_file(self, tmp_path: Path):
        """JSON file should be written to log_dir."""
        record = FailureRecord(
            timestamp="2026-02-24T12:00:00Z",
            section_index=2,
            midi_token_text="bar 1: c4(q)",
            prompt_sent="Generate music for trumpet",
            lilypond_error="syntax error",
            lilypond_source="c''4 d''",
            retry_attempts=3,
            error_hashes=["abc123", "def456"],
            coherence_state={"key_signature": "c \\major"},
        )
        log_dir = str(tmp_path / "failures")
        result = log_failure(record, log_dir=log_dir)
        assert result.exists()
        assert result.suffix == ".json"

    def test_log_failure_creates_dir(self, tmp_path: Path):
        """log_dir should be created if missing."""
        record = FailureRecord(
            timestamp="2026-02-24T12:00:00Z",
            section_index=0,
            midi_token_text="bar 1: c4(q)",
            prompt_sent="Generate music",
            lilypond_error="error",
            lilypond_source="c''4",
            retry_attempts=1,
            error_hashes=["abc"],
            coherence_state={},
        )
        log_dir = str(tmp_path / "nested" / "failures")
        result = log_failure(record, log_dir=log_dir)
        assert Path(log_dir).is_dir()
        assert result.exists()

    def test_log_failure_content_valid(self, tmp_path: Path):
        """File content should deserialize back to a FailureRecord."""
        record = FailureRecord(
            timestamp="2026-02-24T12:00:00Z",
            section_index=3,
            midi_token_text="bar 5: g4(h)",
            prompt_sent="Generate section 3",
            lilypond_error="unmatched brace",
            lilypond_source="g''2 a''~",
            retry_attempts=5,
            error_hashes=["h1", "h2", "h3"],
            coherence_state={"tempo_bpm": 140},
        )
        log_dir = str(tmp_path / "failures")
        result_path = log_failure(record, log_dir=log_dir)

        with open(result_path) as f:
            data = json.load(f)

        loaded = FailureRecord(**data)
        assert loaded.section_index == 3
        assert loaded.retry_attempts == 5
        assert loaded.lilypond_error == "unmatched brace"


class TestLoadFailureLog:
    """Test loading failure records from directory."""

    def test_load_failure_log_reads_all(self, tmp_path: Path):
        """Multiple records should be loaded and returned."""
        log_dir = str(tmp_path / "failures")
        for i in range(3):
            record = FailureRecord(
                timestamp=f"2026-02-24T12:0{i}:00Z",
                section_index=i,
                midi_token_text=f"bar {i}: c4(q)",
                prompt_sent=f"Generate section {i}",
                lilypond_error=f"error {i}",
                lilypond_source=f"c''4 attempt {i}",
                retry_attempts=i + 1,
                error_hashes=[f"hash_{i}"],
                coherence_state={},
            )
            log_failure(record, log_dir=log_dir)

        records = load_failure_log(log_dir=log_dir)
        assert len(records) == 3

    def test_load_failure_log_empty_dir(self, tmp_path: Path):
        """Empty directory should return empty list."""
        log_dir = tmp_path / "empty_failures"
        log_dir.mkdir()
        records = load_failure_log(log_dir=str(log_dir))
        assert records == []


class TestFailureRecordSerialization:
    """Test FailureRecord round-trip serialization."""

    def test_failure_record_serialization(self):
        """FailureRecord should round-trip through JSON."""
        record = FailureRecord(
            timestamp="2026-02-24T15:30:00Z",
            section_index=7,
            midi_token_text="bar 10: e4(q, ff) f4(q)",
            prompt_sent="Generate section 7 with dynamics",
            lilypond_error="unknown escape sequence \\fff",
            lilypond_source="trumpetOne = {\n  e''4\\fff f''\n}",
            retry_attempts=2,
            error_hashes=["aaa111", "bbb222"],
            coherence_state={
                "key_signature": "g \\major",
                "tempo_bpm": 160,
                "dynamic_levels": {"trumpet": "ff"},
            },
        )
        json_str = record.model_dump_json()
        loaded = FailureRecord.model_validate_json(json_str)
        assert loaded.section_index == record.section_index
        assert loaded.error_hashes == record.error_hashes
        assert loaded.coherence_state == record.coherence_state
        assert loaded.lilypond_source == record.lilypond_source
