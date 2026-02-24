"""Shared test fixtures for Engrave."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

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
