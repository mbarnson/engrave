"""Audio format normalization -- convert supported formats to WAV mono 44.1kHz."""

from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment

# Supported audio file extensions (lowercase, no leading dot).
SUPPORTED_FORMATS = frozenset({"mp3", "wav", "aiff", "flac"})

# Default maximum duration in seconds (15 minutes).
DEFAULT_MAX_DURATION_SECONDS = 900


def detect_audio_format(input_path: Path) -> str:
    """Return the lowercase format string derived from the file extension.

    Parameters
    ----------
    input_path:
        Path to an audio file.

    Returns
    -------
    str
        Lowercase format identifier (e.g. ``"mp3"``, ``"wav"``).

    Raises
    ------
    ValueError
        If the extension is empty or maps to an unsupported format.
    """
    suffix = input_path.suffix.lstrip(".").lower()
    if not suffix or suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported audio format '.{suffix}' for {input_path}. "
            f"Supported: {sorted(SUPPORTED_FORMATS)}"
        )
    return suffix


def normalize_audio(
    input_path: Path,
    output_path: Path,
    target_sr: int = 44100,
    channels: int = 1,
    max_duration_seconds: int = DEFAULT_MAX_DURATION_SECONDS,
) -> Path:
    """Normalize an audio file to WAV at the given sample rate and channel count.

    Parameters
    ----------
    input_path:
        Source audio file (MP3, WAV, AIFF, or FLAC).
    output_path:
        Destination path for the normalized WAV file.
    target_sr:
        Target sample rate in Hz (default 44100).
    channels:
        Target channel count (default 1 for mono).
    max_duration_seconds:
        Maximum allowed duration in seconds.  Files exceeding this raise
        ``ValueError``.

    Returns
    -------
    Path
        *output_path* after successful export.

    Raises
    ------
    FileNotFoundError
        If *input_path* does not exist.
    ValueError
        If the format is unsupported or the file exceeds *max_duration_seconds*.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    fmt = detect_audio_format(input_path)

    audio = AudioSegment.from_file(str(input_path), format=fmt)

    # Validate duration.
    duration_seconds = len(audio) / 1000.0
    if duration_seconds > max_duration_seconds:
        raise ValueError(
            f"Audio duration {duration_seconds:.1f}s exceeds maximum "
            f"{max_duration_seconds}s for {input_path}"
        )

    # Convert sample rate.
    if audio.frame_rate != target_sr:
        audio = audio.set_frame_rate(target_sr)

    # Convert channel count.
    if audio.channels != channels:
        audio = audio.set_channels(channels)

    # Export as WAV (16-bit PCM).
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="wav")
    return output_path
