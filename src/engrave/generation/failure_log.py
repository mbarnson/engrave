"""Structured failure logging for LilyPond compilation failures.

Records machine-readable data for every compilation failure, feeding
the TUNE-02 fine-tuning pipeline. Each failure is stored as a JSON file
with timestamp-based filename.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class FailureRecord(BaseModel):
    """Structured record of a LilyPond compilation failure.

    Contains all context needed to reproduce and analyze the failure:
    the MIDI input, the prompt that was sent, the error output, and
    the coherence state at time of failure.
    """

    timestamp: str  # ISO 8601
    section_index: int
    midi_token_text: str  # MIDI tokens that were in the prompt
    prompt_sent: str  # Full prompt text
    lilypond_error: str  # Compiler error output
    lilypond_source: str  # The failing LilyPond code
    retry_attempts: int
    error_hashes: list[str]  # SHA256 hashes of each attempt's error
    coherence_state: dict  # Serialized CoherenceState at time of failure


def log_failure(
    record: FailureRecord,
    log_dir: str = ".engrave/failures",
) -> Path:
    """Write failure record as JSON file with timestamp-based filename.

    Creates log_dir if it does not exist.

    Args:
        record: The failure record to persist.
        log_dir: Directory to store failure JSON files.

    Returns:
        Path to the written JSON file.
    """
    dir_path = Path(log_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    # Create filename from timestamp (sanitize colons for filesystem)
    safe_ts = record.timestamp.replace(":", "-").replace(".", "-")
    filename = f"failure_{safe_ts}_s{record.section_index}.json"
    file_path = dir_path / filename

    with open(file_path, "w") as f:
        json.dump(record.model_dump(), f, indent=2)

    return file_path


def load_failure_log(
    log_dir: str = ".engrave/failures",
) -> list[FailureRecord]:
    """Load all failure records from the log directory.

    Args:
        log_dir: Directory containing failure JSON files.

    Returns:
        List of FailureRecord objects, sorted by timestamp.
    """
    dir_path = Path(log_dir)
    if not dir_path.is_dir():
        return []

    records: list[FailureRecord] = []
    for json_file in sorted(dir_path.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)
        records.append(FailureRecord(**data))

    return records
