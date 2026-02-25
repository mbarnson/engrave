"""Tests for audit log with per-field source resolution tracking."""

from __future__ import annotations

import json
from pathlib import Path

from engrave.generation.audit import AuditEntry, AuditLog, FieldResolution


class TestFieldResolution:
    """Tests for FieldResolution dataclass."""

    def test_field_resolution_defaults(self):
        """FieldResolution with only field name has correct defaults."""
        fr = FieldResolution("key")
        assert fr.field == "key"
        assert fr.midi_value is None
        assert fr.audio_value is None
        assert fr.hint_value is None
        assert fr.resolved_to == ""
        assert fr.source == ""


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_audit_entry_creation(self):
        """AuditEntry populates section_index, section_label, and resolutions."""
        resolutions = [
            FieldResolution(
                field="key",
                midi_value="C major",
                audio_value="Bb major",
                resolved_to="Bb major",
                source="audio",
            ),
        ]
        entry = AuditEntry(
            section_index=0,
            section_label="intro",
            resolutions=resolutions,
        )
        assert entry.section_index == 0
        assert entry.section_label == "intro"
        assert len(entry.resolutions) == 1
        assert entry.resolutions[0].source == "audio"


class TestAuditLog:
    """Tests for AuditLog dataclass."""

    def test_audit_log_add_entry(self):
        """add_entry creates a timestamped entry and appends it."""
        log = AuditLog(job_id="test-run-1")
        resolutions = [
            FieldResolution(field="tempo", midi_value="120", resolved_to="120", source="midi"),
        ]
        log.add_entry(section_index=0, section_label="intro", resolutions=resolutions)

        assert len(log.entries) == 1
        assert log.entries[0].section_index == 0
        assert log.entries[0].section_label == "intro"
        assert log.entries[0].timestamp != ""  # Should be set

    def test_audit_log_write_json(self, tmp_path: Path):
        """write() produces valid JSON that can be parsed back."""
        log = AuditLog(job_id="test-run-2")
        log.add_entry(
            section_index=0,
            section_label="verse",
            resolutions=[
                FieldResolution(
                    field="key",
                    midi_value="C major",
                    audio_value="Bb major",
                    resolved_to="Bb major",
                    source="audio",
                ),
            ],
        )

        path = log.write(tmp_path)
        assert path.exists()
        assert path.name == "audit_log.json"

        # Parse it back
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["job_id"] == "test-run-2"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["resolutions"][0]["field"] == "key"

    def test_audit_log_empty_write(self, tmp_path: Path):
        """Empty AuditLog writes valid JSON with empty entries list."""
        log = AuditLog()
        path = log.write(tmp_path)
        assert path.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["job_id"] == ""
        assert data["entries"] == []
