"""Audio input pipeline -- format normalization, source separation, transcription, and description."""

from engrave.audio.describer import Describer, GeminiDescriber, create_describer
from engrave.audio.description import AudioDescription, SectionDescription
from engrave.audio.normalizer import normalize_audio
from engrave.audio.pipeline import AudioPipeline, JobResult, StemResult
from engrave.audio.quality import StemQuality, annotate_quality
from engrave.audio.templates import (
    render_full_description,
    render_section_description,
    render_track_summary,
)
from engrave.audio.youtube import extract_youtube_audio

__all__: list[str] = [
    "AudioDescription",
    "AudioPipeline",
    "Describer",
    "GeminiDescriber",
    "JobResult",
    "SectionDescription",
    "StemQuality",
    "StemResult",
    "annotate_quality",
    "create_describer",
    "extract_youtube_audio",
    "normalize_audio",
    "render_full_description",
    "render_section_description",
    "render_track_summary",
]
