"""Unit tests for benchmark MIDI-to-audio renderer.

FluidSynth is fully mocked -- these tests verify correct argument passing
and error handling without requiring a real FluidSynth installation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.benchmark.renderer import render_midi_to_audio


@pytest.fixture
def fake_midi(tmp_path: Path) -> Path:
    """Create a fake MIDI file for testing."""
    midi = tmp_path / "test.mid"
    midi.write_bytes(b"fake-midi-data")
    return midi


class TestRenderMidiToAudio:
    """Tests for render_midi_to_audio()."""

    @patch("engrave.benchmark.renderer.FluidSynth")
    def test_calls_fluidsynth_with_soundfont(
        self, mock_fs_class: MagicMock, fake_midi: Path, tmp_path: Path
    ) -> None:
        """Renderer passes custom soundfont path to FluidSynth constructor."""
        wav_path = tmp_path / "output.wav"
        mock_instance = MagicMock()
        mock_fs_class.return_value = mock_instance

        result = render_midi_to_audio(fake_midi, wav_path, soundfont="/path/to/font.sf2")

        mock_fs_class.assert_called_once_with("/path/to/font.sf2")
        mock_instance.midi_to_audio.assert_called_once_with(str(fake_midi), str(wav_path))
        assert result == wav_path

    @patch("engrave.benchmark.renderer.FluidSynth")
    def test_calls_fluidsynth_default_soundfont(
        self, mock_fs_class: MagicMock, fake_midi: Path, tmp_path: Path
    ) -> None:
        """Renderer uses default FluidSynth constructor when no soundfont specified."""
        wav_path = tmp_path / "output.wav"
        mock_instance = MagicMock()
        mock_fs_class.return_value = mock_instance

        render_midi_to_audio(fake_midi, wav_path)

        mock_fs_class.assert_called_once_with()
        mock_instance.midi_to_audio.assert_called_once_with(str(fake_midi), str(wav_path))

    @patch("engrave.benchmark.renderer.FluidSynth")
    def test_creates_parent_directory(
        self, mock_fs_class: MagicMock, fake_midi: Path, tmp_path: Path
    ) -> None:
        """Renderer creates parent directories for wav_path if they don't exist."""
        wav_path = tmp_path / "nested" / "dir" / "output.wav"
        mock_fs_class.return_value = MagicMock()

        render_midi_to_audio(fake_midi, wav_path)

        assert wav_path.parent.exists()

    def test_raises_file_not_found_for_missing_midi(self, tmp_path: Path) -> None:
        """Renderer raises FileNotFoundError when MIDI file doesn't exist."""
        missing = tmp_path / "does_not_exist.mid"
        wav_path = tmp_path / "output.wav"

        with pytest.raises(FileNotFoundError, match=r"does_not_exist\.mid"):
            render_midi_to_audio(missing, wav_path)

    @patch("engrave.benchmark.renderer.FluidSynth")
    def test_returns_wav_path(
        self, mock_fs_class: MagicMock, fake_midi: Path, tmp_path: Path
    ) -> None:
        """Renderer returns the wav_path argument."""
        wav_path = tmp_path / "output.wav"
        mock_fs_class.return_value = MagicMock()

        result = render_midi_to_audio(fake_midi, wav_path)

        assert result == wav_path
