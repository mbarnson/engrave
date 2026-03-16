"""Integration tests for YouTube extraction flow through the audio pipeline.

Tests that YouTube URLs are correctly detected, audio is extracted, and the
pipeline processes the extracted audio through all stages.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from engrave.audio.pipeline import AudioPipeline, JobResult
from engrave.cli import app
from engrave.config.settings import AudioConfig


@pytest.fixture
def audio_config() -> AudioConfig:
    """Return a minimal AudioConfig for testing."""
    return AudioConfig()


@pytest.fixture
def pipeline(audio_config: AudioConfig, mock_transcriber: MagicMock) -> AudioPipeline:
    """Create an AudioPipeline with injected mock transcriber."""
    return AudioPipeline(config=audio_config, transcriber=mock_transcriber)


class TestProcessYoutube:
    """Test process_youtube with mocked yt-dlp and pipeline stages."""

    def test_youtube_extraction_and_pipeline(
        self,
        pipeline: AudioPipeline,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        sample_wav: Path,
        tmp_path: Path,
    ) -> None:
        """YouTube URL is extracted then processed through pipeline."""
        job_dir = tmp_path / "youtube_job"

        with patch(
            "engrave.audio.pipeline.extract_youtube_audio",
            return_value=sample_wav,
        ) as mock_extract:
            result = pipeline.process_youtube(
                "https://www.youtube.com/watch?v=test123",
                job_dir=job_dir,
            )

        mock_extract.assert_called_once()
        assert isinstance(result, JobResult)
        assert result.job_dir == job_dir
        assert len(result.stem_results) == 4

    def test_youtube_creates_download_dir(
        self,
        pipeline: AudioPipeline,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        sample_wav: Path,
        tmp_path: Path,
    ) -> None:
        """process_youtube creates a download subdirectory."""
        job_dir = tmp_path / "youtube_job"

        with patch(
            "engrave.audio.pipeline.extract_youtube_audio",
            return_value=sample_wav,
        ):
            pipeline.process_youtube(
                "https://www.youtube.com/watch?v=test123",
                job_dir=job_dir,
            )

        assert (job_dir / "download").exists()


class TestCLIProcessAudio:
    """Test the CLI process-audio command with mocked dependencies."""

    runner = CliRunner()

    def test_cli_with_audio_file(
        self,
        sample_wav: Path,
        mock_normalizer: MagicMock,
        mock_separator: MagicMock,
        mock_transcriber: MagicMock,
        settings: object,
        tmp_path: Path,
    ) -> None:
        """CLI process-audio command works with an audio file path."""
        job_dir = tmp_path / "cli_job"

        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.process.return_value = JobResult(
            job_dir=job_dir,
            input_path=sample_wav,
            stem_results=[],
            metadata={},
        )

        with (
            patch(
                "engrave.audio.pipeline.AudioPipeline",
                return_value=mock_pipeline_instance,
            ),
            patch("engrave.config.settings.Settings", return_value=settings),
        ):
            result = self.runner.invoke(
                app,
                ["process-audio", str(sample_wav), "--output-dir", str(job_dir)],
            )

        assert result.exit_code == 0, result.output
        assert "Pipeline complete" in result.output

    def test_cli_with_youtube_url(
        self,
        settings: object,
        tmp_path: Path,
    ) -> None:
        """CLI process-audio command detects YouTube URL and calls process_youtube."""
        job_dir = tmp_path / "cli_yt_job"

        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.process_youtube.return_value = JobResult(
            job_dir=job_dir,
            input_path=Path("/tmp/fake.wav"),
            stem_results=[],
            metadata={},
        )

        with (
            patch(
                "engrave.audio.pipeline.AudioPipeline",
                return_value=mock_pipeline_instance,
            ),
            patch("engrave.config.settings.Settings", return_value=settings),
            patch(
                "engrave.audio.youtube.is_youtube_url",
                return_value=True,
            ),
        ):
            result = self.runner.invoke(
                app,
                [
                    "process-audio",
                    "https://www.youtube.com/watch?v=test123",
                    "--output-dir",
                    str(job_dir),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_pipeline_instance.process_youtube.assert_called_once()

    def test_cli_missing_file_error(self, settings: object, tmp_path: Path) -> None:
        """CLI exits with error for missing audio file."""
        mock_pipeline_instance = MagicMock()

        with (
            patch(
                "engrave.audio.pipeline.AudioPipeline",
                return_value=mock_pipeline_instance,
            ),
            patch("engrave.config.settings.Settings", return_value=settings),
            patch(
                "engrave.audio.youtube.is_youtube_url",
                return_value=False,
            ),
        ):
            result = self.runner.invoke(
                app,
                ["process-audio", str(tmp_path / "missing.wav")],
            )

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_cli_help_shows_options(self) -> None:
        """CLI process-audio --help displays expected options."""
        result = self.runner.invoke(app, ["process-audio", "--help"], color=False)

        assert result.exit_code == 0
        # Strip ANSI escape codes in case typer still emits them
        import re

        output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "--output-dir" in output
        assert "--no-separate" in output
        assert "--steps" in output
