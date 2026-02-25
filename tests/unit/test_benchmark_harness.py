"""Unit tests for benchmark harness orchestration.

All pipeline stages (render, process, diff) are mocked to test
orchestration logic without requiring FluidSynth, audio-separator,
or basic_pitch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pretty_midi
import pytest

from engrave.benchmark.evaluator import MidiDiffResult
from engrave.benchmark.harness import BenchmarkConfig, BenchmarkHarness, _compute_aggregate
from engrave.benchmark.models import AggregateScore, BenchmarkRun, StemMetrics

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeStemResult:
    """Minimal stem result matching the pipeline's StemResult interface."""

    stem_name: str
    midi_path: Path
    wav_path: Path


@dataclass
class FakeJobResult:
    """Minimal job result matching the pipeline's JobResult interface."""

    job_dir: Path
    stem_results: list[FakeStemResult]


def _create_simple_midi(path: Path) -> Path:
    """Create a simple MIDI file with a few notes."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0)
    for pitch, start in [(60, 0.0), (62, 0.5), (64, 1.0), (65, 1.5)]:
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=start, end=start + 0.5)
        )
    pm.instruments.append(instrument)
    pm.write(str(path))
    return path


@pytest.fixture
def bench_config() -> BenchmarkConfig:
    """Default benchmark configuration for tests."""
    return BenchmarkConfig(
        soundfont_path=None,
        onset_tolerance=0.05,
        results_dir="test_results",
    )


@pytest.fixture
def reference_midi(tmp_path: Path) -> Path:
    """Create a reference MIDI file."""
    return _create_simple_midi(tmp_path / "reference.mid")


@pytest.fixture
def mock_pipeline(tmp_path: Path) -> MagicMock:
    """Create a mock pipeline that returns fake stem results with real MIDI files."""
    pipeline = MagicMock()

    def fake_process(input_path: Path, job_dir: Path | None = None) -> FakeJobResult:
        # Create fake stem MIDI files
        stems = []
        for stem_name in ["bass", "drums", "vocals"]:
            midi_path = tmp_path / f"{stem_name}.mid"
            _create_simple_midi(midi_path)
            wav_path = tmp_path / f"{stem_name}.wav"
            wav_path.write_bytes(b"fake-wav")
            stems.append(
                FakeStemResult(stem_name=stem_name, midi_path=midi_path, wav_path=wav_path)
            )

        return FakeJobResult(job_dir=job_dir or tmp_path / "job", stem_results=stems)

    pipeline.process.side_effect = fake_process
    return pipeline


# ---------------------------------------------------------------------------
# Harness orchestration tests
# ---------------------------------------------------------------------------


class TestBenchmarkHarnessRunSingle:
    """Tests for BenchmarkHarness.run_single()."""

    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_calls_render_with_correct_paths(
        self,
        mock_render: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
    ) -> None:
        """Harness calls render_midi_to_audio with the reference MIDI."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)

        harness.run_single(reference_midi)

        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args.args[0] == reference_midi
        assert "ground_truth.wav" in str(call_args.args[1])

    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_calls_pipeline_process_with_rendered_audio(
        self,
        mock_render: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
    ) -> None:
        """Harness passes the rendered WAV to pipeline.process()."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)

        harness.run_single(reference_midi)

        mock_pipeline.process.assert_called_once()
        call_args = mock_pipeline.process.call_args
        # First arg is the ground_truth.wav path inside the temp dir
        assert call_args.args[0].name == "ground_truth.wav"

    @patch("engrave.benchmark.harness.diff_midi")
    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_calls_diff_midi_for_each_stem(
        self,
        mock_render: MagicMock,
        mock_diff: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
    ) -> None:
        """Harness calls diff_midi once per stem result."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        mock_diff.return_value = MidiDiffResult(precision=0.8, recall=0.7, f1=0.75, avg_overlap=0.6)
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)

        run = harness.run_single(reference_midi)

        # Pipeline returns 3 stems (bass, drums, vocals)
        assert mock_diff.call_count == 3
        assert len(run.stem_metrics) == 3

    @patch("engrave.benchmark.harness.diff_midi")
    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_benchmark_run_has_correct_metrics(
        self,
        mock_render: MagicMock,
        mock_diff: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
    ) -> None:
        """BenchmarkRun contains correct per-stem metrics from diff results."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        mock_diff.return_value = MidiDiffResult(precision=0.9, recall=0.8, f1=0.85, avg_overlap=0.7)
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)

        run = harness.run_single(reference_midi)

        assert isinstance(run, BenchmarkRun)
        for sm in run.stem_metrics:
            assert sm.precision == 0.9
            assert sm.recall == 0.8
            assert sm.f1 == 0.85

    @patch("engrave.benchmark.harness.diff_midi")
    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_saves_json_when_results_dir_provided(
        self,
        mock_render: MagicMock,
        mock_diff: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
        tmp_path: Path,
    ) -> None:
        """Results are saved to JSON when results_dir is provided."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        mock_diff.return_value = MidiDiffResult(precision=0.8, recall=0.7, f1=0.75, avg_overlap=0.6)
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)
        results_dir = tmp_path / "results"

        run = harness.run_single(reference_midi, results_dir=results_dir)

        # Check JSON file was created
        json_files = list(results_dir.glob("*.json"))
        assert len(json_files) == 1
        assert run.run_id in json_files[0].name

        # Verify JSON content is valid
        data = json.loads(json_files[0].read_text())
        assert data["run_id"] == run.run_id
        assert len(data["stem_metrics"]) == 3

    @patch("engrave.benchmark.harness.diff_midi")
    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_no_json_saved_without_results_dir(
        self,
        mock_render: MagicMock,
        mock_diff: MagicMock,
        reference_midi: Path,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
        tmp_path: Path,
    ) -> None:
        """No JSON is saved when results_dir is not provided."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        mock_diff.return_value = MidiDiffResult(precision=0.8, recall=0.7, f1=0.75, avg_overlap=0.6)
        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)

        harness.run_single(reference_midi)

        # No JSON files should be in tmp_path/results
        results_dir = tmp_path / "results"
        if results_dir.exists():
            assert len(list(results_dir.glob("*.json"))) == 0


class TestBenchmarkHarnessRunBatch:
    """Tests for BenchmarkHarness.run_batch()."""

    @patch("engrave.benchmark.harness.diff_midi")
    @patch("engrave.benchmark.harness.render_midi_to_audio")
    def test_runs_once_per_midi_path(
        self,
        mock_render: MagicMock,
        mock_diff: MagicMock,
        mock_pipeline: MagicMock,
        bench_config: BenchmarkConfig,
        tmp_path: Path,
    ) -> None:
        """Batch runs run_single once for each MIDI path."""
        mock_render.return_value = Path("/tmp/ground_truth.wav")
        mock_diff.return_value = MidiDiffResult(precision=0.8, recall=0.7, f1=0.75, avg_overlap=0.6)

        midi_paths = []
        for i in range(3):
            midi_path = _create_simple_midi(tmp_path / f"midi_{i}.mid")
            midi_paths.append(midi_path)

        harness = BenchmarkHarness(pipeline=mock_pipeline, config=bench_config)
        results_dir = tmp_path / "batch_results"

        runs = harness.run_batch(midi_paths, results_dir)

        assert len(runs) == 3
        # Each run processed 3 stems, so 9 total diff calls
        assert mock_diff.call_count == 9
        # JSON files saved for each run
        json_files = list(results_dir.glob("*.json"))
        assert len(json_files) == 3


class TestBenchmarkHarnessCompareRuns:
    """Tests for BenchmarkHarness.compare_runs()."""

    def test_compare_two_runs(self, tmp_path: Path) -> None:
        """Compare two benchmark runs produces formatted output."""
        # Create two benchmark result files
        for i, f1_val in enumerate([0.85, 0.72]):
            run = BenchmarkRun(
                run_id=f"run_{i}",
                timestamp="2026-01-01T00:00:00Z",
                source_midi_path=f"/test/midi_{i}.mid",
                stem_metrics=[
                    StemMetrics(
                        stem_name="bass",
                        precision=f1_val + 0.05,
                        recall=f1_val - 0.05,
                        f1=f1_val,
                        avg_overlap=f1_val - 0.1,
                        note_count_ref=100,
                        note_count_est=95,
                    ),
                ],
                aggregate=AggregateScore(
                    mean_f1=f1_val,
                    mean_precision=f1_val + 0.05,
                    mean_recall=f1_val - 0.05,
                    stem_count=1,
                    worst_stem="bass",
                    worst_f1=f1_val,
                ),
            )
            run.save(tmp_path)

        json_files = sorted(tmp_path.glob("*.json"))
        output = BenchmarkHarness.compare_runs(json_files)

        assert "Benchmark Comparison" in output
        assert "run_0" in output
        assert "run_1" in output
        assert "bass" in output

    def test_compare_empty_list(self) -> None:
        """Compare with empty list returns 'No runs to compare.'"""
        output = BenchmarkHarness.compare_runs([])
        assert output == "No runs to compare."


# ---------------------------------------------------------------------------
# Data model serialization tests
# ---------------------------------------------------------------------------


class TestBenchmarkRunSerialization:
    """Tests for BenchmarkRun JSON round-trip serialization."""

    def test_to_json_from_json_round_trip(self) -> None:
        """BenchmarkRun serializes to JSON and deserializes back correctly."""
        original = BenchmarkRun(
            run_id="test_run_001",
            timestamp="2026-01-01T00:00:00Z",
            source_midi_path="/path/to/test.mid",
            model_config={"separation": "htdemucs_ft"},
            stem_metrics=[
                StemMetrics(
                    stem_name="bass",
                    precision=0.9,
                    recall=0.85,
                    f1=0.875,
                    avg_overlap=0.8,
                    note_count_ref=100,
                    note_count_est=95,
                ),
                StemMetrics(
                    stem_name="vocals",
                    precision=0.7,
                    recall=0.6,
                    f1=0.65,
                    avg_overlap=0.55,
                    note_count_ref=200,
                    note_count_est=180,
                ),
            ],
            aggregate=AggregateScore(
                mean_f1=0.7625,
                mean_precision=0.8,
                mean_recall=0.725,
                stem_count=2,
                worst_stem="vocals",
                worst_f1=0.65,
            ),
            pipeline_config={"sample_rate": 44100},
        )

        json_str = original.to_json()
        restored = BenchmarkRun.from_json(json_str)

        assert restored.run_id == original.run_id
        assert restored.timestamp == original.timestamp
        assert restored.source_midi_path == original.source_midi_path
        assert restored.model_config == original.model_config
        assert restored.pipeline_config == original.pipeline_config
        assert len(restored.stem_metrics) == 2
        assert restored.stem_metrics[0].stem_name == "bass"
        assert restored.stem_metrics[0].precision == 0.9
        assert restored.stem_metrics[1].stem_name == "vocals"
        assert restored.aggregate.mean_f1 == 0.7625
        assert restored.aggregate.worst_stem == "vocals"

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """BenchmarkRun saves to file and loads back correctly."""
        original = BenchmarkRun(
            run_id="save_test",
            timestamp="2026-02-25T00:00:00Z",
            source_midi_path="/path/to/test.mid",
            stem_metrics=[
                StemMetrics(
                    stem_name="piano",
                    precision=0.95,
                    recall=0.92,
                    f1=0.935,
                    avg_overlap=0.88,
                    note_count_ref=50,
                    note_count_est=48,
                ),
            ],
            aggregate=AggregateScore(
                mean_f1=0.935,
                mean_precision=0.95,
                mean_recall=0.92,
                stem_count=1,
                worst_stem="piano",
                worst_f1=0.935,
            ),
        )

        saved_path = original.save(tmp_path / "results")
        assert saved_path.exists()

        loaded = BenchmarkRun.load(saved_path)
        assert loaded.run_id == "save_test"
        assert loaded.stem_metrics[0].stem_name == "piano"
        assert loaded.aggregate.mean_f1 == 0.935


# ---------------------------------------------------------------------------
# Aggregate computation tests
# ---------------------------------------------------------------------------


class TestComputeAggregate:
    """Tests for _compute_aggregate()."""

    def test_single_stem(self) -> None:
        """Aggregate of a single stem equals that stem's metrics."""
        metrics = [
            StemMetrics(
                stem_name="bass",
                precision=0.9,
                recall=0.8,
                f1=0.85,
                avg_overlap=0.7,
                note_count_ref=100,
                note_count_est=90,
            )
        ]
        agg = _compute_aggregate(metrics)
        assert agg.mean_f1 == 0.85
        assert agg.mean_precision == 0.9
        assert agg.worst_stem == "bass"

    def test_multiple_stems_identifies_worst(self) -> None:
        """Aggregate correctly identifies the worst-performing stem."""
        metrics = [
            StemMetrics("bass", 0.9, 0.85, 0.875, 0.8, 100, 95),
            StemMetrics("vocals", 0.7, 0.6, 0.65, 0.5, 200, 180),
            StemMetrics("drums", 0.8, 0.75, 0.775, 0.7, 150, 140),
        ]
        agg = _compute_aggregate(metrics)
        assert agg.worst_stem == "vocals"
        assert agg.worst_f1 == 0.65
        assert agg.stem_count == 3

    def test_empty_metrics(self) -> None:
        """Empty metrics list returns zeroed aggregate."""
        agg = _compute_aggregate([])
        assert agg.mean_f1 == 0.0
        assert agg.stem_count == 0
        assert agg.worst_stem == ""
