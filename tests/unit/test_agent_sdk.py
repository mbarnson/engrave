"""Tests for Agent SDK provider integration."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engrave.config.settings import RoleConfig
from engrave.llm.agent_sdk import _client_cache, _resolve_model, agent_sdk_complete
from engrave.llm.exceptions import AuthenticationError, ProviderError


class TestModelResolution:
    """Test agent_sdk/ model prefix stripping and alias resolution."""

    def test_strips_prefix(self) -> None:
        assert _resolve_model("agent_sdk/claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"

    def test_resolves_haiku_alias(self) -> None:
        assert _resolve_model("agent_sdk/haiku") == "claude-haiku-4-5-20251001"

    def test_resolves_sonnet_alias(self) -> None:
        assert _resolve_model("agent_sdk/sonnet") == "claude-sonnet-4-6"

    def test_resolves_opus_alias(self) -> None:
        assert _resolve_model("agent_sdk/opus") == "claude-opus-4-6"

    def test_unknown_model_passes_through(self) -> None:
        assert _resolve_model("agent_sdk/claude-future-model") == "claude-future-model"


class TestAgentSdkComplete:
    """Test agent_sdk_complete function."""

    @pytest.fixture
    def role_config(self) -> RoleConfig:
        return RoleConfig(
            model="agent_sdk/haiku",
            max_tokens=1024,
            api_key="sk-ant-test-key",
        )

    @pytest.fixture(autouse=False)
    def mock_anthropic(self):
        """Patch anthropic.AsyncAnthropic and return the mock client."""
        _client_cache.clear()
        with patch("engrave.llm.agent_sdk.anthropic") as mock_mod:
            mock_client = AsyncMock()
            mock_mod.AsyncAnthropic.return_value = mock_client
            mock_mod.NOT_GIVEN = object()
            mock_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})

            # Default response
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = "Generated LilyPond"

            usage = MagicMock()
            usage.input_tokens = 100
            usage.output_tokens = 50

            response = MagicMock()
            response.content = [text_block]
            response.usage = usage

            mock_client.messages.create = AsyncMock(return_value=response)

            yield mock_mod, mock_client

    @pytest.mark.asyncio
    async def test_calls_anthropic_with_api_key(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        mock_mod, mock_client = mock_anthropic
        messages = [{"role": "user", "content": "Fix this LilyPond"}]

        await agent_sdk_complete(
            role_config=role_config,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )

        mock_mod.AsyncAnthropic.assert_called_once_with(api_key="sk-ant-test-key")
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["messages"] == [{"role": "user", "content": "Fix this LilyPond"}]

    @pytest.mark.asyncio
    async def test_oauth_token_creates_bearer_client(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        """OAuth auth_token_override creates client with Bearer header."""
        mock_mod, _mock_client = mock_anthropic

        await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
            auth_token_override="oauth-test-token",
        )

        # Should create client with Bearer auth header
        mock_mod.AsyncAnthropic.assert_called_once_with(
            api_key="oauth",
            default_headers={"Authorization": "Bearer oauth-test-token"},
        )

    @pytest.mark.asyncio
    async def test_oauth_token_takes_priority_over_api_key(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        """When both OAuth token and API key are available, OAuth wins."""
        mock_mod, _mock_client = mock_anthropic

        await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
            auth_token_override="oauth-token",
            api_key_override="sk-ant-key",
        )

        # OAuth token should be used, not the API key
        mock_mod.AsyncAnthropic.assert_called_once_with(
            api_key="oauth",
            default_headers={"Authorization": "Bearer oauth-token"},
        )

    @pytest.mark.asyncio
    async def test_env_auth_token_used_when_no_override(
        self, role_config: RoleConfig, mock_anthropic, monkeypatch
    ) -> None:
        """ANTHROPIC_AUTH_TOKEN env var is used when no override is provided."""
        mock_mod, _mock_client = mock_anthropic
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "env-oauth-token")

        await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
        )

        mock_mod.AsyncAnthropic.assert_called_once_with(
            api_key="oauth",
            default_headers={"Authorization": "Bearer env-oauth-token"},
        )

    @pytest.mark.asyncio
    async def test_returns_text_content(self, role_config: RoleConfig, mock_anthropic) -> None:
        result = await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
        )
        assert result == "Generated LilyPond"

    @pytest.mark.asyncio
    async def test_extracts_system_messages(self, role_config: RoleConfig, mock_anthropic) -> None:
        _mock_mod, mock_client = mock_anthropic
        messages = [
            {"role": "system", "content": "You are a music expert."},
            {"role": "user", "content": "Generate notation"},
        ]

        await agent_sdk_complete(
            role_config=role_config,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are a music expert."
        assert call_kwargs["messages"] == [{"role": "user", "content": "Generate notation"}]

    @pytest.mark.asyncio
    async def test_api_key_override_takes_priority(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        mock_mod, _mock_client = mock_anthropic

        await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
            api_key_override="sk-ant-runtime-key",
        )

        mock_mod.AsyncAnthropic.assert_called_once_with(api_key="sk-ant-runtime-key")

    @pytest.mark.asyncio
    async def test_raises_auth_error_when_no_credential(self) -> None:
        role_config = RoleConfig(model="agent_sdk/haiku", api_key=None)

        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTHROPIC_AUTH_TOKEN is not set
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
            with pytest.raises(AuthenticationError) as exc_info:
                await agent_sdk_complete(
                    role_config=role_config,
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=1024,
                )
        assert exc_info.value.requires_reauth is True
        assert exc_info.value.provider == "agent_sdk"

    @pytest.mark.asyncio
    async def test_raises_auth_error_on_401(self, role_config: RoleConfig, mock_anthropic) -> None:
        mock_mod, mock_client = mock_anthropic
        mock_client.messages.create.side_effect = mock_mod.AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError) as exc_info:
            await agent_sdk_complete(
                role_config=role_config,
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=1024,
            )
        assert exc_info.value.requires_reauth is True

    @pytest.mark.asyncio
    async def test_raises_provider_error_on_other_failure(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        _, mock_client = mock_anthropic
        mock_client.messages.create.side_effect = RuntimeError("Network timeout")

        with pytest.raises(ProviderError) as exc_info:
            await agent_sdk_complete(
                role_config=role_config,
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=1024,
            )
        assert "Network timeout" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_string(
        self, role_config: RoleConfig, mock_anthropic
    ) -> None:
        _, mock_client = mock_anthropic
        mock_client.messages.create.return_value.content = []

        result = await agent_sdk_complete(
            role_config=role_config,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=1024,
        )
        assert result == ""


class TestRouterAgentSdkDispatch:
    """Test InferenceRouter dispatches agent_sdk/ models correctly."""

    @pytest.fixture
    def agent_sdk_settings(self, tmp_path):
        """Settings with an agent_sdk role configured."""
        from tests.conftest import _make_settings_class

        toml_content = """\
[providers.vllm_mlx]
api_base = "http://localhost:8000/v1"

[providers.agent_sdk]
api_key = "sk-ant-test-key"
default_model = "claude-haiku-4-5-20251001"

[roles.compile_fixer]
model = "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
max_tokens = 4096
tags = ["code"]

[roles.generator]
model = "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
max_tokens = 8192
tags = ["code", "lilypond"]

[roles.describer]
model = "anthropic/claude-sonnet-4-20250514"
max_tokens = 2048
tags = ["audio", "description"]

[roles.desktop_fixer]
model = "agent_sdk/haiku"
max_tokens = 4096
tags = ["code", "desktop"]

[lilypond]
min_version = "2.24"
compile_timeout = 60
max_fix_attempts = 5
context_lines = 20

[pipeline]
max_concurrent_groups = 8

[corpus]
embedding_model = "nomic-embed-text"
db_path = "data/corpus_db"
collection_name = "lilypond_phrases"

[audio]
target_sample_rate = 44100
target_channels = 1
max_duration_seconds = 900
supported_formats = ["mp3", "wav", "aiff", "flac"]
"""
        toml_path = tmp_path / "engrave.toml"
        toml_path.write_text(toml_content)
        cls = _make_settings_class(str(toml_path))
        return cls(_env_file=None)

    def test_agent_sdk_role_resolved(self, agent_sdk_settings) -> None:
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(agent_sdk_settings)
        assert "desktop_fixer" in router._roles
        assert router._roles["desktop_fixer"].model == "agent_sdk/haiku"
        assert router._roles["desktop_fixer"].api_key == "sk-ant-test-key"

    @pytest.mark.asyncio
    async def test_dispatches_to_agent_sdk(self, agent_sdk_settings) -> None:
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(agent_sdk_settings)

        with patch("engrave.llm.agent_sdk.agent_sdk_complete", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = "fixed code"
            result = await router.complete(
                role="desktop_fixer",
                messages=[{"role": "user", "content": "fix this"}],
            )

        assert result == "fixed code"
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["role_config"].model == "agent_sdk/haiku"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_runtime_oauth_token_injection(self, agent_sdk_settings) -> None:
        """set_agent_sdk_auth passes OAuth token to agent_sdk_complete."""
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(agent_sdk_settings)
        router.set_agent_sdk_auth("oauth-runtime-token")

        with patch("engrave.llm.agent_sdk.agent_sdk_complete", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = "result"
            await router.complete(
                role="desktop_fixer",
                messages=[{"role": "user", "content": "test"}],
            )

        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["auth_token_override"] == "oauth-runtime-token"

    @pytest.mark.asyncio
    async def test_legacy_runtime_key_injection(self, agent_sdk_settings) -> None:
        """set_agent_sdk_key still works for backwards compatibility."""
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(agent_sdk_settings)
        router.set_agent_sdk_key("sk-ant-runtime")

        with patch("engrave.llm.agent_sdk.agent_sdk_complete", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = "result"
            await router.complete(
                role="desktop_fixer",
                messages=[{"role": "user", "content": "test"}],
            )

        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["api_key_override"] == "sk-ant-runtime"

    @pytest.mark.asyncio
    async def test_existing_litellm_roles_still_work(
        self, agent_sdk_settings, mock_acompletion
    ) -> None:
        """Existing hosted_vllm roles still dispatch via litellm."""
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(agent_sdk_settings)
        await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": "test"}],
        )
        mock_acompletion.assert_called_once()
