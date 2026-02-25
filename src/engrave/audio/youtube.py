"""YouTube audio extraction via yt-dlp Python API.

Downloads audio from a YouTube URL and converts it to WAV using the
yt-dlp library with FFmpegExtractAudio postprocessor.  Output filenames
are based on the video ID (not title) for deterministic, reproducible
pipeline runs.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)

# Patterns that identify a YouTube URL.
_YOUTUBE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?"),
    re.compile(r"^https?://youtu\.be/"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/"),
]


class YouTubeExtractionError(RuntimeError):
    """Raised when yt-dlp fails to download or extract audio."""


def is_youtube_url(url: str) -> bool:
    """Return True if *url* looks like a YouTube video URL."""
    return any(pat.search(url) for pat in _YOUTUBE_PATTERNS)


def extract_youtube_audio(url: str, output_dir: Path) -> Path:
    """Download audio from *url* and convert to WAV in *output_dir*.

    Uses the yt-dlp Python API with ``FFmpegExtractAudio`` postprocessor.
    The output filename is ``<video_id>.wav`` for deterministic results.

    Parameters
    ----------
    url:
        A YouTube video URL.
    output_dir:
        Directory where the WAV file will be written (created if needed).

    Returns
    -------
    Path
        Absolute path to the extracted WAV file.

    Raises
    ------
    ValueError
        If *url* is empty or not a string.
    YouTubeExtractionError
        If yt-dlp fails to download or process the video.
    """
    if not url or not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeExtractionError(f"Failed to download audio from {url}: {exc}") from exc
    except Exception as exc:
        raise YouTubeExtractionError(
            f"Unexpected error extracting audio from {url}: {exc}"
        ) from exc

    wav_path = output_dir / f"{video_id}.wav"
    logger.info("Extracted YouTube audio: %s -> %s", url, wav_path)
    return wav_path
