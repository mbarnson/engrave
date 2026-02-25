"""Unit tests for the Transcriber protocol and BasicPitchTranscriber.

All basic_pitch imports are mocked at the module level -- basic_pitch is
not installed in the project's Python 3.12 environment.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.audio.transcriber import (
    BasicPitchTranscriber,
    Transcriber,
    TranscriptionConfig,
    create_transcriber,
)

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestTranscriberProtocol:
    """Verify BasicPitchTranscriber satisfies the Transcriber protocol."""

    def test_basic_pitch_transcriber_is_transcriber(self) -> None:
        transcriber = BasicPitchTranscriber()
        assert isinstance(transcriber, Transcriber)

    def test_protocol_is_runtime_checkable(self) -> None:
        """An arbitrary object without transcribe() is NOT a Transcriber."""

        class NotATranscriber:
            pass

        assert not isinstance(NotATranscriber(), Transcriber)


# ---------------------------------------------------------------------------
# In-process path (mocked basic_pitch)
# ---------------------------------------------------------------------------


class TestInprocessTranscription:
    """Test the in-process ONNX execution path with mocked basic_pitch."""

    def test_inprocess_calls_predict_and_writes_midi(self, tmp_path: Path) -> None:
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_dir = tmp_path / "output"

        with (
            patch(
                "engrave.audio.transcriber.BasicPitchTranscriber._transcribe_inprocess"
            ) as mock_inprocess,
        ):
            # Simulate the inprocess path writing the MIDI file
            def side_effect(wav_path: Path, midi_path: Path) -> None:
                midi_path.parent.mkdir(parents=True, exist_ok=True)
                midi_path.write_bytes(b"MThd" + b"\x00" * 100)

            mock_inprocess.side_effect = side_effect

            transcriber = BasicPitchTranscriber()
            result = transcriber.transcribe(wav_file, output_dir)

            assert result == output_dir / "test.mid"
            mock_inprocess.assert_called_once()

    def test_inprocess_internal_imports_and_predict(self, tmp_path: Path) -> None:
        """Verify _transcribe_inprocess calls predict() with correct args."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)
        midi_path = tmp_path / "output" / "test.mid"
        midi_path.parent.mkdir(parents=True, exist_ok=True)

        mock_midi_data = MagicMock()
        mock_model_class = MagicMock()
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_predict = MagicMock(return_value=(MagicMock(), mock_midi_data, MagicMock()))
        mock_model_path = "/fake/model/path"

        with (
            patch.dict(
                "sys.modules",
                {
                    "basic_pitch": MagicMock(ICASSP_2022_MODEL_PATH=mock_model_path),
                    "basic_pitch.inference": MagicMock(
                        predict=mock_predict, Model=mock_model_class
                    ),
                },
            ),
        ):
            transcriber = BasicPitchTranscriber(
                onset_threshold=0.6,
                frame_threshold=0.4,
                minimum_note_length_ms=100,
            )
            transcriber._transcribe_inprocess(wav_file, midi_path)

            mock_model_class.assert_called_once_with(mock_model_path)
            mock_predict.assert_called_once_with(
                wav_file,
                mock_model_instance,
                onset_threshold=0.6,
                frame_threshold=0.4,
                minimum_note_length=100,
            )
            mock_midi_data.write.assert_called_once_with(str(midi_path))


# ---------------------------------------------------------------------------
# Subprocess path
# ---------------------------------------------------------------------------


class TestSubprocessTranscription:
    """Test the subprocess execution path."""

    def test_subprocess_constructs_correct_command(self, tmp_path: Path) -> None:
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_dir = tmp_path / "output"

        venv_python = Path("/opt/bp310/bin/python")

        with patch("engrave.audio.transcriber.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            transcriber = BasicPitchTranscriber(venv_python=venv_python)
            result = transcriber.transcribe(wav_file, output_dir)

            assert result == output_dir / "test.mid"
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert cmd[0] == str(venv_python)
            assert cmd[1:3] == ["-m", "basic_pitch"]
            assert cmd[3] == str(output_dir)
            assert cmd[4] == str(wav_file)
            assert "--model-serialization" in cmd
            assert "onnx" in cmd
            assert call_args[1]["capture_output"] is True
            assert call_args[1]["text"] is True
            assert call_args[1]["timeout"] == 300

    def test_subprocess_error_raises_runtime_error(self, tmp_path: Path) -> None:
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_dir = tmp_path / "output"

        venv_python = Path("/opt/bp310/bin/python")

        with patch("engrave.audio.transcriber.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'tensorflow'",
            )

            transcriber = BasicPitchTranscriber(venv_python=venv_python)
            with pytest.raises(RuntimeError, match="basic_pitch subprocess failed"):
                transcriber.transcribe(wav_file, output_dir)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Test error handling for invalid inputs."""

    def test_missing_wav_raises_file_not_found(self, tmp_path: Path) -> None:
        transcriber = BasicPitchTranscriber()
        nonexistent = tmp_path / "does_not_exist.wav"

        with pytest.raises(FileNotFoundError, match="WAV file not found"):
            transcriber.transcribe(nonexistent, tmp_path / "output")

    def test_output_dir_created_if_missing(self, tmp_path: Path) -> None:
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_dir = tmp_path / "nested" / "deep" / "output"

        with patch("engrave.audio.transcriber.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            transcriber = BasicPitchTranscriber(venv_python=Path("/usr/bin/python3"))
            transcriber.transcribe(wav_file, output_dir)

            assert output_dir.exists()


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


class TestCreateTranscriber:
    """Test the create_transcriber factory function."""

    def test_creates_inprocess_transcriber(self) -> None:
        config = TranscriptionConfig()
        transcriber = create_transcriber(config)

        assert isinstance(transcriber, BasicPitchTranscriber)
        assert isinstance(transcriber, Transcriber)
        assert transcriber.venv_python is None
        assert transcriber.onset_threshold == 0.5
        assert transcriber.frame_threshold == 0.3
        assert transcriber.minimum_note_length_ms == 58

    def test_creates_subprocess_transcriber(self) -> None:
        venv = Path("/opt/bp310/bin/python")
        config = TranscriptionConfig(venv_python=venv)
        transcriber = create_transcriber(config)

        assert isinstance(transcriber, BasicPitchTranscriber)
        assert transcriber.venv_python == venv

    def test_passes_custom_thresholds(self) -> None:
        config = TranscriptionConfig(
            onset_threshold=0.7,
            frame_threshold=0.5,
            minimum_note_length_ms=120,
        )
        transcriber = create_transcriber(config)

        assert isinstance(transcriber, BasicPitchTranscriber)
        assert transcriber.onset_threshold == 0.7
        assert transcriber.frame_threshold == 0.5
        assert transcriber.minimum_note_length_ms == 120
