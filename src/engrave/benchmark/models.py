"""Data models for benchmark runs, stem metrics, and aggregate scores.

All models support JSON serialization for systematic comparison of
pipeline configurations across benchmark runs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StemMetrics:
    """Per-stem evaluation metrics from mir_eval comparison.

    Attributes:
        stem_name: Name of the separated stem (e.g. "bass", "drums").
        precision: Fraction of estimated notes that match a reference note.
        recall: Fraction of reference notes matched by an estimated note.
        f1: Harmonic mean of precision and recall.
        avg_overlap: Average temporal overlap ratio for matched note pairs.
        note_count_ref: Number of notes in the reference MIDI.
        note_count_est: Number of notes in the estimated (transcribed) MIDI.
    """

    stem_name: str
    precision: float
    recall: float
    f1: float
    avg_overlap: float
    note_count_ref: int
    note_count_est: int


@dataclass
class AggregateScore:
    """Aggregate metrics across all stems in a benchmark run.

    Attributes:
        mean_f1: Mean F1 score across all stems.
        mean_precision: Mean precision across all stems.
        mean_recall: Mean recall across all stems.
        stem_count: Number of stems evaluated.
        worst_stem: Name of the stem with the lowest F1 score.
        worst_f1: F1 score of the worst-performing stem.
    """

    mean_f1: float
    mean_precision: float
    mean_recall: float
    stem_count: int
    worst_stem: str
    worst_f1: float


@dataclass
class BenchmarkRun:
    """Complete benchmark run results with metadata and per-stem metrics.

    Attributes:
        run_id: Unique identifier for this run (timestamp-based).
        timestamp: ISO 8601 timestamp of when the run started.
        source_midi_path: Path to the reference MIDI file used as input.
        model_config: Model configuration used for separation/transcription.
        stem_metrics: Per-stem evaluation results.
        aggregate: Aggregate score across all stems.
        pipeline_config: Full pipeline configuration snapshot.
    """

    run_id: str
    timestamp: str
    source_midi_path: str
    model_config: dict[str, Any] = field(default_factory=dict)
    stem_metrics: list[StemMetrics] = field(default_factory=list)
    aggregate: AggregateScore = field(
        default_factory=lambda: AggregateScore(
            mean_f1=0.0,
            mean_precision=0.0,
            mean_recall=0.0,
            stem_count=0,
            worst_stem="",
            worst_f1=0.0,
        )
    )
    pipeline_config: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str) -> BenchmarkRun:
        """Deserialize from a JSON string.

        Args:
            data: JSON string produced by ``to_json()``.

        Returns:
            Reconstructed BenchmarkRun instance.
        """
        raw = json.loads(data)
        stem_metrics = [StemMetrics(**sm) for sm in raw.pop("stem_metrics", [])]
        aggregate = AggregateScore(**raw.pop("aggregate", {}))
        return cls(
            **raw,
            stem_metrics=stem_metrics,
            aggregate=aggregate,
        )

    def save(self, results_dir: Path) -> Path:
        """Write this run's results to a JSON file.

        Args:
            results_dir: Directory to write the JSON file into.

        Returns:
            Path to the written JSON file.
        """
        results_dir.mkdir(parents=True, exist_ok=True)
        path = results_dir / f"{self.run_id}.json"
        path.write_text(self.to_json())
        return path

    @classmethod
    def load(cls, path: Path) -> BenchmarkRun:
        """Load a BenchmarkRun from a JSON file.

        Args:
            path: Path to a JSON file produced by ``save()``.

        Returns:
            Deserialized BenchmarkRun instance.
        """
        return cls.from_json(path.read_text())
