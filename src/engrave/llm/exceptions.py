"""Provider-agnostic exceptions for LLM routing."""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when an LLM provider fails to complete a request.

    Wraps the original exception with provider and model context.
    Never silently falls back to another provider.
    """

    def __init__(self, provider: str, model: str, original_error: Exception) -> None:
        self.provider = provider
        self.model = model
        self.original_error = original_error
        super().__init__(f"Provider '{provider}' failed for model '{model}': {original_error}")


class RoleNotFoundError(Exception):
    """Raised when a requested pipeline role is not configured.

    Includes the requested role name and available roles for diagnostics.
    """

    def __init__(self, role: str, available_roles: list[str]) -> None:
        self.role = role
        self.available_roles = available_roles
        super().__init__(
            f"Role '{role}' not found in config. "
            f"Available roles: {', '.join(sorted(available_roles))}"
        )
