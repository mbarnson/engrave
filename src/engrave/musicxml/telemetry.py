"""LilyPond/JSON disagreement telemetry logging.

Records quality signals when the LilyPond and JSON generation paths
produce different musical content for the same section.  Feeds
TUNE-02 fine-tuning data per CONTEXT.md decision.

Disagreements are always logged to Python logger at WARNING level.
When an ``output_dir`` is provided, a structured JSON file is also
written for offline analysis and training data collection.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def log_disagreement(
    section_index: int,
    instrument: str,
    ly_source: str,
    json_data: dict,
    reason: str,
    output_dir: Path | None = None,
) -> None:
    """Record a LilyPond/JSON disagreement as quality telemetry.

    Parameters
    ----------
    section_index:
        Zero-based index of the section where the disagreement occurred.
    instrument:
        Instrument identifier (e.g. ``"trumpet_1"``).
    ly_source:
        LilyPond source fragment for this instrument/section.
    json_data:
        Parsed JSON notation data for this instrument/section.
    reason:
        Human-readable description of the disagreement.
    output_dir:
        Optional output directory.  When provided, a JSON file is
        written to ``{output_dir}/telemetry/disagreement_{section}_{instrument}.json``.
    """
    logger.warning(
        "LilyPond/JSON disagreement: section=%d instrument=%s reason=%s",
        section_index,
        instrument,
        reason,
    )

    if output_dir is not None:
        telemetry_dir = output_dir / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "section_index": section_index,
            "instrument": instrument,
            "ly_source": ly_source,
            "json_data": json_data,
            "reason": reason,
        }

        filename = f"disagreement_{section_index}_{instrument}.json"
        file_path = telemetry_dir / filename
        try:
            file_path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("Failed to write telemetry file: %s", file_path)
