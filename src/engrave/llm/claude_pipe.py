"""Claude Code pipe-mode provider.

Shells out to ``claude -p`` (pipe mode) which uses the user's existing
Claude Code authentication.  No API key needed — users run ``claude login``
once and all subsequent calls go through their authenticated session.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import TYPE_CHECKING

from engrave.llm.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from engrave.config.settings import RoleConfig

logger = logging.getLogger(__name__)

_CLAUDE_PIPE_PREFIX = "claude_pipe/"

# Model aliases — allow short names in config
_MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


def _resolve_model(model: str) -> str:
    """Strip ``claude_pipe/`` prefix and resolve aliases.

    ``claude_pipe/haiku`` -> ``claude-haiku-4-5-20251001``
    ``claude_pipe/claude-haiku-4-5-20251001`` -> ``claude-haiku-4-5-20251001``
    """
    bare = model.removeprefix(_CLAUDE_PIPE_PREFIX)
    return _MODEL_ALIASES.get(bare, bare)


def check_claude_installed() -> bool:
    """Return True if ``claude`` is on PATH."""
    return shutil.which("claude") is not None


async def check_claude_authenticated() -> bool:
    """Return True if ``claude`` is logged in.

    Runs ``claude auth status`` and checks for a zero exit code.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "auth",
            "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def claude_pipe_complete(
    role_config: RoleConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    """Send a completion request via ``claude -p`` (pipe mode).

    Builds a single prompt string from the messages list and pipes it
    to ``claude -p --model <model>``.  The response comes back on stdout.

    Args:
        role_config: Resolved role configuration (model, max_tokens).
        messages: Chat messages in OpenAI format (role/content dicts).
        temperature: Sampling temperature (passed to claude via flag).
        max_tokens: Maximum tokens to generate.

    Returns:
        The completion text.

    Raises:
        AuthenticationError: If claude is not installed or not authenticated.
        ProviderError: If the subprocess fails.
    """
    if not check_claude_installed():
        raise AuthenticationError(
            "claude_pipe",
            role_config.model,
            FileNotFoundError(
                "Claude Code CLI not found. "
                "Install with: npm install -g @anthropic-ai/claude-code\n"
                "Then run: claude login"
            ),
        )

    model_id = _resolve_model(role_config.model)

    # Build prompt from messages.
    # System messages become a preamble, user/assistant messages follow.
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"[Previous response]\n{content}")
        else:
            parts.append(content)

    prompt = "\n\n".join(parts)

    cmd = [
        "claude",
        "-p",
        "--model",
        model_id,
        "--max-tokens",
        str(max_tokens),
    ]

    logger.info("claude_pipe: model=%s, prompt_len=%d", model_id, len(prompt))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=120,
        )
    except FileNotFoundError as e:
        raise AuthenticationError(
            "claude_pipe",
            role_config.model,
            FileNotFoundError(
                "Claude Code CLI not found. "
                "Install with: npm install -g @anthropic-ai/claude-code\n"
                "Then run: claude login"
            ),
        ) from e
    except TimeoutError as e:
        raise ProviderError(
            "claude_pipe",
            role_config.model,
            TimeoutError("claude -p timed out after 120 seconds"),
        ) from e

    if proc.returncode != 0:
        stderr_text = stderr.decode(errors="replace").strip()
        # Check for authentication-related failures
        if "auth" in stderr_text.lower() or "login" in stderr_text.lower():
            raise AuthenticationError(
                "claude_pipe",
                role_config.model,
                RuntimeError(f"Claude Code not authenticated. Run: claude login\n{stderr_text}"),
            )
        raise ProviderError(
            "claude_pipe",
            role_config.model,
            RuntimeError(f"claude -p exited with code {proc.returncode}: {stderr_text}"),
        )

    result = stdout.decode(errors="replace").strip()

    if not result:
        logger.warning("claude_pipe returned empty response for model '%s'", model_id)
        return ""

    logger.debug("claude_pipe response length: %d chars", len(result))
    return result
