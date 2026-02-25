"""Shared test fixtures for Engrave."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

if TYPE_CHECKING:
    from engrave.config.settings import Settings


MINIMAL_TOML = """\
[providers.lm_studio]
api_base = "http://localhost:1234/v1"

[roles.compile_fixer]
model = "lm_studio/qwen3-coder-next"
max_tokens = 4096
min_context_window = 32000
tags = ["code"]

[roles.generator]
model = "lm_studio/qwen3-coder-next"
max_tokens = 8192
tags = ["code", "lilypond"]

[roles.describer]
model = "anthropic/claude-sonnet-4-20250514"
max_tokens = 2048
tags = ["audio", "description"]

[lilypond]
min_version = "2.24"
compile_timeout = 60
max_fix_attempts = 5
context_lines = 20

[corpus]
embedding_model = "nomic-embed-text"
db_path = "data/corpus_db"
collection_name = "lilypond_phrases"
"""


def _make_settings_class(toml_path: str) -> type:
    """Create a Settings subclass that loads from a specific TOML path."""
    from engrave.config.settings import Settings

    class TestSettings(Settings):
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
            toml_settings = TomlConfigSettingsSource(settings_cls, toml_file=toml_path)
            return (
                init_settings,
                env_settings,
                dotenv_settings,
                toml_settings,
                file_secret_settings,
            )

    return TestSettings


@pytest.fixture
def tmp_engrave_toml(tmp_path: Path) -> Path:
    """Write a minimal engrave.toml to tmp_path and return its path."""
    toml_path = tmp_path / "engrave.toml"
    toml_path.write_text(MINIMAL_TOML)
    return toml_path


@pytest.fixture
def settings(tmp_engrave_toml: Path) -> Settings:
    """Load Settings from the tmp engrave.toml."""
    cls = _make_settings_class(str(tmp_engrave_toml))
    return cls(_env_file=None)


@pytest.fixture
def mock_acompletion():
    """Patch litellm.acompletion and return the mock."""
    mock = AsyncMock()
    # Default: return a simple completion response
    mock.return_value.choices = [AsyncMock(message=AsyncMock(content="Test response"))]
    with patch("litellm.acompletion", mock):
        yield mock


@pytest.fixture
def mock_compiler():
    """Mock LilyPondCompiler with configurable compile() responses.

    Default: returns a successful compilation result.
    Override compile.return_value or compile.side_effect in tests.
    """
    from engrave.lilypond.compiler import RawCompileResult

    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


@pytest.fixture
def mock_router():
    """Mock InferenceRouter with configurable complete() responses.

    Default: returns a simple fixed LilyPond source.
    Override complete.return_value or complete.side_effect in tests.
    """
    router = AsyncMock()
    router.complete.return_value = '\\version "2.24.4"\n\\relative c\' { c4 d e f | g2 g | }\n'
    return router


# ---------------------------------------------------------------------------
# Corpus fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def corpus_config(tmp_path: Path):
    """Return a CorpusConfig pointing at a temp directory."""
    from engrave.config.settings import CorpusConfig

    return CorpusConfig(
        embedding_model="all-MiniLM-L6-v2",
        db_path=str(tmp_path / "test_corpus_db"),
        collection_name="test_phrases",
    )


@pytest.fixture
def corpus_store(corpus_config):
    """Return a CorpusStore backed by an in-memory ChromaDB client."""
    import chromadb

    from engrave.corpus.store import CorpusStore

    client = chromadb.Client()
    return CorpusStore(config=corpus_config, client=client)
