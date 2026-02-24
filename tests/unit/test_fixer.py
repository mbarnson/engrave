"""Tests for compile-fix retry loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from engrave.lilypond.compiler import RawCompileResult
from engrave.lilypond.fixer import CompileResult, compile_with_fix_loop


def _make_raw_result(
    success: bool = False,
    stderr: str = "",
    stdout: str = "",
    returncode: int = 1,
    output_path: Path | None = None,
) -> RawCompileResult:
    """Helper to create RawCompileResult for mocking."""
    return RawCompileResult(
        success=success,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        output_path=output_path,
    )


PARSEABLE_ERROR = "/tmp/test.ly:3:1: error: unmatched '{'\n{\n"
PARSEABLE_ERROR_2 = "/tmp/test.ly:5:10: error: syntax error, unexpected end\n  bad line\n"
PARSEABLE_ERROR_3 = "/tmp/test.ly:7:1: error: missing brace\n  more stuff\n"
PARSEABLE_ERROR_4 = "/tmp/test.ly:9:5: error: unknown command\n  \\badcmd\n"
PARSEABLE_ERROR_5 = "/tmp/test.ly:11:2: error: type check failure\n  oops\n"

VALID_LILYPOND = '\\version "2.24.4"\n\\relative c\' { c4 d e f | g2 g | }\n'


class TestSuccessOnFirstCompile:
    @pytest.mark.asyncio
    async def test_success_on_first_compile(self) -> None:
        mock_compiler = MagicMock()
        mock_compiler.compile.return_value = _make_raw_result(
            success=True, returncode=0, output_path=Path("/tmp/out.pdf")
        )
        mock_router = AsyncMock()

        result = await compile_with_fix_loop(
            source=VALID_LILYPOND,
            router=mock_router,
            compiler=mock_compiler,
        )
        assert isinstance(result, CompileResult)
        assert result.success is True
        assert result.attempts == []
        mock_router.complete.assert_not_called()


class TestFixAfterOneFailure:
    @pytest.mark.asyncio
    async def test_fix_after_one_failure(self) -> None:
        mock_compiler = MagicMock()
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=PARSEABLE_ERROR),
            _make_raw_result(success=True, returncode=0, output_path=Path("/tmp/out.pdf")),
        ]
        mock_router = AsyncMock()
        mock_router.complete.return_value = VALID_LILYPOND

        result = await compile_with_fix_loop(
            source="broken source",
            router=mock_router,
            compiler=mock_compiler,
        )
        assert result.success is True
        assert len(result.attempts) == 1
        mock_router.complete.assert_called_once()


class TestEarlyExitOnRepeatedError:
    @pytest.mark.asyncio
    async def test_early_exit_on_repeated_error(self) -> None:
        """Same error every time -> exit after 2 attempts (not 5)."""
        mock_compiler = MagicMock()
        # Same stderr every time => same hash
        mock_compiler.compile.return_value = _make_raw_result(success=False, stderr=PARSEABLE_ERROR)
        mock_router = AsyncMock()
        mock_router.complete.return_value = "still broken"

        result = await compile_with_fix_loop(
            source="broken source",
            router=mock_router,
            compiler=mock_compiler,
            max_attempts=5,
        )
        assert result.success is False
        # Should exit after 2 attempts: first one adds hash, second sees it repeated
        assert len(result.attempts) <= 2


class TestFailAfterMaxAttempts:
    @pytest.mark.asyncio
    async def test_fail_after_max_attempts(self) -> None:
        """Different errors each time -> exhausts all 5 attempts."""
        different_errors = [
            PARSEABLE_ERROR,
            PARSEABLE_ERROR_2,
            PARSEABLE_ERROR_3,
            PARSEABLE_ERROR_4,
            PARSEABLE_ERROR_5,
        ]
        mock_compiler = MagicMock()
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=err) for err in different_errors
        ]
        mock_router = AsyncMock()
        mock_router.complete.return_value = "still broken each time"

        result = await compile_with_fix_loop(
            source="broken source",
            router=mock_router,
            compiler=mock_compiler,
            max_attempts=5,
        )
        assert result.success is False
        assert len(result.attempts) == 5


class TestUnparseableErrorStopsLoop:
    @pytest.mark.asyncio
    async def test_unparseable_error_stops_loop(self) -> None:
        mock_compiler = MagicMock()
        mock_compiler.compile.return_value = _make_raw_result(
            success=False,
            stderr="Some weird output that does not match the error pattern\n",
        )
        mock_router = AsyncMock()

        result = await compile_with_fix_loop(
            source="broken source",
            router=mock_router,
            compiler=mock_compiler,
        )
        assert result.success is False
        # Router should not be called since errors are unparseable
        mock_router.complete.assert_not_called()


class TestErrorContextExtracted:
    @pytest.mark.asyncio
    async def test_error_context_extracted(self) -> None:
        """Verify that the LLM prompt includes ~20 lines of context, not the full source."""
        # Build a 100-line source with error at line 50
        lines = [f"line {i}" for i in range(100)]
        long_source = "\n".join(lines)
        error_at_line_50 = "/tmp/test.ly:50:1: error: bad thing\n  line 50\n"

        mock_compiler = MagicMock()
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=error_at_line_50),
            _make_raw_result(success=True, returncode=0, output_path=Path("/tmp/out.pdf")),
        ]
        mock_router = AsyncMock()
        mock_router.complete.return_value = VALID_LILYPOND

        await compile_with_fix_loop(
            source=long_source,
            router=mock_router,
            compiler=mock_compiler,
            context_lines=20,
        )

        # Check the prompt sent to router
        call_args = mock_router.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"]
        # The CONTEXT AROUND ERROR section should contain ~20 lines, not all 100
        # Extract just the context section from the prompt
        context_start = prompt_text.index("CONTEXT AROUND ERROR:")
        context_end = prompt_text.index("FULL SOURCE:")
        context_section = prompt_text[context_start:context_end]
        context_lines_found = [line for line in context_section.splitlines() if "|" in line]
        assert len(context_lines_found) <= 21  # ~20 lines centered on error


class TestFixPromptIncludesErrorMessage:
    @pytest.mark.asyncio
    async def test_fix_prompt_includes_error_message(self) -> None:
        """Verify the prompt sent to router includes the error message and severity."""
        mock_compiler = MagicMock()
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=PARSEABLE_ERROR),
            _make_raw_result(success=True, returncode=0, output_path=Path("/tmp/out.pdf")),
        ]
        mock_router = AsyncMock()
        mock_router.complete.return_value = VALID_LILYPOND

        await compile_with_fix_loop(
            source="broken source",
            router=mock_router,
            compiler=mock_compiler,
        )

        call_args = mock_router.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"]
        assert "unmatched" in prompt_text
        assert "error" in prompt_text.lower()
