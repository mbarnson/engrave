"""Gherkin step definitions for compile-fix retry loop integration tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, scenario, then, when

from engrave.lilypond.compiler import RawCompileResult
from engrave.lilypond.fixer import compile_with_fix_loop

VALID_SOURCE = '\\version "2.24.4"\n\\relative c\' { c4 d e f | g2 g | }\n'
BROKEN_SOURCE = '\\version "2.24.4"\n\\relative c\' { c4 d e f\n'
PARSEABLE_ERROR = "/tmp/test.ly:3:1: error: unmatched '{'\n{\n"

# Different errors for max-attempts scenario
DIFFERENT_ERRORS = [
    "/tmp/test.ly:3:1: error: unmatched '{'\n{\n",
    "/tmp/test.ly:5:10: error: syntax error\n  bad line\n",
    "/tmp/test.ly:7:1: error: missing brace\n  more stuff\n",
    "/tmp/test.ly:9:5: error: unknown command\n  \\badcmd\n",
    "/tmp/test.ly:11:2: error: type check failure\n  oops\n",
]


def _make_raw_result(
    success: bool = False,
    stderr: str = "",
    returncode: int = 1,
    output_path: Path | None = None,
) -> RawCompileResult:
    return RawCompileResult(
        success=success,
        returncode=returncode,
        stdout="",
        stderr=stderr,
        output_path=output_path,
    )


# --- Scenarios ---


@scenario("features/compile_fix_loop.feature", "Successful compilation of valid LilyPond")
def test_successful_compilation():
    pass


@scenario("features/compile_fix_loop.feature", "LLM fixes a broken LilyPond file within 5 attempts")
def test_fix_broken():
    pass


@scenario("features/compile_fix_loop.feature", "Early exit on repeated error")
def test_early_exit():
    pass


@scenario("features/compile_fix_loop.feature", "Fail with diagnostics after max attempts")
def test_fail_max_attempts():
    pass


# --- Given steps ---


@given("a valid LilyPond source", target_fixture="source")
def valid_source():
    return VALID_SOURCE


@given("a LilyPond source with a syntax error", target_fixture="source")
def broken_source():
    return BROKEN_SOURCE


@given("a LilyPond source with an unfixable error", target_fixture="source")
def unfixable_source():
    return BROKEN_SOURCE


@given("a LilyPond source with a complex error", target_fixture="source")
def complex_error_source():
    return BROKEN_SOURCE


@given("a mock LLM that returns the corrected source", target_fixture="mock_router")
def mock_llm_corrects():
    router = AsyncMock()
    router.complete.return_value = VALID_SOURCE
    return router


@given("a mock LLM that always returns the same broken code", target_fixture="mock_router")
def mock_llm_same_broken():
    router = AsyncMock()
    router.complete.return_value = BROKEN_SOURCE
    return router


@given(
    "a mock LLM that returns different but still broken code each time",
    target_fixture="mock_router",
)
def mock_llm_different_broken():
    router = AsyncMock()
    # Return different broken code each time
    broken_variants = [
        f'\\version "2.24.4"\n\\relative c\' {{ c4 d e f variant{i}\n' for i in range(5)
    ]
    router.complete.side_effect = broken_variants
    return router


# --- When steps ---


@when("I compile the source", target_fixture="result")
def compile_source(source):
    mock_compiler = MagicMock()
    mock_compiler.compile.return_value = _make_raw_result(
        success=True, returncode=0, output_path=Path("/tmp/out.pdf")
    )
    mock_router = AsyncMock()
    return asyncio.run(
        compile_with_fix_loop(
            source=source,
            router=mock_router,
            compiler=mock_compiler,
        )
    )


@when("I compile with the fix loop enabled", target_fixture="result")
def compile_with_fix(source, mock_router):
    mock_compiler = MagicMock()

    # Check which scenario we're in by examining the router mock
    if mock_router.complete.side_effect is not None:
        # "different but still broken code each time" scenario
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=err) for err in DIFFERENT_ERRORS
        ]
    elif mock_router.complete.return_value == VALID_SOURCE:
        # "corrected source" scenario: fail once, then succeed
        mock_compiler.compile.side_effect = [
            _make_raw_result(success=False, stderr=PARSEABLE_ERROR),
            _make_raw_result(success=True, returncode=0, output_path=Path("/tmp/out.pdf")),
        ]
    else:
        # "same broken code" scenario: always fails with same error
        mock_compiler.compile.return_value = _make_raw_result(success=False, stderr=PARSEABLE_ERROR)

    return asyncio.run(
        compile_with_fix_loop(
            source=source,
            router=mock_router,
            compiler=mock_compiler,
            max_attempts=5,
        )
    )


# --- Then steps ---


@then("the compilation succeeds")
def check_success(result):
    assert result.success is True


@then("no fix attempts were made")
def check_no_attempts(result):
    assert result.attempts == []


@then("at most 5 fix attempts were made")
def check_at_most_5(result):
    assert len(result.attempts) <= 5


@then("the loop exits before 5 attempts")
def check_early_exit(result):
    assert len(result.attempts) < 5


@then("the diagnostics show a repeated error hash")
def check_repeated_hash(result):
    # The loop detected a repeated error hash and stopped early
    assert len(result.attempts) < 5
    if len(result.attempts) >= 2:
        # Verify the same hash appeared (triggering early exit)
        hashes = [a.error_hash for a in result.attempts]
        assert len(hashes) != len(set(hashes)), "Expected repeated error hash"


@then("the compilation fails")
def check_failure(result):
    assert result.success is False


@then("5 fix attempts were made")
def check_5_attempts(result):
    assert len(result.attempts) == 5


@then("the diagnostics include the original error and all fix attempts")
def check_diagnostics(result):
    assert len(result.attempts) == 5
    assert result.final_errors is not None
    assert len(result.final_errors) > 0
