"""Integration tests for the end-to-end audio pipeline.

Uses mocked separator, transcriber, and normalizer (from conftest) to verify
the pipeline orchestration, job directory structure, and error propagation
without requiring actual audio models.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.audio.pipeline import AudioPipeline, JobResult, StemResult
from engrave.config.settings import AudioConfig


@pytest.fixture
def audio_config() -> AudioConfig:
    """Return a minimal AudioConfig for testing."""
    return AudioConfig()


@pytest.fixture
def pipeline(audio_config: AudioConfig, mock_transcriber: MagicMock) -> AudioPipeline:
    """Create an AudioPipeline with injected mock transcriber."""
    return AudioPipeline(config=audio_config, transcriber=mock_transcriber)


class TestFullPipeline:
    """Test the complete pipeline with mocked dependencies."""

    def test_pipeline_produces_job_result(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full pipeline produces JobResult with stem results."""
        job_dir = tmp_path / "test_job"
        result = pipeline.process(sample_wav, job_dir=job_dir)

        assert isinstance(result, JobResult)
        assert result.job_dir == job_dir
        assert result.input_path == sample_wav
        assert len(result.stem_results) == 4  # drums, bass, vocals, other

    def test_pipeline_creates_job_directory_structure(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pipeline creates expected subdirectories."""
        job_dir = tmp_path / "test_job"
        pipeline.process(sample_wav, job_dir=job_dir)

        assert (job_dir / "input.wav").exists()
        assert (job_dir / "separation").exists()
        assert (job_dir / "transcription").exists()
        assert (job_dir / "quality").exists()
        assert (job_dir / "quality" / "stem_quality.json").exists()
        assert (job_dir / "metadata.json").exists()

    def test_pipeline_writes_metadata_json(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pipeline writes metadata.json with correct structure."""
        job_dir = tmp_path / "test_job"
        pipeline.process(sample_wav, job_dir=job_dir)

        metadata_path = job_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        assert metadata["stem_count"] == 4
        assert "elapsed_seconds" in metadata
        assert "config" in metadata
        assert metadata["config"]["target_sample_rate"] == 44100

    def test_stem_results_have_correct_fields(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Each StemResult has stem_name, midi_path, wav_path, quality, model_used."""
        job_dir = tmp_path / "test_job"
        result = pipeline.process(sample_wav, job_dir=job_dir)

        for sr in result.stem_results:
            assert isinstance(sr, StemResult)
            assert sr.stem_name in ("drums", "bass", "vocals", "other")
            assert sr.midi_path.exists()
            assert sr.wav_path.exists()
            assert sr.quality is not None
            assert sr.quality.note_count >= 0
            assert sr.model_used == "mock_model"

    def test_quality_annotations_written(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pipeline writes stem_quality.json with quality data for each stem."""
        job_dir = tmp_path / "test_job"
        pipeline.process(sample_wav, job_dir=job_dir)

        quality_path = job_dir / "quality" / "stem_quality.json"
        quality_data = json.loads(quality_path.read_text())

        assert len(quality_data) == 4
        for record in quality_data:
            assert "stem_name" in record
            assert "note_count" in record
            assert "pitch_range_violations" in record

    def test_pipeline_auto_generates_job_dir(
        self,
        pipeline: AudioPipeline,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Pipeline auto-generates timestamped job directory when none provided."""
        # Redirect job dir creation to tmp_path
        monkeypatch.chdir(tmp_path)
        result = pipeline.process(sample_wav)

        assert result.job_dir.exists()
        assert "jobs" in str(result.job_dir)


class TestPipelineErrorHandling:
    """Test error propagation from individual stages."""

    def test_normalizer_failure_propagates(
        self,
        audio_config: AudioConfig,
        mock_transcriber: MagicMock,
        sample_wav: Path,
        tmp_path: Path,
    ) -> None:
        """Normalizer errors propagate through the pipeline."""
        pipeline = AudioPipeline(config=audio_config, transcriber=mock_transcriber)

        with (
            patch(
                "engrave.audio.pipeline.normalize_audio",
                side_effect=ValueError("Duration exceeds maximum"),
            ),
            pytest.raises(ValueError, match="Duration exceeds maximum"),
        ):
            pipeline.process(sample_wav, job_dir=tmp_path / "test_job")

    def test_separator_failure_propagates(
        self,
        audio_config: AudioConfig,
        mock_transcriber: MagicMock,
        mock_normalizer: MagicMock,
        sample_wav: Path,
        tmp_path: Path,
    ) -> None:
        """Separator errors propagate through the pipeline."""
        pipeline = AudioPipeline(config=audio_config, transcriber=mock_transcriber)

        with (
            patch(
                "engrave.audio.pipeline.run_separation",
                side_effect=RuntimeError("Model loading failed"),
            ),
            pytest.raises(RuntimeError, match="Model loading failed"),
        ):
            pipeline.process(sample_wav, job_dir=tmp_path / "test_job")

    def test_transcriber_failure_propagates(
        self,
        audio_config: AudioConfig,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        sample_wav: Path,
        tmp_path: Path,
    ) -> None:
        """Transcriber errors on any stem propagate through the pipeline."""
        bad_transcriber = MagicMock()
        bad_transcriber.transcribe.side_effect = RuntimeError("basic_pitch failed")

        pipeline = AudioPipeline(config=audio_config, transcriber=bad_transcriber)

        with pytest.raises(RuntimeError, match="basic_pitch failed"):
            pipeline.process(sample_wav, job_dir=tmp_path / "test_job")

    def test_file_not_found_error(
        self,
        audio_config: AudioConfig,
        mock_transcriber: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pipeline raises FileNotFoundError for missing input file."""
        pipeline = AudioPipeline(config=audio_config, transcriber=mock_transcriber)
        missing_file = tmp_path / "does_not_exist.wav"

        with pytest.raises(FileNotFoundError, match=r"does_not_exist\.wav"):
            pipeline.process(missing_file, job_dir=tmp_path / "test_job")
