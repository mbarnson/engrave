"""InferenceRouter wrapping LiteLLM with role-based dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from engrave.config.roles import validate_and_resolve_roles
from engrave.llm.exceptions import ProviderError, RoleNotFoundError

if TYPE_CHECKING:
    from engrave.config.settings import RoleConfig, Settings

logger = logging.getLogger(__name__)

_AGENT_SDK_PREFIX = "agent_sdk/"


def _inject_no_think(messages: list[dict]) -> list[dict]:
    """Append '/no_think' to the last user message.

    Qwen3 chat templates recognise this suffix as a signal to skip the
    ``<think>`` reasoning block and produce content directly.  Without it
    vllm-mlx returns ``content: null`` with only 1 completion token.

    A shallow copy of the messages list is returned so the caller's
    original is not mutated.
    """
    msgs = [m.copy() for m in messages]
    for msg in reversed(msgs):
        if msg.get("role") == "user":
            text = msg.get("content", "")
            if isinstance(text, str) and "/no_think" not in text:
                msg["content"] = text.rstrip() + " /no_think"
            break
    return msgs


class InferenceRouter:
    """Route LLM calls by pipeline role, not provider.

    Resolves role names (e.g., 'compile_fixer') to provider+model
    combinations via config, then dispatches to LiteLLM.

    Fail-don't-fallback: if the configured provider fails, the error
    is raised immediately. No silent fallback to another provider.
    """

    def __init__(self, settings: Settings) -> None:
        self._roles: dict[str, RoleConfig] = validate_and_resolve_roles(
            settings.roles, settings.providers
        )
        self._agent_sdk_auth_token: str | None = None
        self._agent_sdk_key: str | None = None

    def set_agent_sdk_auth(self, auth_token: str) -> None:
        """Inject an OAuth bearer token for the agent_sdk provider at runtime.

        Called by the Tauri frontend after the user completes the OAuth flow.
        This token takes priority over config/env values for all
        ``agent_sdk/`` model requests.
        """
        self._agent_sdk_auth_token = auth_token
        logger.info("Agent SDK OAuth token updated at runtime")

    def set_agent_sdk_key(self, api_key: str) -> None:
        """Inject an API key for the agent_sdk provider at runtime.

        Legacy method for backwards compatibility. Prefer
        :meth:`set_agent_sdk_auth` with OAuth tokens.
        """
        self._agent_sdk_key = api_key
        logger.info("Agent SDK API key updated at runtime (legacy)")

    async def complete(
        self,
        role: str,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> str:
        """Send completion request for a given pipeline role.

        Args:
            role: Pipeline role name (e.g., 'compile_fixer', 'generator').
            messages: Chat messages in OpenAI format.
            temperature: Sampling temperature (default 0.3 for deterministic output).
            max_tokens: Override max tokens from role config.

        Returns:
            The completion text from the model.

        Raises:
            RoleNotFoundError: If the role is not in config.
            ProviderError: If the provider fails (wraps the original exception).
        """
        import litellm

        if role not in self._roles:
            raise RoleNotFoundError(role, list(self._roles.keys()))

        role_config = self._roles[role]
        model = role_config.model
        provider = model.split("/")[0] if "/" in model else "unknown"

        logger.info("Routing role '%s' to model '%s'", role, model)

        # Dispatch agent_sdk/ models to the Anthropic SDK directly.
        if model.startswith(_AGENT_SDK_PREFIX):
            from engrave.llm.agent_sdk import agent_sdk_complete

            return await agent_sdk_complete(
                role_config=role_config,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or role_config.max_tokens,
                auth_token_override=self._agent_sdk_auth_token,
                api_key_override=self._agent_sdk_key,
            )

        try:
            # Disable thinking mode for Qwen3 models served via vllm-mlx.
            # vllm-mlx ignores the enable_thinking API parameter, so we
            # inject "/no_think" into the last user message content.  This
            # is the Qwen3 chat-template convention that suppresses the
            # <think> block and returns content directly.
            effective_messages = messages
            if "qwen3" in model.lower() or "hosted_vllm/" in model:
                effective_messages = _inject_no_think(messages)

            response = await litellm.acompletion(
                model=model,
                messages=effective_messages,
                temperature=temperature,
                max_tokens=max_tokens or role_config.max_tokens,
                api_base=role_config.api_base,
                api_key=role_config.api_key,
                num_retries=0,  # Fail, don't fallback -- user decision
            )
            # Log token usage for prefix cache observability
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tok = getattr(usage, "prompt_tokens", 0)
                compl_tok = getattr(usage, "completion_tokens", 0)
                cached_tok = getattr(usage, "prompt_tokens_details", None)
                cached_str = ""
                if cached_tok and hasattr(cached_tok, "cached_tokens"):
                    cached_str = f", cached={cached_tok.cached_tokens}"
                logger.debug(
                    "Usage for '%s': prompt=%d, completion=%d%s",
                    role,
                    prompt_tok,
                    compl_tok,
                    cached_str,
                )

            content = response.choices[0].message.content
            if content is None:
                logger.warning(
                    "Model '%s' returned null content for role '%s'; returning empty string",
                    model,
                    role,
                )
                return ""
            return content
        except Exception as e:
            raise ProviderError(provider, model, e) from e
