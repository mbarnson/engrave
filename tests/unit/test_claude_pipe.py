"""Tests for Claude Code pipe-mode provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engrave.config.settings import RoleConfig
from engrave.llm.claude_pipe import _resolve_model, claude_pipe_complete
from engrave.llm.exceptions import AuthenticationError, ProviderError


def _make_mock_proc(returncode: int, stdout: bytes, stderr: bytes):
    """Create a mock subprocess that returns given stdout/stderr."""
    mock_proc = MagicMock()
    mock_proc.returncode = returncode

    async def fake_communicate(input=None):
        return (stdout, stderr)

    mock_proc.communicate = fake_communicate
    return mock_proc


class TestModelResolution:
    """Test claude_pipe/ model prefix stripping and alias resolution."""

    def test_strips_prefix(self) -> None:
        assert (
            _resolve_model("claude_pipe/claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"
        )

    def test_resolves_haiku_alias(self) -> None:
        assert _resolve_model("claude_pipe/haiku") == "claude-haiku-4-5-20251001"

    def test_resolves_sonnet_alias(self) -> None:
        assert _resolve_model("claude_pipe/sonnet") == "claude-sonnet-4-6"

    def test_resolves_opus_alias(self) -> None:
        assert _resolve_model("claude_pipe/opus") == "claude-opus-4-6"

    def test_unknown_model_passes_through(self) -> None:
        assert _resolve_model("claude_pipe/claude-future-model") == "claude-future-model"


class TestClaudePipeComplete:
    """Test claude_pipe_complete function."""

    @pytest.fixture
    def role_config(self) -> RoleConfig:
        return RoleConfig(
            model="claude_pipe/haiku",
            max_tokens=1024,
        )

    @pytest.mark.asyncio
    async def test_raises_auth_error_when_not_installed(self, role_config: RoleConfig) -> None:
        with patch("engrave.llm.claude_pipe.check_claude_installed", return_value=False):
            with pytest.raises(AuthenticationError) as exc_info:
                await claude_pipe_complete(
                    role_config=role_config,
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=1024,
                )
            assert exc_info.value.provider == "claude_pipe"
            assert "not found" in str(exc_info.value.original_error).lower()

    @pytest.mark.asyncio
    async def test_calls_claude_with_correct_args(self, role_config: RoleConfig) -> None:
        mock_proc = _make_mock_proc(0, b"Generated LilyPond output", b"")

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ) as mock_exec,
        ):
            await claude_pipe_complete(
                role_config=role_config,
                messages=[{"role": "user", "content": "Fix this LilyPond"}],
                temperature=0.3,
                max_tokens=1024,
            )

            # Verify claude was called with correct args
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "claude"
            assert "-p" in args
            assert "--model" in args
            assert "claude-haiku-4-5-20251001" in args
            # --max-tokens is not supported by claude -p

    @pytest.mark.asyncio
    async def test_returns_stdout_content(self, role_config: RoleConfig) -> None:
        mock_proc = _make_mock_proc(0, b"Generated LilyPond output", b"")

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess),
        ):
            result = await claude_pipe_complete(
                role_config=role_config,
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=1024,
            )
            assert result == "Generated LilyPond output"

    @pytest.mark.asyncio
    async def test_raises_provider_error_on_nonzero_exit(self, role_config: RoleConfig) -> None:
        mock_proc = _make_mock_proc(1, b"", b"Some error occurred")

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess),
        ):
            with pytest.raises(ProviderError) as exc_info:
                await claude_pipe_complete(
                    role_config=role_config,
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=1024,
                )
            assert "Some error occurred" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_raises_auth_error_on_auth_failure(self, role_config: RoleConfig) -> None:
        mock_proc = _make_mock_proc(1, b"", b"Error: not authenticated, please run claude login")

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess),
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                await claude_pipe_complete(
                    role_config=role_config,
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=1024,
                )
            assert exc_info.value.provider == "claude_pipe"

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_string(self, role_config: RoleConfig) -> None:
        mock_proc = _make_mock_proc(0, b"", b"")

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess),
        ):
            result = await claude_pipe_complete(
                role_config=role_config,
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=1024,
            )
            assert result == ""

    @pytest.mark.asyncio
    async def test_system_messages_included_in_prompt(self, role_config: RoleConfig) -> None:
        captured_input = {}

        async def fake_communicate(input=None):
            captured_input["data"] = input
            return (b"result", b"")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = fake_communicate

        async def fake_create_subprocess(*args, **kwargs):
            return mock_proc

        with (
            patch("engrave.llm.claude_pipe.check_claude_installed", return_value=True),
            patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess),
        ):
            await claude_pipe_complete(
                role_config=role_config,
                messages=[
                    {"role": "system", "content": "You are a music expert."},
                    {"role": "user", "content": "Generate notation"},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            prompt_text = captured_input["data"].decode()
            assert "You are a music expert." in prompt_text
            assert "Generate notation" in prompt_text


class TestRouterClaudePipeDispatch:
    """Test InferenceRouter dispatches claude_pipe/ models correctly."""

    @pytest.fixture
    def claude_pipe_settings(self, tmp_path):
        """Settings with a claude_pipe role configured."""
        from tests.conftest import _make_settings_class

        toml_content = """\
[providers.vllm_mlx]
api_base = "http://localhost:8000/v1"

[roles.compile_fixer]
model = "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
max_tokens = 4096
tags = ["code"]

[roles.generator]
model = "claude_pipe/haiku"
max_tokens = 8192
tags = ["code", "lilypond"]

[roles.describer]
model = "anthropic/claude-sonnet-4-20250514"
max_tokens = 2048
tags = ["audio", "description"]

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

    def test_claude_pipe_role_resolved(self, claude_pipe_settings) -> None:
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(claude_pipe_settings)
        assert "generator" in router._roles
        assert router._roles["generator"].model == "claude_pipe/haiku"

    @pytest.mark.asyncio
    async def test_dispatches_to_claude_pipe(self, claude_pipe_settings) -> None:
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(claude_pipe_settings)

        with patch(
            "engrave.llm.claude_pipe.claude_pipe_complete", new_callable=AsyncMock
        ) as mock_fn:
            mock_fn.return_value = "generated lilypond"
            result = await router.complete(
                role="generator",
                messages=[{"role": "user", "content": "generate notation"}],
            )

        assert result == "generated lilypond"
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["role_config"].model == "claude_pipe/haiku"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 8192

    @pytest.mark.asyncio
    async def test_existing_litellm_roles_still_work(
        self, claude_pipe_settings, mock_acompletion
    ) -> None:
        """Existing hosted_vllm roles still dispatch via litellm."""
        from engrave.llm.router import InferenceRouter

        router = InferenceRouter(claude_pipe_settings)
        await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": "test"}],
        )
        mock_acompletion.assert_called_once()
