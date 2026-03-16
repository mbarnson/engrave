"""Per-measure surgical re-generation via LLM.

Extracts a target instrument's music content from a compiled .ly file,
sends the full content with bar context and user hint to the LLM, splices
the result back, and recompiles through the fix loop.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engrave.generation.templates import sanitize_var_name
from engrave.lilypond.fixer import compile_with_fix_loop, extract_lilypond_from_response

if TYPE_CHECKING:
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

logger = logging.getLogger(__name__)

# Regex to match a variable block: varName = { ... }
_VAR_BLOCK_RE = re.compile(
    r"^(\w+)\s*=\s*\{(.*?)\n\}",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class MeasureFixResult:
    """Result of a per-measure fix operation."""

    success: bool
    ly_source: str  # Updated .ly source (or original on failure)
    error: str | None = None


def _extract_variable(ly_source: str, var_name: str) -> tuple[str, int, int] | None:
    """Extract a variable block's content and its span in the source.

    Returns:
        Tuple of (content, start_offset, end_offset) or None if not found.
        start_offset..end_offset covers the entire ``varName = { ... }`` block.
    """
    pattern = re.compile(
        rf"^({re.escape(var_name)}\s*=\s*\{{)(.*?)\n(\}})",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(ly_source)
    if not match:
        return None
    content = match.group(2).strip()
    return content, match.start(), match.end()


def _build_measure_fix_prompt(
    instrument_name: str,
    var_content: str,
    bar_number: int,
    user_hint: str,
    context_bars: int = 2,
) -> str:
    """Build a prompt for the LLM to fix a specific measure.

    The LLM receives the full instrument part and is asked to modify
    only the target bar while preserving everything else.
    """
    return f"""You are editing a LilyPond instrument part. Fix ONLY measure (bar) {bar_number} according to the user's instructions below. Return the COMPLETE instrument content with the fix applied.

INSTRUMENT: {instrument_name}

CURRENT CONTENT:
{var_content}

USER CORRECTION FOR BAR {bar_number}:
{user_hint}

RULES:
1. Modify ONLY bar {bar_number}. Keep ALL other bars exactly as they are.
2. Bar numbers count from the beginning of the piece. Bar checks (|) separate measures.
3. Preserve the exact rhythmic duration of the bar (it must still fill the time signature).
4. Use absolute pitch mode (no \\relative). Concert pitch (no \\transpose).
5. Keep articulations, dynamics, and expression marks on untouched bars.
6. Do NOT add \\version, \\score, variable wrappers, or any structural elements.
7. Return ONLY the music content that goes inside the variable braces.
8. Do NOT wrap the output in markdown code blocks.

Return the corrected music content:"""


def _splice_variable(ly_source: str, var_name: str, new_content: str) -> str:
    """Replace a variable's music content in the .ly source."""
    pattern = re.compile(
        rf"^({re.escape(var_name)}\s*=\s*\{{)\s*\n?(.*?)\n(\}})",
        re.MULTILINE | re.DOTALL,
    )

    def replacer(match: re.Match) -> str:
        return f"{match.group(1)}\n  {new_content}\n{match.group(3)}"

    result, count = pattern.subn(replacer, ly_source, count=1)
    if count == 0:
        raise ValueError(f"Variable '{var_name}' not found in source")
    return result


async def fix_measure(
    ly_source: str,
    instrument_name: str,
    bar_number: int,
    user_hint: str,
    router: InferenceRouter,
    compiler: LilyPondCompiler,
) -> MeasureFixResult:
    """Fix a specific measure for one instrument in a compiled .ly file.

    1. Extract the target instrument's variable content
    2. Send to LLM with bar number and user hint
    3. Splice the fixed content back into the full source
    4. Recompile through the fix loop to validate

    Args:
        ly_source: Complete .ly file source.
        instrument_name: Human-readable instrument name (e.g. "Trumpet").
        bar_number: 1-based bar number to fix.
        user_hint: User's correction instruction.
        router: LLM inference router.
        compiler: LilyPond compiler.

    Returns:
        MeasureFixResult with updated source or error.
    """
    var_name = sanitize_var_name(instrument_name)

    # Extract the variable content
    extracted = _extract_variable(ly_source, var_name)
    if extracted is None:
        return MeasureFixResult(
            success=False,
            ly_source=ly_source,
            error=f"Instrument variable '{var_name}' not found in source",
        )

    var_content, _, _ = extracted

    # Build prompt and call LLM
    prompt = _build_measure_fix_prompt(
        instrument_name=instrument_name,
        var_content=var_content,
        bar_number=bar_number,
        user_hint=user_hint,
    )

    logger.info(
        "Fixing measure %d for %s (var: %s)",
        bar_number,
        instrument_name,
        var_name,
    )

    try:
        response = await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception as e:
        return MeasureFixResult(
            success=False,
            ly_source=ly_source,
            error=f"LLM request failed: {e}",
        )

    fixed_content = extract_lilypond_from_response(response)

    # Splice back into the full source
    try:
        updated_source = _splice_variable(ly_source, var_name, fixed_content)
    except ValueError as e:
        return MeasureFixResult(
            success=False,
            ly_source=ly_source,
            error=str(e),
        )

    # Compile through fix loop to validate
    compile_result = await compile_with_fix_loop(
        source=updated_source,
        router=router,
        compiler=compiler,
    )

    if compile_result.success:
        logger.info("Measure fix compiled successfully")
        return MeasureFixResult(
            success=True,
            ly_source=compile_result.source,
        )
    else:
        error_msgs = [e.message for e in compile_result.final_errors]
        logger.warning("Measure fix failed compilation: %s", error_msgs)
        return MeasureFixResult(
            success=False,
            ly_source=ly_source,
            error=f"Compilation failed after fix: {'; '.join(error_msgs[:3])}",
        )
