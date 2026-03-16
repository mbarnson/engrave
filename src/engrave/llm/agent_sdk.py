"""Anthropic API provider via the anthropic Python SDK.

Handles completion requests for ``agent_sdk/`` prefixed models.  The API key
can come from config, environment, or runtime injection (desktop app token
exchange).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anthropic

from engrave.llm.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from engrave.config.settings import RoleConfig

logger = logging.getLogger(__name__)

# Anthropic model aliases — allow short names in config
_MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}


def _resolve_model(model: str) -> str:
    """Strip ``agent_sdk/`` prefix and resolve aliases.

    ``agent_sdk/haiku`` -> ``claude-haiku-4-5-20251001``
    ``agent_sdk/claude-haiku-4-5-20251001`` -> ``claude-haiku-4-5-20251001``
    """
    bare = model.removeprefix("agent_sdk/")
    return _MODEL_ALIASES.get(bare, bare)


async def agent_sdk_complete(
    role_config: RoleConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    api_key_override: str | None = None,
) -> str:
    """Send a completion request via the Anthropic Python SDK.

    Args:
        role_config: Resolved role configuration (model, api_key, max_tokens).
        messages: Chat messages in OpenAI format (role/content dicts).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.
        api_key_override: Runtime API key (e.g., from Tauri frontend token exchange).
            Takes priority over role_config.api_key.

    Returns:
        The completion text.

    Raises:
        AuthenticationError: If the API key is missing or rejected.
        ProviderError: If the API call fails for other reasons.
    """
    api_key = api_key_override or role_config.api_key
    model_id = _resolve_model(role_config.model)

    if not api_key:
        raise AuthenticationError(
            "agent_sdk",
            role_config.model,
            ValueError("No API key configured for agent_sdk provider. "
                        "Set providers.agent_sdk.api_key in engrave.toml, "
                        "ENGRAVE_PROVIDERS__AGENT_SDK__API_KEY env var, "
                        "or call set_agent_sdk_key() at runtime."),
        )

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Convert OpenAI-format messages to Anthropic format.
    # Anthropic Messages API uses a separate `system` parameter.
    system_parts: list[str] = []
    api_messages: list[dict] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_parts.append(msg.get("content", ""))
        else:
            api_messages.append({"role": msg["role"], "content": msg.get("content", "")})

    try:
        response = await client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system="\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN,
            messages=api_messages,
        )

        # Log token usage
        if response.usage:
            logger.debug(
                "Agent SDK usage for '%s': input=%d, output=%d",
                model_id,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

        # Extract text content from the response
        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        return "\n".join(text_parts) if text_parts else ""

    except anthropic.AuthenticationError as e:
        raise AuthenticationError("agent_sdk", role_config.model, e) from e
    except Exception as e:
        raise ProviderError("agent_sdk", role_config.model, e) from e
