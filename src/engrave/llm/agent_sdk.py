"""Anthropic API provider via the anthropic Python SDK.

Handles completion requests for ``agent_sdk/`` prefixed models.  Authentication
uses OAuth bearer tokens (from the desktop app's OAuth PKCE flow) or falls back
to API keys for headless/CI usage.

Priority chain for credentials:
1. ``auth_token_override`` (runtime injection from Tauri OAuth flow)
2. ``ANTHROPIC_AUTH_TOKEN`` environment variable
3. ``api_key_override`` (runtime injection, legacy)
4. ``role_config.api_key`` (config/env, legacy)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import anthropic

from engrave.llm.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from engrave.config.settings import RoleConfig

logger = logging.getLogger(__name__)


_client_cache: dict[int, anthropic.AsyncAnthropic] = {}


def _get_client(
    *,
    auth_token: str | None = None,
    api_key: str | None = None,
) -> anthropic.AsyncAnthropic:
    """Return a cached AsyncAnthropic client.

    Uses OAuth bearer token if available, otherwise falls back to API key.
    Cache is keyed on hash of the credential to avoid retaining plaintext.
    """
    if auth_token:
        cache_key = hash(("bearer", auth_token))
        if cache_key not in _client_cache:
            while len(_client_cache) >= 4:
                _client_cache.pop(next(iter(_client_cache)))
            _client_cache[cache_key] = anthropic.AsyncAnthropic(
                api_key="oauth",
                default_headers={"Authorization": f"Bearer {auth_token}"},
            )
        return _client_cache[cache_key]

    if api_key:
        cache_key = hash(("apikey", api_key))
        if cache_key not in _client_cache:
            while len(_client_cache) >= 4:
                _client_cache.pop(next(iter(_client_cache)))
            _client_cache[cache_key] = anthropic.AsyncAnthropic(api_key=api_key)
        return _client_cache[cache_key]

    raise ValueError("No auth_token or api_key provided")


# Anthropic model aliases — allow short names in config
_MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
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
    auth_token_override: str | None = None,
    api_key_override: str | None = None,
) -> str:
    """Send a completion request via the Anthropic Python SDK.

    Args:
        role_config: Resolved role configuration (model, api_key, max_tokens).
        messages: Chat messages in OpenAI format (role/content dicts).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.
        auth_token_override: OAuth bearer token from Tauri desktop OAuth flow.
            Highest priority credential.
        api_key_override: Legacy API key override for backwards compatibility.

    Returns:
        The completion text.

    Raises:
        AuthenticationError: If no credential is available or is rejected.
        ProviderError: If the API call fails for other reasons.
    """
    # Resolve credential with priority chain
    auth_token = auth_token_override or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    api_key = api_key_override or role_config.api_key
    model_id = _resolve_model(role_config.model)

    if not auth_token and not api_key:
        raise AuthenticationError(
            "agent_sdk",
            role_config.model,
            ValueError(
                "No OAuth token or API key configured for agent_sdk provider. "
                "Sign in with Claude in the desktop app, or set "
                "ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY env var."
            ),
        )

    try:
        client = _get_client(auth_token=auth_token, api_key=api_key)
    except ValueError as e:
        raise AuthenticationError("agent_sdk", role_config.model, e) from e

    if auth_token:
        logger.debug("Using OAuth bearer token for agent_sdk request")
    else:
        logger.debug("Using API key for agent_sdk request (legacy)")

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
        text_parts = [block.text for block in response.content if block.type == "text"]
        return "\n".join(text_parts) if text_parts else ""

    except anthropic.AuthenticationError as e:
        raise AuthenticationError("agent_sdk", role_config.model, e) from e
    except Exception as e:
        raise ProviderError("agent_sdk", role_config.model, e) from e
