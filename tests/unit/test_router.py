"""Tests for InferenceRouter dispatch and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engrave.llm.exceptions import ProviderError, RoleNotFoundError
from engrave.llm.router import InferenceRouter


@pytest.fixture
def router(settings):
    """Create an InferenceRouter from test settings."""
    return InferenceRouter(settings)


class TestRouterResolution:
    """Test router resolves roles to correct model strings."""

    def test_resolves_role_to_model(self, router: InferenceRouter) -> None:
        """Router has all configured roles with correct models."""
        assert "compile_fixer" in router._roles
        assert router._roles["compile_fixer"].model == "lm_studio/qwen3-coder-next"

    def test_resolves_api_base_for_local_provider(self, router: InferenceRouter) -> None:
        """Local providers get api_base from provider config."""
        fixer = router._roles["compile_fixer"]
        assert fixer.api_base == "http://localhost:1234/v1"

    def test_cloud_provider_has_no_api_base(self, router: InferenceRouter) -> None:
        """Cloud providers (anthropic) have None api_base."""
        describer = router._roles["describer"]
        assert describer.api_base is None


class TestRouterCompletion:
    """Test router calls acompletion with correct parameters."""

    @pytest.mark.asyncio
    async def test_calls_acompletion_with_correct_params(
        self, router: InferenceRouter, mock_acompletion: AsyncMock
    ) -> None:
        """Router passes model, messages, temperature, max_tokens to acompletion."""
        messages = [{"role": "user", "content": "test"}]
        await router.complete(role="compile_fixer", messages=messages, temperature=0.1)

        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["model"] == "lm_studio/qwen3-coder-next"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 4096  # from role config
        assert call_kwargs["api_base"] == "http://localhost:1234/v1"
        assert call_kwargs["num_retries"] == 0

    @pytest.mark.asyncio
    async def test_returns_completion_content(
        self, router: InferenceRouter, mock_acompletion: AsyncMock
    ) -> None:
        """Router returns the text content from the completion response."""
        mock_acompletion.return_value.choices = [
            MagicMock(message=MagicMock(content="fixed code here"))
        ]
        result = await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": "fix this"}],
        )
        assert result == "fixed code here"

    @pytest.mark.asyncio
    async def test_max_tokens_override(
        self, router: InferenceRouter, mock_acompletion: AsyncMock
    ) -> None:
        """Explicit max_tokens overrides role config default."""
        await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )
        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["max_tokens"] == 100


class TestRouterErrors:
    """Test router error handling."""

    @pytest.mark.asyncio
    async def test_raises_role_not_found_for_unknown_role(self, router: InferenceRouter) -> None:
        """Unknown role raises RoleNotFoundError with available roles."""
        with pytest.raises(RoleNotFoundError) as exc_info:
            await router.complete(
                role="nonexistent_role",
                messages=[{"role": "user", "content": "test"}],
            )
        assert exc_info.value.role == "nonexistent_role"
        assert "compile_fixer" in exc_info.value.available_roles

    @pytest.mark.asyncio
    async def test_raises_provider_error_on_acompletion_failure(
        self, router: InferenceRouter, mock_acompletion: AsyncMock
    ) -> None:
        """Provider failures are wrapped in ProviderError."""
        mock_acompletion.side_effect = Exception("Connection refused")

        with pytest.raises(ProviderError) as exc_info:
            await router.complete(
                role="compile_fixer",
                messages=[{"role": "user", "content": "test"}],
            )
        assert exc_info.value.provider == "lm_studio"
        assert exc_info.value.model == "lm_studio/qwen3-coder-next"
        assert "Connection refused" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_cloud_provider_passes_none_api_base(
        self, router: InferenceRouter, mock_acompletion: AsyncMock
    ) -> None:
        """Cloud provider (anthropic) passes None for api_base."""
        await router.complete(
            role="describer",
            messages=[{"role": "user", "content": "describe this"}],
        )
        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["api_base"] is None
        assert call_kwargs["model"] == "anthropic/claude-sonnet-4-20250514"
