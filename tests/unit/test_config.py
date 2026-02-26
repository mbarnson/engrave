"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from engrave.config.roles import validate_and_resolve_roles
from engrave.config.settings import Settings


class TestSettingsLoading:
    """Test Settings loads from engrave.toml."""

    def test_loads_from_toml(self, settings: Settings) -> None:
        """Settings loads providers and roles from engrave.toml."""
        assert settings.providers.vllm_mlx.api_base == "http://localhost:8000/v1"
        assert "compile_fixer" in settings.roles
        assert "generator" in settings.roles
        assert "describer" in settings.roles

    def test_role_configs_populated(self, settings: Settings) -> None:
        """Role configs have model and tags."""
        fixer = settings.roles["compile_fixer"]
        assert fixer.model == "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
        assert fixer.tags == ["code"]

        describer = settings.roles["describer"]
        assert describer.model == "anthropic/claude-sonnet-4-20250514"
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

    def test_resolve_vllm_mlx_provider(self, settings: Settings) -> None:
        """vllm-mlx roles get api_base from provider config."""
        resolved = validate_and_resolve_roles(settings.roles, settings.providers)
        fixer = resolved["compile_fixer"]
        assert fixer.api_base == "http://localhost:8000/v1"

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
