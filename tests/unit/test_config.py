"""Tests for configuration loading and validation."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from engrave.config.roles import validate_and_resolve_roles
from engrave.config.settings import Settings


class TestSettingsLoading:
    """Test Settings loads from engrave.toml."""

    def test_loads_from_toml(self, settings: Settings) -> None:
        """Settings loads providers and roles from engrave.toml."""
        assert settings.providers.lm_studio.api_base == "http://localhost:1234/v1"
        assert "compile_fixer" in settings.roles
        assert "generator" in settings.roles
        assert "describer" in settings.roles

    def test_role_configs_populated(self, settings: Settings) -> None:
        """Role configs have model, max_tokens, and tags."""
        fixer = settings.roles["compile_fixer"]
        assert fixer.model == "lm_studio/qwen3-coder-next"
        assert fixer.max_tokens == 4096
        assert fixer.tags == ["code"]

        describer = settings.roles["describer"]
        assert describer.model == "anthropic/claude-sonnet-4-20250514"
        assert describer.max_tokens == 2048
        assert describer.tags == ["audio", "description"]

    def test_lilypond_config(self, settings: Settings) -> None:
        """LilyPond config loads from TOML."""
        assert settings.lilypond.min_version == "2.24"
        assert settings.lilypond.compile_timeout == 60
        assert settings.lilypond.max_fix_attempts == 5
        assert settings.lilypond.context_lines == 20

    def test_env_override(self, tmp_engrave_toml: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables override TOML values."""
        monkeypatch.setenv("ENGRAVE_PROVIDERS__ANTHROPIC_API_KEY", "sk-test-key-123")
        from tests.conftest import _make_settings_class

        cls = _make_settings_class(str(tmp_engrave_toml))
        s = cls(_env_file=None)
        assert s.providers.anthropic_api_key == "sk-test-key-123"

    def test_missing_toml_uses_defaults(self, tmp_path: Path) -> None:
        """Missing TOML file uses defaults without error."""
        from tests.conftest import _make_settings_class

        nonexistent = str(tmp_path / "nonexistent.toml")
        cls = _make_settings_class(nonexistent)
        s = cls(_env_file=None)
        assert s.roles == {}
        assert s.providers.lm_studio.api_base is None
        assert s.lilypond.compile_timeout == 60


class TestRoleValidation:
    """Test role resolution and validation."""

    def test_resolve_lm_studio_provider(self, settings: Settings) -> None:
        """LM Studio roles get api_base from provider config."""
        resolved = validate_and_resolve_roles(settings.roles, settings.providers)
        fixer = resolved["compile_fixer"]
        assert fixer.api_base == "http://localhost:1234/v1"

    def test_resolve_anthropic_api_key(
        self, tmp_engrave_toml: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anthropic roles get api_key from provider config."""
        monkeypatch.setenv("ENGRAVE_PROVIDERS__ANTHROPIC_API_KEY", "sk-ant-test")
        from tests.conftest import _make_settings_class

        cls = _make_settings_class(str(tmp_engrave_toml))
        s = cls(_env_file=None)
        resolved = validate_and_resolve_roles(s.roles, s.providers)
        describer = resolved["describer"]
        assert describer.api_key == "sk-ant-test"

    def test_warns_on_insufficient_context_window(self, settings: Settings) -> None:
        """Warn if model context window is below role minimum."""
        # The lm_studio/ prefix estimates 32000 tokens,
        # set min_context_window to 64000 to trigger warning
        settings.roles["compile_fixer"].min_context_window = 64000
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate_and_resolve_roles(settings.roles, settings.providers)
            context_warnings = [x for x in w if "context window" in str(x.message)]
            assert len(context_warnings) >= 1
            assert "compile_fixer" in str(context_warnings[0].message)
