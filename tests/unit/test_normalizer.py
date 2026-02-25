"""Tests for audio format normalization."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.audio.normalizer import (
    SUPPORTED_FORMATS,
    detect_audio_format,
    normalize_audio,
)

# ---------------------------------------------------------------------------
# Helpers -- programmatic WAV creation (no pydub dependency in fixtures)
# ---------------------------------------------------------------------------


def _make_wav(
    path: Path,
    *,
    sample_rate: int = 44100,
    channels: int = 1,
    duration_s: float = 1.0,
    frequency: float = 440.0,
) -> Path:
    """Write a minimal valid WAV file containing a sine wave.

    Uses only the ``wave`` and ``struct`` stdlib modules so test fixtures
    never depend on pydub.
    """
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frame = struct.pack("<h", sample) * channels
            wf.writeframes(frame)
    return path


# ---------------------------------------------------------------------------
# detect_audio_format
# ---------------------------------------------------------------------------


class TestDetectAudioFormat:
    """Tests for detect_audio_format()."""

    @pytest.mark.parametrize("ext", sorted(SUPPORTED_FORMATS))
    def test_supported_formats(self, tmp_path: Path, ext: str) -> None:
        """Supported extensions are returned as lowercase strings."""
        p = tmp_path / f"test.{ext}"
        p.touch()
        assert detect_audio_format(p) == ext

    def test_uppercase_extension(self, tmp_path: Path) -> None:
        """Extension matching is case-insensitive."""
        p = tmp_path / "test.MP3"
        p.touch()
        assert detect_audio_format(p) == "mp3"

    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        """Unsupported extensions raise ValueError."""
        p = tmp_path / "test.ogg"
        p.touch()
        with pytest.raises(ValueError, match="Unsupported audio format"):
            detect_audio_format(p)

    def test_no_extension_raises(self, tmp_path: Path) -> None:
        """Files without an extension raise ValueError."""
        p = tmp_path / "audiofile"
        p.touch()
        with pytest.raises(ValueError, match="Unsupported audio format"):
            detect_audio_format(p)


# ---------------------------------------------------------------------------
# normalize_audio -- real WAV round-trip
# ---------------------------------------------------------------------------


class TestNormalizeAudioWav:
    """Tests using real WAV fixtures (no mocks)."""

    def test_passthrough_mono_44100(self, sample_wav: Path, tmp_path: Path) -> None:
        """A mono 44.1kHz WAV passes through unchanged (modulo re-encoding)."""
        out = tmp_path / "out.wav"
        result = normalize_audio(sample_wav, out)
        assert result == out
        assert out.exists()
        with wave.open(str(out), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 44100

    def test_stereo_to_mono(self, tmp_path: Path) -> None:
        """Stereo input is downmixed to mono."""
        stereo_path = _make_wav(tmp_path / "stereo.wav", channels=2, duration_s=0.5)
        out = tmp_path / "mono_out.wav"
        normalize_audio(stereo_path, out)
        with wave.open(str(out), "rb") as wf:
            assert wf.getnchannels() == 1

    def test_resample(self, tmp_path: Path) -> None:
        """Input at a non-standard sample rate is resampled to target."""
        src = _make_wav(tmp_path / "sr22050.wav", sample_rate=22050, duration_s=0.5)
        out = tmp_path / "resampled.wav"
        normalize_audio(src, out, target_sr=44100)
        with wave.open(str(out), "rb") as wf:
            assert wf.getframerate() == 44100

    def test_output_directory_created(self, sample_wav: Path, tmp_path: Path) -> None:
        """Parent directories for output_path are created automatically."""
        out = tmp_path / "deep" / "nested" / "out.wav"
        normalize_audio(sample_wav, out)
        assert out.exists()

    def test_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError for non-existent input."""
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            normalize_audio(tmp_path / "ghost.wav", tmp_path / "out.wav")

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """Unsupported format extension raises ValueError."""
        bad = tmp_path / "song.ogg"
        bad.write_bytes(b"\x00")
        with pytest.raises(ValueError, match="Unsupported audio format"):
            normalize_audio(bad, tmp_path / "out.wav")

    def test_duration_exceeded(self, tmp_path: Path) -> None:
        """Files longer than max_duration_seconds are rejected."""
        # Create a short WAV then mock duration check
        src = _make_wav(tmp_path / "short.wav", duration_s=0.5)
        out = tmp_path / "out.wav"
        # Use a tiny max to trigger the check
        with pytest.raises(ValueError, match="exceeds maximum"):
            normalize_audio(src, out, max_duration_seconds=0)


# ---------------------------------------------------------------------------
# normalize_audio -- mocked pydub for MP3/AIFF/FLAC
# ---------------------------------------------------------------------------


class TestNormalizeAudioMocked:
    """Tests for non-WAV formats using mocked pydub.AudioSegment."""

    @pytest.mark.parametrize("ext", ["mp3", "aiff", "flac"])
    def test_non_wav_format(self, tmp_path: Path, ext: str) -> None:
        """Non-WAV formats are loaded via pydub and exported as WAV."""
        src = tmp_path / f"song.{ext}"
        src.write_bytes(b"\x00" * 100)
        out = tmp_path / "out.wav"

        mock_audio = MagicMock()
        mock_audio.frame_rate = 44100
        mock_audio.channels = 1
        mock_audio.__len__ = MagicMock(return_value=5000)  # 5 seconds in ms

        with patch(
            "engrave.audio.normalizer.AudioSegment.from_file",
            return_value=mock_audio,
        ) as mock_from_file:
            normalize_audio(src, out)
            mock_from_file.assert_called_once_with(str(src), format=ext)
            mock_audio.export.assert_called_once_with(str(out), format="wav")

    def test_non_wav_resampled_and_downmixed(self, tmp_path: Path) -> None:
        """Non-WAV files are resampled and downmixed when needed."""
        src = tmp_path / "song.mp3"
        src.write_bytes(b"\x00" * 100)
        out = tmp_path / "out.wav"

        mock_audio = MagicMock()
        mock_audio.frame_rate = 48000
        mock_audio.channels = 2
        mock_audio.__len__ = MagicMock(return_value=3000)

        resampled = MagicMock()
        resampled.channels = 2
        resampled.__len__ = MagicMock(return_value=3000)

        downmixed = MagicMock()
        downmixed.__len__ = MagicMock(return_value=3000)

        mock_audio.set_frame_rate.return_value = resampled
        resampled.set_channels.return_value = downmixed

        with patch(
            "engrave.audio.normalizer.AudioSegment.from_file",
            return_value=mock_audio,
        ):
            normalize_audio(src, out, target_sr=44100, channels=1)
            mock_audio.set_frame_rate.assert_called_once_with(44100)
            resampled.set_channels.assert_called_once_with(1)
            downmixed.export.assert_called_once_with(str(out), format="wav")
