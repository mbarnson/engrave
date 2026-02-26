"""Pydantic-settings models loading engrave.toml + .env."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider endpoint."""

    api_base: str | None = None
    api_key: str | None = None


class ProvidersConfig(BaseModel):
    """All provider configurations."""

    lm_studio: ProviderConfig = ProviderConfig()
    vllm_mlx: ProviderConfig = ProviderConfig()
    runpod: ProviderConfig = ProviderConfig()
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


class RoleConfig(BaseModel):
    """Configuration for a pipeline role mapping to a provider+model."""

    model: str
    max_tokens: int = 4096
    tags: list[str] = []
    # Resolved from provider config during validation
    api_base: str | None = None
    api_key: str | None = None


class LilyPondConfig(BaseModel):
    """LilyPond compilation settings."""

    min_version: str = "2.24"
    compile_timeout: int = 60
    max_fix_attempts: int = 5
    context_lines: int = 20


class SeparationStep(BaseModel):
    """A single step in a hierarchical source separation cascade."""

    model: str
    input_stem: str = "mix"
    output_stems: list[str]


class SeparationConfig(BaseModel):
    """Source separation pipeline configuration."""

    steps: list[SeparationStep] = []

    @classmethod
    def default_steps(cls) -> SeparationConfig:
        """Return a big band default cascade.

        1. htdemucs_ft splits the mix into drums, bass, vocals, other.
        2. bs_roformer isolates piano from the 'other' residual.
        """
        return cls(
            steps=[
                SeparationStep(
                    model="htdemucs_ft",
                    input_stem="mix",
                    output_stems=["drums", "bass", "vocals", "other"],
                ),
                SeparationStep(
                    model="bs_roformer",
                    input_stem="other",
                    output_stems=["piano", "residual"],
                ),
            ]
        )


class TranscriptionConfig(BaseModel):
    """Audio-to-MIDI transcription settings."""

    backend: str = "basic_pitch"
    venv_python: str | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    minimum_note_length_ms: int = 58


class BenchmarkConfig(BaseModel):
    """Benchmark harness configuration."""

    soundfont_path: str | None = None
    onset_tolerance: float = 0.05
    results_dir: str = "data/benchmark_results"


class DescriberConfig(BaseModel):
    """Audio LM describer configuration.

    Controls the audio description backend that sends audio to an LLM
    for structured musical analysis.  Read from ``[audio.describer]``
    in engrave.toml.
    """

    model: str = "gemini/gemini-3-flash"
    """LiteLLM model identifier for the audio LM backend."""

    timeout: int = 120
    """Request timeout in seconds."""

    max_file_size_mb: int = 15
    """Threshold above which audio is downsampled to 16 kHz before sending."""

    max_retries: int = 1
    """Retries on validation failure before returning minimal defaults."""


class AudioConfig(BaseModel):
    """Audio input pipeline configuration.

    Controls format normalization, source separation, transcription,
    description (audio LM), and benchmark harness settings.
    Read from ``[audio]`` in engrave.toml.
    """

    target_sample_rate: int = 44100
    target_channels: int = 1
    max_duration_seconds: int = 900
    supported_formats: list[str] = ["mp3", "wav", "aiff", "flac"]
    separation: SeparationConfig = SeparationConfig()
    transcription: TranscriptionConfig = TranscriptionConfig()
    describer: DescriberConfig = DescriberConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()


class CorpusConfig(BaseModel):
    """Corpus storage and embedding configuration.

    Read from the ``[corpus]`` section of ``engrave.toml``.
    """

    embedding_model: str = "nomic-embed-text"
    db_path: str = "data/corpus_db"
    collection_name: str = "lilypond_phrases"


class Settings(BaseSettings):
    """Application settings loaded from engrave.toml + .env with env var override.

    Priority chain: env vars > .env > TOML > defaults
    """

    providers: ProvidersConfig = ProvidersConfig()
    roles: dict[str, RoleConfig] = {}
    lilypond: LilyPondConfig = LilyPondConfig()
    corpus: CorpusConfig = CorpusConfig()
    audio: AudioConfig = AudioConfig()

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="ENGRAVE_",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        **kwargs: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include TOML config.

        Priority (highest to lowest):
        1. Init kwargs
        2. Environment variables
        3. .env file
        4. TOML file (engrave.toml)
        5. Defaults
        """
        toml_path = str(PROJECT_ROOT / "engrave.toml")
        toml_settings = TomlConfigSettingsSource(settings_cls, toml_file=toml_path)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_settings,
            file_secret_settings,
        )
