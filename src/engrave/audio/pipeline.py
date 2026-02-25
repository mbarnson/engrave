"""Audio pipeline orchestration -- normalize, separate, transcribe, annotate.

Creates a timestamped job directory for each invocation, runs each stage
sequentially, and collects per-stem MIDI paths with quality metadata.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engrave.audio.normalizer import normalize_audio
from engrave.audio.quality import StemQuality, annotate_quality, get_expected_range
from engrave.audio.separator import StemOutput, get_default_steps, run_separation
from engrave.audio.transcriber import (
    Transcriber,
    TranscriptionConfig,
    create_transcriber,
)
from engrave.audio.youtube import extract_youtube_audio
from engrave.config.settings import AudioConfig

logger = logging.getLogger(__name__)


@dataclass
class StemResult:
    """Result for a single separated + transcribed stem.

    Attributes:
        stem_name: Standardized stem name (e.g. "drums", "bass").
        midi_path: Path to the transcribed MIDI file.
        wav_path: Path to the separated WAV file.
        quality: Quality heuristic metrics for this stem.
        model_used: Separation model that produced this stem.
    """

    stem_name: str
    midi_path: Path
    wav_path: Path
    quality: StemQuality
    model_used: str


@dataclass
class JobResult:
    """Result of a full pipeline invocation.

    Attributes:
        job_dir: Path to the timestamped job directory.
        input_path: Path to the original input audio file.
        stem_results: Per-stem MIDI paths and quality metadata.
        metadata: Pipeline config, timing, and model versions.
    """

    job_dir: Path
    input_path: Path
    stem_results: list[StemResult]
    metadata: dict[str, Any] = field(default_factory=dict)


class AudioPipeline:
    """Orchestrates the full audio-to-MIDI pipeline.

    Stages run sequentially:
      1. Normalize input audio to WAV mono 44.1kHz
      2. Separate into stems via hierarchical cascade
      3. Transcribe each stem WAV to MIDI
      4. Annotate quality metrics per transcribed MIDI

    Args:
        config: Audio pipeline configuration from settings.
        transcriber: Optional injected transcriber (for testing).
            If None, creates one from config.
    """

    def __init__(
        self,
        config: AudioConfig,
        transcriber: Transcriber | None = None,
    ) -> None:
        self.config = config
        if transcriber is not None:
            self._transcriber = transcriber
        else:
            tc = TranscriptionConfig(
                venv_python=(
                    Path(config.transcription.venv_python)
                    if config.transcription.venv_python
                    else None
                ),
                onset_threshold=config.transcription.onset_threshold,
                frame_threshold=config.transcription.frame_threshold,
                minimum_note_length_ms=config.transcription.minimum_note_length_ms,
            )
            self._transcriber = create_transcriber(tc)

    def process(self, input_path: Path, job_dir: Path | None = None) -> JobResult:
        """Run the full pipeline on an audio file.

        Args:
            input_path: Path to the source audio file (MP3, WAV, AIFF, FLAC).
            job_dir: Optional custom job directory. If None, creates a
                timestamped directory under ``jobs/``.

        Returns:
            JobResult with per-stem MIDI paths and quality metadata.

        Raises:
            FileNotFoundError: If input_path does not exist.
        """
        t0 = time.monotonic()

        if not input_path.exists():
            msg = f"Input audio file not found: {input_path}"
            raise FileNotFoundError(msg)

        # Create job directory
        if job_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            job_dir = Path("jobs") / f"{timestamp}_{input_path.stem}"
        job_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Pipeline started: input=%s, job_dir=%s", input_path, job_dir)

        # Stage 1: Normalize
        normalized_path = job_dir / "input.wav"
        normalize_audio(
            input_path,
            normalized_path,
            target_sr=self.config.target_sample_rate,
            channels=self.config.target_channels,
            max_duration_seconds=self.config.max_duration_seconds,
        )
        logger.info("Normalize complete: %s", normalized_path)

        # Stage 2: Separate
        separation_dir = job_dir / "separation"
        steps = self.config.separation.steps
        if not steps:
            # Use default big band cascade from separator module
            sep_steps = get_default_steps()
        else:
            # Convert config SeparationStep models to separator.SeparationStep
            from engrave.audio.separator import SeparationStep as SepStep

            sep_steps = [
                SepStep(
                    model=s.model,
                    input_stem=s.input_stem,
                    output_stems=s.output_stems,
                )
                for s in steps
            ]
        stem_outputs: list[StemOutput] = run_separation(normalized_path, sep_steps, separation_dir)
        logger.info("Separation complete: %d stems", len(stem_outputs))

        # Stage 3: Transcribe
        transcription_dir = job_dir / "transcription"
        transcription_dir.mkdir(parents=True, exist_ok=True)

        midi_paths: dict[str, Path] = {}
        for stem in stem_outputs:
            midi_path = self._transcriber.transcribe(stem.path, transcription_dir)
            midi_paths[stem.stem_name] = midi_path
        logger.info("Transcription complete: %d MIDI files", len(midi_paths))

        # Stage 4: Annotate quality
        quality_dir = job_dir / "quality"
        quality_dir.mkdir(parents=True, exist_ok=True)

        stem_results: list[StemResult] = []
        quality_records: list[dict[str, Any]] = []
        for stem in stem_outputs:
            midi_path = midi_paths[stem.stem_name]
            expected_range = get_expected_range(stem.stem_name)
            quality = annotate_quality(
                midi_path,
                stem.stem_name,
                expected_range=expected_range,
            )
            stem_results.append(
                StemResult(
                    stem_name=stem.stem_name,
                    midi_path=midi_path,
                    wav_path=stem.path,
                    quality=quality,
                    model_used=stem.model_used,
                )
            )
            quality_records.append(quality.to_dict())

        # Write quality summary
        quality_json = quality_dir / "stem_quality.json"
        quality_json.write_text(json.dumps(quality_records, indent=2, default=str))
        logger.info("Quality annotation complete")

        # Write job metadata
        elapsed = time.monotonic() - t0
        metadata: dict[str, Any] = {
            "input_path": str(input_path),
            "job_dir": str(job_dir),
            "stem_count": len(stem_results),
            "elapsed_seconds": round(elapsed, 2),
            "config": {
                "target_sample_rate": self.config.target_sample_rate,
                "target_channels": self.config.target_channels,
                "max_duration_seconds": self.config.max_duration_seconds,
            },
            "stems": [
                {
                    "name": sr.stem_name,
                    "midi_path": str(sr.midi_path),
                    "wav_path": str(sr.wav_path),
                    "model_used": sr.model_used,
                }
                for sr in stem_results
            ],
        }
        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str))

        logger.info("Pipeline complete: %d stems in %.1fs", len(stem_results), elapsed)

        return JobResult(
            job_dir=job_dir,
            input_path=input_path,
            stem_results=stem_results,
            metadata=metadata,
        )

    def process_youtube(self, url: str, job_dir: Path | None = None) -> JobResult:
        """Download audio from a YouTube URL and run the full pipeline.

        Args:
            url: YouTube video URL.
            job_dir: Optional custom job directory. If None, auto-generated.

        Returns:
            JobResult with per-stem MIDI paths and quality metadata.
        """
        # Create a temporary directory for the download
        if job_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            job_dir = Path("jobs") / f"{timestamp}_youtube"
        job_dir.mkdir(parents=True, exist_ok=True)

        download_dir = job_dir / "download"
        download_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Extracting audio from YouTube: %s", url)
        wav_path = extract_youtube_audio(url, download_dir)

        return self.process(wav_path, job_dir)
