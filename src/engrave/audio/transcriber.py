"""Pluggable MIDI transcription engine.

Defines a Protocol-based contract for WAV-to-MIDI transcription and a
concrete BasicPitchTranscriber that supports both in-process (ONNX) and
subprocess (Python 3.10 venv) execution paths.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Transcriber(Protocol):
    """WAV-in, MIDI-out contract for pluggable transcription backends."""

    def transcribe(self, wav_path: Path, output_dir: Path) -> Path:
        """Transcribe a WAV file to MIDI.

        Args:
            wav_path: Path to the input WAV file.
            output_dir: Directory to write the output MIDI file into.

        Returns:
            Path to the written MIDI file.
        """
        ...


@dataclass
class TranscriptionConfig:
    """Configuration for transcription engine setup.

    Attributes:
        venv_python: Path to a Python 3.10 venv interpreter for subprocess
            execution. If None, uses in-process ONNX inference.
        onset_threshold: Onset detection threshold for Basic Pitch (0-1).
        frame_threshold: Frame detection threshold for Basic Pitch (0-1).
        minimum_note_length_ms: Minimum note length in milliseconds.
    """

    venv_python: Path | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    minimum_note_length_ms: int = 58


@dataclass
class BasicPitchTranscriber:
    """Basic Pitch transcription backend with dual execution paths.

    When ``venv_python`` is None, imports ``basic_pitch`` directly and runs
    inference in-process using ONNX. When ``venv_python`` points to a
    Python 3.10 interpreter, invokes ``basic_pitch`` as a subprocess.

    Attributes:
        venv_python: Path to Python 3.10 venv interpreter, or None for
            in-process execution.
        onset_threshold: Onset detection threshold (0-1).
        frame_threshold: Frame detection threshold (0-1).
        minimum_note_length_ms: Minimum note length in milliseconds.
    """

    venv_python: Path | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    minimum_note_length_ms: int = 58

    def transcribe(self, wav_path: Path, output_dir: Path) -> Path:
        """Transcribe a WAV file to MIDI via Basic Pitch.

        Args:
            wav_path: Path to the input WAV file.
            output_dir: Directory to write the output MIDI file into.

        Returns:
            Path to the written MIDI file.

        Raises:
            FileNotFoundError: If wav_path does not exist.
            RuntimeError: If subprocess transcription fails.
        """
        if not wav_path.exists():
            msg = f"WAV file not found: {wav_path}"
            raise FileNotFoundError(msg)

        output_dir.mkdir(parents=True, exist_ok=True)
        midi_path = output_dir / f"{wav_path.stem}.mid"

        if self.venv_python is not None:
            self._transcribe_subprocess(wav_path, midi_path)
        else:
            self._transcribe_inprocess(wav_path, midi_path)

        return midi_path

    def _transcribe_inprocess(self, wav_path: Path, midi_path: Path) -> None:
        """Run Basic Pitch in-process using ONNX model.

        Imports basic_pitch lazily to avoid import errors when the package
        is not installed in the current environment.
        """
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model, predict

        model = Model(ICASSP_2022_MODEL_PATH)
        _model_output, midi_data, _note_events = predict(
            wav_path,
            model,
            onset_threshold=self.onset_threshold,
            frame_threshold=self.frame_threshold,
            minimum_note_length=self.minimum_note_length_ms,
        )
        midi_data.write(str(midi_path))

    def _transcribe_subprocess(self, wav_path: Path, midi_path: Path) -> None:
        """Run Basic Pitch via subprocess in isolated Python 3.10 venv.

        Raises:
            RuntimeError: If the subprocess exits with non-zero return code.
        """
        cmd = [
            str(self.venv_python),
            "-m",
            "basic_pitch",
            str(midi_path.parent),
            str(wav_path),
            "--model-serialization",
            "onnx",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            msg = f"basic_pitch subprocess failed (exit {result.returncode}): {result.stderr}"
            raise RuntimeError(msg)


def create_transcriber(config: TranscriptionConfig) -> Transcriber:
    """Factory: create a Transcriber from configuration.

    Args:
        config: Transcription configuration specifying execution path
            and tuning parameters.

    Returns:
        A BasicPitchTranscriber configured per the supplied config.
    """
    return BasicPitchTranscriber(
        venv_python=config.venv_python,
        onset_threshold=config.onset_threshold,
        frame_threshold=config.frame_threshold,
        minimum_note_length_ms=config.minimum_note_length_ms,
    )
