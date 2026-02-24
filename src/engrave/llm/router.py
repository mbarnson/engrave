"""InferenceRouter wrapping LiteLLM with role-based dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from engrave.config.roles import validate_and_resolve_roles
from engrave.llm.exceptions import ProviderError, RoleNotFoundError

if TYPE_CHECKING:
    from engrave.config.settings import RoleConfig, Settings

logger = logging.getLogger(__name__)


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

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or role_config.max_tokens,
                api_base=role_config.api_base,
                api_key=role_config.api_key,
                num_retries=0,  # Fail, don't fallback -- user decision
            )
            return response.choices[0].message.content
        except Exception as e:
            raise ProviderError(provider, model, e) from e
