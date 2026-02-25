"""Audio input pipeline -- format normalization, source separation, and transcription."""

from engrave.audio.normalizer import normalize_audio
from engrave.audio.pipeline import AudioPipeline, JobResult, StemResult
from engrave.audio.quality import StemQuality, annotate_quality
from engrave.audio.youtube import extract_youtube_audio

__all__: list[str] = [
    "AudioPipeline",
    "JobResult",
    "StemQuality",
    "StemResult",
    "annotate_quality",
    "extract_youtube_audio",
    "normalize_audio",
]
