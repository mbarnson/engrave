"""Unit tests for YouTube audio extraction (all yt-dlp calls mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.audio.youtube import (
    YouTubeExtractionError,
    extract_youtube_audio,
    is_youtube_url,
)

# ---------------------------------------------------------------------------
# is_youtube_url
# ---------------------------------------------------------------------------


class TestIsYoutubeUrl:
    """Validate URL pattern matching for YouTube links."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abcDEF12345",
            "https://youtube.com/shorts/abcDEF12345",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42",
        ],
    )
    def test_valid_youtube_urls(self, url: str) -> None:
        assert is_youtube_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://vimeo.com/12345",
            "https://example.com/watch?v=xyz",
            "https://www.youtube.com/playlist?list=PLxyz",
            "not-a-url",
            "",
        ],
    )
    def test_non_youtube_urls(self, url: str) -> None:
        assert is_youtube_url(url) is False


# ---------------------------------------------------------------------------
# extract_youtube_audio -- happy path (mocked)
# ---------------------------------------------------------------------------


class TestExtractYoutubeAudio:
    """Core extraction tests with fully mocked yt-dlp."""

    @patch("engrave.audio.youtube.yt_dlp")
    def test_returns_wav_path_from_video_id(self, mock_yt_dlp: MagicMock, tmp_path: Path) -> None:
        """Verify output path is <output_dir>/<video_id>.wav."""
        fake_info = {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up"}
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = fake_info
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance

        result = extract_youtube_audio("https://www.youtube.com/watch?v=dQw4w9WgXcQ", tmp_path)

        assert result == tmp_path / "dQw4w9WgXcQ.wav"

    @patch("engrave.audio.youtube.yt_dlp")
    def test_passes_correct_options(self, mock_yt_dlp: MagicMock, tmp_path: Path) -> None:
        """Verify yt-dlp receives the expected options dict."""
        fake_info = {"id": "abc123"}
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = fake_info
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance

        extract_youtube_audio("https://youtu.be/abc123", tmp_path)

        # Check YoutubeDL was constructed with the right options
        call_args = mock_yt_dlp.YoutubeDL.call_args
        opts = call_args[0][0]
        assert opts["format"] == "bestaudio/best"
        assert opts["quiet"] is True
        assert "%(id)s.%(ext)s" in opts["outtmpl"]
        assert any(
            pp.get("key") == "FFmpegExtractAudio" and pp.get("preferredcodec") == "wav"
            for pp in opts["postprocessors"]
        )

    @patch("engrave.audio.youtube.yt_dlp")
    def test_creates_output_dir_if_missing(self, mock_yt_dlp: MagicMock, tmp_path: Path) -> None:
        """Output directory is created automatically when it does not exist."""
        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()

        fake_info = {"id": "vid1"}
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = fake_info
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance

        extract_youtube_audio("https://youtu.be/vid1", nested)
        assert nested.exists()


# ---------------------------------------------------------------------------
# extract_youtube_audio -- error handling
# ---------------------------------------------------------------------------


class TestExtractYoutubeAudioErrors:
    """Error paths: invalid input and yt-dlp failures."""

    def test_empty_url_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            extract_youtube_audio("", tmp_path)

    def test_whitespace_url_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            extract_youtube_audio("   ", tmp_path)

    @patch("engrave.audio.youtube.yt_dlp")
    def test_download_error_raises_extraction_error(
        self, mock_yt_dlp: MagicMock, tmp_path: Path
    ) -> None:
        """yt-dlp DownloadError is wrapped in YouTubeExtractionError."""
        mock_ydl_instance = MagicMock()
        download_err = type("DownloadError", (Exception,), {})("video unavailable")
        mock_ydl_instance.extract_info.side_effect = download_err
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance
        # Assign the DownloadError class to the mock's utils namespace
        mock_yt_dlp.utils.DownloadError = type(download_err)

        with pytest.raises(YouTubeExtractionError, match="Failed to download"):
            extract_youtube_audio("https://youtu.be/bad", tmp_path)

    @patch("engrave.audio.youtube.yt_dlp")
    def test_unexpected_error_raises_extraction_error(
        self, mock_yt_dlp: MagicMock, tmp_path: Path
    ) -> None:
        """Non-DownloadError exceptions are wrapped as unexpected."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = OSError("disk full")
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)
        mock_yt_dlp.YoutubeDL.return_value = mock_ydl_instance
        # Make DownloadError a class that OSError does NOT match
        mock_yt_dlp.utils.DownloadError = type("DownloadError", (Exception,), {})

        with pytest.raises(YouTubeExtractionError, match="Unexpected error"):
            extract_youtube_audio("https://youtu.be/bad2", tmp_path)
