"""Role-to-model resolution with validation."""

from __future__ import annotations

import logging
import warnings

from engrave.config.settings import ProvidersConfig, RoleConfig

logger = logging.getLogger(__name__)

# Known context window sizes for common model prefixes (conservative estimates).
# Used for validation only -- not authoritative.
KNOWN_CONTEXT_WINDOWS: dict[str, int] = {
    "anthropic/claude-sonnet-4": 200_000,
    "anthropic/claude-opus-4": 200_000,
    "openai/gpt-4o": 128_000,
    "openai/gpt-4.1": 1_000_000,
    "lm_studio/": 32_000,  # conservative default for local models
}


def _estimate_context_window(model: str) -> int | None:
    """Estimate context window for a model string based on known prefixes."""
    for prefix, window in KNOWN_CONTEXT_WINDOWS.items():
        if model.startswith(prefix):
            return window
    return None


def _resolve_provider_for_role(
    role_config: RoleConfig,
    providers: ProvidersConfig,
) -> RoleConfig:
    """Resolve api_base and api_key from provider config into a role config.

    Examines the model string prefix to determine which provider to use,
    then copies the relevant api_base and api_key into the role config.
    """
    model = role_config.model

    if model.startswith("lm_studio/"):
        role_config.api_base = role_config.api_base or providers.lm_studio.api_base
        role_config.api_key = role_config.api_key or providers.lm_studio.api_key
    elif model.startswith("anthropic/"):
        role_config.api_key = role_config.api_key or providers.anthropic_api_key
    elif model.startswith("openai/"):
        role_config.api_key = role_config.api_key or providers.openai_api_key
    elif model.startswith("hosted_vllm/") or model.startswith("runpod/"):
        role_config.api_base = role_config.api_base or providers.runpod.api_base
        role_config.api_key = role_config.api_key or providers.runpod.api_key

    return role_config


def validate_and_resolve_roles(
    roles: dict[str, RoleConfig],
    providers: ProvidersConfig,
) -> dict[str, RoleConfig]:
    """Validate role configs and resolve provider details.

    For each role:
    1. Resolve api_base/api_key from the matching provider config
    2. Warn if the model's estimated context window is below the role's min_context_window
    3. Log the resolved configuration

    Returns the roles dict with resolved provider details.
    """
    resolved: dict[str, RoleConfig] = {}

    for role_name, role_config in roles.items():
        # Resolve provider details
        role_config = _resolve_provider_for_role(role_config, providers)

        # Validate context window
        estimated = _estimate_context_window(role_config.model)
        if estimated is not None and estimated < role_config.min_context_window:
            warnings.warn(
                f"Role '{role_name}': model '{role_config.model}' has estimated context "
                f"window {estimated:,} tokens, below minimum {role_config.min_context_window:,}",
                stacklevel=2,
            )

        logger.debug(
            "Role '%s' resolved: model=%s, api_base=%s, max_tokens=%d",
            role_name,
            role_config.model,
            role_config.api_base,
            role_config.max_tokens,
        )

        resolved[role_name] = role_config

    return resolved
