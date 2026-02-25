"""Prompt construction with budget management for section-by-section LilyPond generation.

Allocates tokens across MIDI, RAG, coherence, template, and output reserve.
Truncates gracefully when components exceed allocation (RAG first, then
coherence, then MIDI as last resort).
"""

from __future__ import annotations

from dataclasses import dataclass

from engrave.generation.coherence import CoherenceState


@dataclass
class PromptBudget:
    """Token allocations for section generation prompts.

    Budget breakdown for ~32K effective context window:
    - system_instructions: Fixed overhead for rules and formatting
    - template_tokens: LilyPond structural template
    - coherence_tokens: Musical state from previous sections
    - rag_tokens: Retrieved LilyPond examples
    - midi_tokens: MIDI content for this section
    - output_reserve: Reserved for LLM generation output
    - safety_margin: Buffer to avoid context overflow
    - total_limit: Hard limit on total prompt tokens
    """

    system_instructions: int = 2000
    template_tokens: int = 500
    coherence_tokens: int = 500
    rag_tokens: int = 3000
    midi_tokens: int = 4000
    output_reserve: int = 8000
    safety_margin: int = 4000
    total_limit: int = 32000

    @property
    def available_for_content(self) -> int:
        """Tokens available for variable-length content (MIDI + RAG + coherence)."""
        return (
            self.total_limit
            - self.system_instructions
            - self.template_tokens
            - self.output_reserve
            - self.safety_margin
        )


def estimate_tokens(text: str) -> int:
    """Simple token estimation (chars / 4 as rough approximation).

    Sufficient for budget management -- not meant to be exact.

    Args:
        text: Input text string.

    Returns:
        Estimated token count.
    """
    return max(1, len(text) // 4)


def fit_within_budget(
    budget: PromptBudget,
    midi_text: str,
    rag_examples: list[str],
    coherence_text: str,
) -> tuple[str, list[str], str]:
    """Truncate components to fit within the prompt budget.

    Truncation priority (graceful degradation):
    1. Reduce RAG examples from N to fewer
    2. Truncate coherence to essentials (key, time sig, tempo, dynamics only)
    3. Truncate MIDI text (last resort)

    Args:
        budget: Token allocation limits.
        midi_text: MIDI content text for this section.
        rag_examples: List of retrieved LilyPond examples.
        coherence_text: Serialized coherence state text.

    Returns:
        Tuple of (fitted_midi, fitted_rag, fitted_coherence).
    """
    available = budget.available_for_content

    midi_tokens = estimate_tokens(midi_text)
    rag_tokens = sum(estimate_tokens(ex) for ex in rag_examples)
    coherence_tokens = estimate_tokens(coherence_text)

    total_needed = midi_tokens + rag_tokens + coherence_tokens

    # If everything fits, return unchanged
    if total_needed <= available:
        return midi_text, rag_examples, coherence_text

    # Step 1: Reduce RAG examples
    fitted_rag = list(rag_examples)
    while fitted_rag and total_needed > available:
        fitted_rag.pop()
        rag_tokens = sum(estimate_tokens(ex) for ex in fitted_rag)
        total_needed = midi_tokens + rag_tokens + coherence_tokens

    if total_needed <= available:
        return midi_text, fitted_rag, coherence_text

    # Step 2: Truncate coherence text
    fitted_coherence = coherence_text
    target_coherence_tokens = max(
        budget.coherence_tokens,
        available - midi_tokens - rag_tokens,
    )
    if coherence_tokens > target_coherence_tokens:
        # Keep only essential lines (first few lines typically have key, time, tempo)
        char_limit = target_coherence_tokens * 4
        fitted_coherence = coherence_text[:char_limit] if char_limit > 0 else ""
        coherence_tokens = estimate_tokens(fitted_coherence)
        total_needed = midi_tokens + rag_tokens + coherence_tokens

    if total_needed <= available:
        return midi_text, fitted_rag, fitted_coherence

    # Step 3: Truncate MIDI text (last resort)
    target_midi_tokens = max(1, available - rag_tokens - coherence_tokens)
    char_limit = target_midi_tokens * 4
    fitted_midi = midi_text[:char_limit] if char_limit < len(midi_text) else midi_text

    return fitted_midi, fitted_rag, fitted_coherence


def build_section_prompt(
    section_midi: dict[str, str],
    coherence: CoherenceState,
    rag_examples: list[str],
    template: str,
    budget: PromptBudget | None = None,
) -> str:
    """Assemble the complete prompt for section generation.

    Applies budget fitting, then formats sections: RULES, CURRENT MUSICAL STATE,
    LILYPOND TEMPLATE, SIMILAR EXAMPLES, MIDI CONTENT, and instruction.

    Args:
        section_midi: Dict mapping track_name to tokenized MIDI text.
        coherence: CoherenceState from previous section.
        rag_examples: Retrieved LilyPond examples from corpus.
        template: LilyPond structural template for this section.
        budget: Optional token budget. Defaults to standard budget.

    Returns:
        Complete prompt string for LLM generation.
    """
    if budget is None:
        budget = PromptBudget()

    # Prepare content for budget fitting
    midi_text = "\n\n".join(
        f"## {track_name}\n{tokens}" for track_name, tokens in section_midi.items()
    )
    coherence_text = coherence.to_prompt_text()

    # Apply budget fitting
    fitted_midi, fitted_rag, fitted_coherence = fit_within_budget(
        budget, midi_text, rag_examples, coherence_text
    )

    # Format RAG section
    rag_text = "\n\n---\n\n".join(fitted_rag) if fitted_rag else "No examples available."

    return f"""Generate LilyPond music content for the following section.

RULES:
1. Use ABSOLUTE pitch mode (no \\relative). Every note must have explicit octave marks.
2. Generate ONLY the music content for each instrument variable. Do NOT generate \\version, \\score, or \\new Staff blocks.
3. All pitches must be in CONCERT PITCH. Do not transpose for any instrument.
4. Preserve all musical content from the MIDI input: pitches, rhythms, dynamics.
5. Add appropriate articulations, dynamics, and expression marks based on the musical context.
6. Output each instrument's music as a separate block labeled with the variable name (% varName).

CURRENT MUSICAL STATE:
{fitted_coherence}

LILYPOND TEMPLATE (fill in the instrument variables):
{template}

SIMILAR EXAMPLES FROM CORPUS:
{rag_text}

MIDI CONTENT FOR THIS SECTION:
{fitted_midi}

Generate the LilyPond music content for each instrument variable:"""
