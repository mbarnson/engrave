"""Audit log for per-field source resolution tracking.

Records which data source (MIDI, audio, or user hint) was authoritative for
each musical field in the generation prompt.  Phase 6 version is skeletal:
hint_value is always None (hints are unstructured text) and audio_value
requires parsing natural language.  Infrastructure is forward-looking.

Output is structured JSON, machine-readable, queryable via ``jq``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FieldResolution:
    """Resolution record for a single musical field (e.g. key, tempo).

    Attributes:
        field: Name of the musical field (e.g. ``"key"``, ``"tempo"``).
        midi_value: Value from MIDI analysis, or ``None``.
        audio_value: Value from audio description, or ``None``.
        hint_value: Value from user hints, or ``None`` (always None in Phase 6).
        resolved_to: The value that went into the generation prompt.
        source: Which source was authoritative (``"hint"``, ``"audio"``, or ``"midi"``).
    """

    field: str
    midi_value: str | None = None
    audio_value: str | None = None
    hint_value: str | None = None
    resolved_to: str = ""
    source: str = ""


@dataclass
class AuditEntry:
    """Audit record for a single section's field resolutions.

    Attributes:
        section_index: Zero-based section index.
        section_label: Human-readable section label.
        timestamp: ISO 8601 timestamp when the entry was created.
        resolutions: Per-field resolution records.
    """

    section_index: int
    section_label: str
    timestamp: str = ""
    resolutions: list[FieldResolution] = field(default_factory=list)


@dataclass
class AuditLog:
    """Structured audit log for an entire generation run.

    Attributes:
        job_id: Unique identifier for the generation job.
        entries: Per-section audit entries.
    """

    job_id: str = ""
    entries: list[AuditEntry] = field(default_factory=list)

    def add_entry(
        self,
        section_index: int,
        section_label: str,
        resolutions: list[FieldResolution],
    ) -> None:
        """Create a timestamped audit entry and append it.

        Args:
            section_index: Zero-based section index.
            section_label: Human-readable section label.
            resolutions: Per-field resolution records for this section.
        """
        entry = AuditEntry(
            section_index=section_index,
            section_label=section_label,
            timestamp=datetime.now(tz=UTC).isoformat(),
            resolutions=resolutions,
        )
        self.entries.append(entry)

    def write(self, output_dir: Path) -> Path:
        """Write audit log as JSON to the given directory.

        Args:
            output_dir: Directory to write ``audit_log.json`` into.

        Returns:
            Path to the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "audit_log.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Audit log written: %s", path)
        return path
