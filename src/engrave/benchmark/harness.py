"""Closed-loop benchmark harness for pipeline evaluation.

Orchestrates: render corpus MIDI to audio (FluidSynth) -> run audio
through separation+transcription pipeline -> diff output MIDI against
ground truth (mir_eval). Results stored as structured JSON for systematic
model comparison.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from engrave.benchmark.evaluator import diff_midi
from engrave.benchmark.models import AggregateScore, BenchmarkRun, StemMetrics
from engrave.benchmark.renderer import render_midi_to_audio

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol for pipeline integration (decoupled from concrete AudioPipeline)
# ---------------------------------------------------------------------------


@runtime_checkable
class PipelineProtocol(Protocol):
    """Minimal contract for audio pipeline used by the benchmark harness.

    The harness needs ``process(input_path, job_dir)`` returning an object
    with ``stem_results`` -- a list of objects each having ``stem_name``
    and ``midi_path`` attributes.
    """

    def process(self, input_path: Path, job_dir: Path | None = None) -> Any:
        """Process audio through separation + transcription."""
        ...


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark harness execution.

    Attributes:
        soundfont_path: Path to a SoundFont (.sf2) file for FluidSynth
            rendering. If None, uses FluidSynth's default.
        onset_tolerance: Maximum onset time difference (seconds) for
            mir_eval note matching. Default: 0.05s (50ms).
        results_dir: Directory for storing benchmark result JSON files.
    """

    soundfont_path: str | None = None
    onset_tolerance: float = 0.05
    results_dir: str = "data/benchmark_results"


class BenchmarkHarness:
    """Closed-loop benchmark harness orchestrating render -> process -> evaluate.

    For each corpus MIDI file:
    1. Render to audio via FluidSynth (ground truth audio)
    2. Process through the audio pipeline (separation + transcription)
    3. Diff each stem's output MIDI against the source MIDI using mir_eval
    4. Compute per-stem and aggregate metrics
    5. Store results as structured JSON

    Args:
        pipeline: Audio pipeline instance satisfying ``PipelineProtocol``.
        config: Benchmark configuration.
    """

    def __init__(self, pipeline: PipelineProtocol, config: BenchmarkConfig) -> None:
        self.pipeline = pipeline
        self.config = config

    def run_single(
        self,
        midi_path: Path,
        results_dir: Path | None = None,
    ) -> BenchmarkRun:
        """Run a single benchmark evaluation on a MIDI file.

        Args:
            midi_path: Path to the reference (ground truth) MIDI file.
            results_dir: Directory to save results JSON. If None, results
                are returned but not persisted.

        Returns:
            BenchmarkRun with per-stem and aggregate metrics.
        """
        now = datetime.now(tz=UTC)
        run_id = f"bench_{now.strftime('%Y%m%d_%H%M%S')}_{midi_path.stem}"

        logger.info("Starting benchmark run: %s (source: %s)", run_id, midi_path)

        with tempfile.TemporaryDirectory(prefix="engrave_bench_") as tmp_str:
            tmp_dir = Path(tmp_str)

            # 1. Render: MIDI -> WAV via FluidSynth
            ground_truth_wav = tmp_dir / "ground_truth.wav"
            render_midi_to_audio(
                midi_path,
                ground_truth_wav,
                soundfont=self.config.soundfont_path,
            )
            logger.info("Rendered ground truth audio: %s", ground_truth_wav)

            # 2. Process: WAV -> separation -> transcription
            job_dir = tmp_dir / "job"
            job_result = self.pipeline.process(ground_truth_wav, job_dir)

            # 3. Evaluate: diff each stem's MIDI against reference
            stem_metrics_list: list[StemMetrics] = []
            for stem_result in job_result.stem_results:
                stem_midi = Path(stem_result.midi_path)
                if not stem_midi.exists():
                    logger.warning(
                        "Stem MIDI not found for %s: %s",
                        stem_result.stem_name,
                        stem_midi,
                    )
                    stem_metrics_list.append(
                        StemMetrics(
                            stem_name=stem_result.stem_name,
                            precision=0.0,
                            recall=0.0,
                            f1=0.0,
                            avg_overlap=0.0,
                            note_count_ref=0,
                            note_count_est=0,
                        )
                    )
                    continue

                diff_result = diff_midi(
                    midi_path,
                    stem_midi,
                    onset_tolerance=self.config.onset_tolerance,
                )

                # Count notes for metrics
                import pretty_midi

                ref_pm = pretty_midi.PrettyMIDI(str(midi_path))
                est_pm = pretty_midi.PrettyMIDI(str(stem_midi))
                ref_notes = sum(len(inst.notes) for inst in ref_pm.instruments if not inst.is_drum)
                est_notes = sum(len(inst.notes) for inst in est_pm.instruments if not inst.is_drum)

                stem_metrics_list.append(
                    StemMetrics(
                        stem_name=stem_result.stem_name,
                        precision=diff_result.precision,
                        recall=diff_result.recall,
                        f1=diff_result.f1,
                        avg_overlap=diff_result.avg_overlap,
                        note_count_ref=ref_notes,
                        note_count_est=est_notes,
                    )
                )

            # 4. Compute aggregate
            aggregate = _compute_aggregate(stem_metrics_list)

            # 5. Build result
            run = BenchmarkRun(
                run_id=run_id,
                timestamp=now.isoformat(),
                source_midi_path=str(midi_path),
                model_config={},
                stem_metrics=stem_metrics_list,
                aggregate=aggregate,
                pipeline_config={},
            )

            # Save if results_dir provided
            if results_dir is not None:
                saved_path = run.save(results_dir)
                logger.info("Saved benchmark results: %s", saved_path)

        return run

    def run_batch(
        self,
        midi_paths: list[Path],
        results_dir: Path,
    ) -> list[BenchmarkRun]:
        """Run benchmark evaluation on multiple MIDI files.

        Args:
            midi_paths: List of reference MIDI file paths.
            results_dir: Directory to save all result JSON files.

        Returns:
            List of BenchmarkRun results, one per MIDI file.
        """
        results: list[BenchmarkRun] = []
        for midi_path in midi_paths:
            run = self.run_single(midi_path, results_dir=results_dir)
            results.append(run)
        return results

    @staticmethod
    def compare_runs(run_paths: list[Path]) -> str:
        """Load and compare benchmark runs from JSON files.

        Args:
            run_paths: Paths to benchmark result JSON files.

        Returns:
            Formatted comparison table as a string.
        """
        runs = [BenchmarkRun.load(p) for p in run_paths]

        if not runs:
            return "No runs to compare."

        # Build comparison table
        lines: list[str] = []
        lines.append("Benchmark Comparison")
        lines.append("=" * 70)

        # Header
        header = f"{'Run ID':<35} {'F1':>6} {'Prec':>6} {'Rec':>6} {'Stems':>6}"
        lines.append(header)
        lines.append("-" * 70)

        for run in runs:
            agg = run.aggregate
            lines.append(
                f"{run.run_id:<35} {agg.mean_f1:>6.3f} "
                f"{agg.mean_precision:>6.3f} {agg.mean_recall:>6.3f} "
                f"{agg.stem_count:>6}"
            )

        lines.append("-" * 70)

        # Per-stem detail for each run
        for run in runs:
            lines.append(f"\n  {run.run_id}:")
            for sm in run.stem_metrics:
                lines.append(
                    f"    {sm.stem_name:<15} F1={sm.f1:.3f}  "
                    f"P={sm.precision:.3f}  R={sm.recall:.3f}  "
                    f"ref={sm.note_count_ref}  est={sm.note_count_est}"
                )

        return "\n".join(lines)


def _compute_aggregate(stem_metrics: list[StemMetrics]) -> AggregateScore:
    """Compute aggregate score across stem metrics.

    Args:
        stem_metrics: Per-stem evaluation results.

    Returns:
        AggregateScore with mean metrics and worst-stem identification.
    """
    if not stem_metrics:
        return AggregateScore(
            mean_f1=0.0,
            mean_precision=0.0,
            mean_recall=0.0,
            stem_count=0,
            worst_stem="",
            worst_f1=0.0,
        )

    n = len(stem_metrics)
    mean_f1 = sum(sm.f1 for sm in stem_metrics) / n
    mean_precision = sum(sm.precision for sm in stem_metrics) / n
    mean_recall = sum(sm.recall for sm in stem_metrics) / n

    worst = min(stem_metrics, key=lambda sm: sm.f1)

    return AggregateScore(
        mean_f1=mean_f1,
        mean_precision=mean_precision,
        mean_recall=mean_recall,
        stem_count=n,
        worst_stem=worst.stem_name,
        worst_f1=worst.f1,
    )
