"""Compile-check-fix retry loop with error hash deduplication."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engrave.lilypond.parser import LilyPondError, parse_lilypond_errors

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter


@dataclass
class FixAttempt:
    """Record of a single fix attempt."""

    attempt_number: int
    error_hash: str
    error_message: str
    fix_applied: str


@dataclass
class CompileResult:
    """Result of compilation with fix loop."""

    success: bool
    output_path: str | None
    source: str  # Final source (fixed or original)
    attempts: list[FixAttempt] = field(default_factory=list)
    final_errors: list[LilyPondError] = field(default_factory=list)


def extract_error_context(source: str, error: LilyPondError, context_lines: int = 20) -> str:
    """Extract ~context_lines lines centered on the error line number.

    Returns the snippet with line numbers for context.

    Args:
        source: The full LilyPond source code.
        error: The parsed error to center context around.
        context_lines: How many lines to include (centered on error).

    Returns:
        String with numbered lines from the source around the error.
    """
    lines = source.splitlines()
    error_line = error.line - 1  # 0-indexed

    half = context_lines // 2
    start = max(0, error_line - half)
    end = min(len(lines), error_line + half + 1)

    context_parts: list[str] = []
    for i in range(start, end):
        marker = " >> " if i == error_line else "    "
        context_parts.append(f"{marker}{i + 1:4d} | {lines[i]}")

    return "\n".join(context_parts)


def build_fix_prompt(
    source_context: str,
    errors: list[LilyPondError],
    original_source: str,
) -> str:
    """Build a prompt telling the LLM to fix LilyPond syntax errors.

    The prompt emphasizes strict musical preservation: only fix
    syntax/structural errors, never change notes, articulations,
    or dynamics.

    Args:
        source_context: Extracted context lines around the error.
        errors: List of parsed errors from compilation.
        original_source: The complete LilyPond source code.

    Returns:
        Prompt string for the LLM.
    """
    error_descriptions = []
    for err in errors:
        error_descriptions.append(
            f"- {err.severity} at line {err.line}, column {err.column}: {err.message}"
        )
        if err.offending_line:
            error_descriptions.append(f"  Offending line: {err.offending_line}")

    errors_text = "\n".join(error_descriptions)

    return f"""Fix the following LilyPond compilation errors. Return ONLY the complete, corrected LilyPond source code.

CRITICAL RULES:
1. STRICT MUSICAL PRESERVATION: Keep ALL notes, articulations, dynamics, and musical content EXACTLY as written.
2. Only fix syntax errors and structural issues (missing braces, incorrect commands, etc.).
3. If you cannot fix the error without changing musical content, return the source unchanged.
4. Return the COMPLETE source file, not just the changed section.
5. Do NOT wrap the output in markdown code blocks.

ERRORS:
{errors_text}

CONTEXT AROUND ERROR:
{source_context}

FULL SOURCE:
{original_source}

Return the corrected LilyPond source code:"""


# Pattern to extract LilyPond from markdown code blocks
_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:lilypond|ly)?\s*\n(.*?)```",
    re.DOTALL,
)


def extract_lilypond_from_response(response: str) -> str:
    """Extract LilyPond code from LLM response.

    Handles responses that are:
    - Plain LilyPond source (returned as-is)
    - Wrapped in markdown code blocks (extracted)
    - Mixed with explanation text (code block extracted)

    Args:
        response: Raw LLM response text.

    Returns:
        Extracted LilyPond source code.
    """
    # Try to find a code block first
    match = _CODE_BLOCK_PATTERN.search(response)
    if match:
        return match.group(1).strip()

    # Check for generic code block
    generic_match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
    if generic_match:
        return generic_match.group(1).strip()

    # Return as-is (assume plain LilyPond)
    return response.strip()


async def compile_with_fix_loop(
    source: str,
    router: InferenceRouter,
    compiler: LilyPondCompiler,
    max_attempts: int = 5,
    context_lines: int = 20,
) -> CompileResult:
    """Compile LilyPond with LLM-assisted error recovery.

    The loop:
    1. Compiles the source
    2. If successful, returns immediately
    3. Parses errors from stderr
    4. Checks for unparseable errors (stops if found)
    5. Checks for repeated error hashes (early exit)
    6. Extracts context around the first error
    7. Asks the LLM to fix the error
    8. Retries with the fixed source

    Args:
        source: LilyPond source code to compile.
        router: InferenceRouter for LLM fix requests.
        compiler: LilyPondCompiler for subprocess compilation.
        max_attempts: Maximum number of fix attempts (default 5).
        context_lines: Lines of context around errors for LLM (default 20).

    Returns:
        CompileResult with full diagnostics.
    """
    seen_hashes: set[str] = set()
    attempts: list[FixAttempt] = []
    current_source = source
    errors: list[LilyPondError] = []

    for attempt_num in range(max_attempts):
        result = compiler.compile(current_source)

        if result.success:
            return CompileResult(
                success=True,
                output_path=str(result.output_path) if result.output_path else None,
                source=current_source,
                attempts=attempts,
            )

        # Parse errors from stderr (and stdout per Pitfall 2)
        combined_output = result.stderr
        if result.stdout:
            combined_output = result.stdout + "\n" + result.stderr
        errors = parse_lilypond_errors(combined_output)
        logger.info(
            "  Fix loop attempt %d: %d errors. First: %s",
            attempt_num + 1,
            len(errors),
            errors[0].message if errors else "(unparseable)",
        )
        if not errors:
            logger.warning("  Unparseable compiler output:\n%s", combined_output[:500])
            break

        # Early exit on repeated error
        error_hash = hashlib.sha256(result.stderr.encode()).hexdigest()[:16]

        if error_hash in seen_hashes:
            # Record this attempt before exiting
            attempts.append(
                FixAttempt(
                    attempt_number=attempt_num + 1,
                    error_hash=error_hash,
                    error_message=errors[0].message,
                    fix_applied="Repeated error detected -- stopping early",
                )
            )
            break
        seen_hashes.add(error_hash)

        # Extract context around first error
        error_context = extract_error_context(current_source, errors[0], context_lines)

        # Ask LLM to fix
        fix_prompt = build_fix_prompt(
            source_context=error_context,
            errors=errors,
            original_source=current_source,
        )

        fixed_response = await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": fix_prompt}],
            temperature=0.1,  # Low temperature for precise fixes
        )

        attempts.append(
            FixAttempt(
                attempt_number=attempt_num + 1,
                error_hash=error_hash,
                error_message=errors[0].message,
                fix_applied=f"LLM fix attempt {attempt_num + 1}",
            )
        )

        current_source = extract_lilypond_from_response(fixed_response)

    return CompileResult(
        success=False,
        output_path=None,
        source=current_source,
        attempts=attempts,
        final_errors=errors,
    )
