"""Role-to-model resolution with validation."""

from __future__ import annotations

import logging

from engrave.config.settings import ProvidersConfig, RoleConfig

logger = logging.getLogger(__name__)


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
    elif model.startswith("hosted_vllm/"):
        role_config.api_base = role_config.api_base or providers.vllm_mlx.api_base
        role_config.api_key = role_config.api_key or providers.vllm_mlx.api_key
    elif model.startswith("anthropic/"):
        role_config.api_key = role_config.api_key or providers.anthropic_api_key
    elif model.startswith("openai/"):
        role_config.api_key = role_config.api_key or providers.openai_api_key
    elif model.startswith("runpod/"):
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
    2. Log the resolved configuration

    Returns the roles dict with resolved provider details.
    """
    resolved: dict[str, RoleConfig] = {}

    for role_name, role_config in roles.items():
        # Resolve provider details
        role_config = _resolve_provider_for_role(role_config, providers)

        logger.debug(
            "Role '%s' resolved: model=%s, api_base=%s, max_tokens=%d",
            role_name,
            role_config.model,
            role_config.api_base,
            role_config.max_tokens,
        )

        resolved[role_name] = role_config

    return resolved
