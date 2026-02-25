"""Unit tests for LilyPond/JSON disagreement telemetry."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from engrave.musicxml.telemetry import log_disagreement


class TestLogDisagreement:
    """Tests for log_disagreement()."""

    def test_logs_warning_to_logger(self, caplog: logging.LogRecord) -> None:
        """Disagreement is logged at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="engrave.musicxml.telemetry"):
            log_disagreement(
                section_index=2,
                instrument="trumpet_1",
                ly_source="c'4 d' e' f'",
                json_data={"instrument": "trumpet_1", "measures": []},
                reason="Note count mismatch",
            )
        assert any("disagreement" in r.message.lower() for r in caplog.records)
        assert any("trumpet_1" in r.message for r in caplog.records)

    def test_writes_file_when_output_dir_provided(self, tmp_path: Path) -> None:
        """JSON telemetry file is written when output_dir is given."""
        log_disagreement(
            section_index=1,
            instrument="alto_sax",
            ly_source="bf4 c'8",
            json_data={"instrument": "alto_sax", "measures": [{"number": 1, "notes": []}]},
            reason="Missing articulation",
            output_dir=tmp_path,
        )
        telemetry_dir = tmp_path / "telemetry"
        assert telemetry_dir.exists()

        expected_file = telemetry_dir / "disagreement_1_alto_sax.json"
        assert expected_file.exists()

        data = json.loads(expected_file.read_text())
        assert data["section_index"] == 1
        assert data["instrument"] == "alto_sax"
        assert data["reason"] == "Missing articulation"
        assert "timestamp" in data
        assert data["ly_source"] == "bf4 c'8"

    def test_no_crash_when_output_dir_is_none(self) -> None:
        """No file written and no crash when output_dir is None."""
        # Should not raise
        log_disagreement(
            section_index=0,
            instrument="bass",
            ly_source="c4",
            json_data={},
            reason="test",
            output_dir=None,
        )

    def test_creates_telemetry_subdirectory(self, tmp_path: Path) -> None:
        """Telemetry directory is created automatically."""
        out = tmp_path / "deep" / "nested"
        # output_dir itself doesn't need to exist -- telemetry subdir is created
        out.mkdir(parents=True)
        log_disagreement(
            section_index=3,
            instrument="piano",
            ly_source="<c e g>4",
            json_data={"chord": True},
            reason="Chord voicing differs",
            output_dir=out,
        )
        assert (out / "telemetry" / "disagreement_3_piano.json").exists()

    def test_file_contains_all_fields(self, tmp_path: Path) -> None:
        """Written JSON contains all expected fields."""
        json_input = {"instrument": "trombone_1", "key": "bf_major"}
        log_disagreement(
            section_index=5,
            instrument="trombone_1",
            ly_source="bf,4 c8 d ef",
            json_data=json_input,
            reason="Dynamic placement",
            output_dir=tmp_path,
        )
        data = json.loads((tmp_path / "telemetry" / "disagreement_5_trombone_1.json").read_text())
        assert data["section_index"] == 5
        assert data["instrument"] == "trombone_1"
        assert data["ly_source"] == "bf,4 c8 d ef"
        assert data["json_data"] == json_input
        assert data["reason"] == "Dynamic placement"
        assert "timestamp" in data
