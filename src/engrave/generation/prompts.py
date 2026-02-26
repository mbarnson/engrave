"""Prompt construction with budget management for section-by-section LilyPond generation.

Allocates tokens across MIDI, RAG, coherence, template, and output reserve.
Truncates gracefully when components exceed allocation (RAG first, then
coherence, then MIDI as last resort).

Also provides JSON generation prompt suffix and extraction utilities for the
parallel LilyPond + JSON fan-out (Chatterfart prefix-caching pattern).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from engrave.generation.coherence import CoherenceState

logger = logging.getLogger(__name__)


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
    safety_margin: int = 3200
    description_tokens: int = 800
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
    audio_description: str = "",
    user_hints: str = "",
) -> list[dict[str, str]]:
    """Assemble the prompt as an OpenAI-format messages list for prefix caching.

    The message structure is optimized for vllm-mlx prefix caching:

    - **system**: Rules + DEFINITIVE hints (shared across ALL requests)
    - **user[0]**: CONTEXTUAL audio analysis (shared within a temporal section)
    - **assistant**: Acknowledgement (shared within a temporal section)
    - **user[1]**: Variable content — coherence, template, RAG, MIDI (unique per group)

    vllm-mlx ``_compute_prefix_boundary()`` replaces the last user message
    with a dummy to find the longest common prefix.  By placing shared content
    in earlier messages, ~700 tokens are cached vs ~265 with a single message.

    Audio description and user hints are NEVER truncated (they are small and
    high-authority).  Only MIDI, RAG, and coherence participate in budget
    fitting.

    Args:
        section_midi: Dict mapping track_name to tokenized MIDI text.
        coherence: CoherenceState from previous section.
        rag_examples: Retrieved LilyPond examples from corpus.
        template: LilyPond structural template for this section.
        budget: Optional token budget. Defaults to standard budget.
        audio_description: Rendered natural language audio description text.
        user_hints: Raw user hint text (free text, LLM is the parser).

    Returns:
        OpenAI-format messages list (list of dicts with "role" and "content").
    """
    if budget is None:
        budget = PromptBudget()

    # Prepare content for budget fitting
    midi_text = "\n\n".join(
        f"## {track_name}\n{tokens}" for track_name, tokens in section_midi.items()
    )
    coherence_text = coherence.to_prompt_text()

    # Apply budget fitting (audio_description and user_hints excluded -- never truncated)
    fitted_midi, fitted_rag, fitted_coherence = fit_within_budget(
        budget, midi_text, rag_examples, coherence_text
    )

    # Format RAG section
    rag_text = "\n\n---\n\n".join(fitted_rag) if fitted_rag else "No examples available."

    # Three-tier authority content
    definitive_content = user_hints if user_hints else "No user hints provided."
    contextual_content = audio_description if audio_description else "No audio analysis available."

    # -- Message 1: system (shared across ALL requests) --
    system_content = f"""You generate LilyPond music content. RULES:
1. Use ABSOLUTE pitch mode (no \\relative). Every note must have explicit octave marks.
2. Generate ONLY the music content for each instrument variable. Do NOT generate \\version, \\score, or \\new Staff blocks.
3. All pitches must be in CONCERT PITCH. Do not transpose for any instrument.
4. Preserve all musical content from the MIDI input: pitches, rhythms, dynamics.
5. Add appropriate articulations, dynamics, and expression marks based on the musical context.
6. Output each instrument's music as a separate block labeled with the variable name (% varName).

=== DEFINITIVE (User Hints -- always authoritative) ===
{definitive_content}"""

    # -- Message 2: user (shared within temporal section) --
    shared_context = f"""=== CONTEXTUAL (Audio Analysis -- structural observations) ===
{contextual_content}"""

    # -- Message 4: user (variable per group -- last user msg for prefix boundary) --
    variable_content = f"""=== CURRENT MUSICAL STATE ===
{fitted_coherence}

LILYPOND TEMPLATE (fill in the instrument variables):
{template}

SIMILAR EXAMPLES FROM CORPUS:
{rag_text}

=== RAW INPUT (MIDI Transcription -- treat as noisy suggestion) ===
{fitted_midi}

Generate the LilyPond music content for each instrument variable:"""

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": shared_context},
        {
            "role": "assistant",
            "content": "Understood. I'll follow the rules and context to generate LilyPond.",
        },
        {"role": "user", "content": variable_content},
    ]


def build_json_generation_suffix(instrument_names: list[str]) -> str:
    """Build the suffix appended to the shared prompt that instructs JSON output.

    The suffix tells the LLM to produce structured JSON notation events
    instead of LilyPond.  It includes a concrete example matching the
    format from CONTEXT.md (measure-level structure, flat note internals,
    LilyPond-style pitch names).

    Args:
        instrument_names: List of instrument names; one SectionNotation
            object per instrument is requested.

    Returns:
        Prompt suffix string with JSON format instructions and example.
    """
    instruments_list = ", ".join(f'"{name}"' for name in instrument_names)

    return f"""Instead of LilyPond, generate structured JSON notation events for this section.

OUTPUT FORMAT:
Return a JSON array with one object per instrument.  The instruments are: {instruments_list}.

Each object follows this structure:
```json
[
  {{
    "instrument": "trumpet_1",
    "key": "bf_major",
    "time_signature": "4/4",
    "measures": [
      {{
        "number": 17,
        "notes": [
          {{"pitch": "bf4", "beat": 1.0, "duration": 1.0, "articulations": ["marcato"], "dynamic": "f"}},
          {{"pitch": "d5", "beat": 2.0, "duration": 0.5}},
          {{"pitch": "ef5", "beat": 2.5, "duration": 0.5}},
          {{"pitch": "f5", "beat": 3.0, "duration": 2.0, "expressions": ["tenuto"]}}
        ]
      }},
      {{
        "number": 18,
        "notes": [
          {{"type": "rest", "beat": 1.0, "duration": 4.0}}
        ]
      }}
    ]
  }}
]
```

RULES:
1. Use "type": "rest" for rests (no pitch field needed).
2. Place "dynamic" on the FIRST note where the dynamic level changes, not on every note.
3. "articulations" and "expressions" are arrays; omit them when empty rather than using an empty array.
4. Pitch uses LilyPond-style names: bf4 for B-flat 4, ef5 for E-flat 5, fis3 for F-sharp 3.
5. "duration" is in quarterLength units: 1.0 = quarter note, 0.5 = eighth note, 2.0 = half note.
6. Measure numbers must be explicit and sequential.
7. Output ONLY the JSON array.  No commentary, no markdown, no explanation.

Generate the JSON notation events:"""


# -- JSON extraction from LLM response -----------------------------------

# Pattern to extract JSON from markdown code blocks
_JSON_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*\n(.*?)```",
    re.DOTALL,
)

# Pattern to find individual JSON objects with one level of brace nesting
_JSON_OBJECT_PATTERN = re.compile(
    r"\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}",
    re.DOTALL,
)


def extract_json_from_response(response: str) -> list[dict]:
    """Extract JSON notation events from an LLM response.

    Handles responses that are:
    - Clean JSON arrays or objects
    - Wrapped in markdown code blocks (``\\`\\`\\`json ... \\`\\`\\```)
    - Mixed with surrounding commentary text
    - Malformed (returns empty list, never raises)

    Args:
        response: Raw LLM response text.

    Returns:
        List of parsed dicts (one per instrument).  Empty list on
        complete parse failure.
    """
    # Step 1: Strip markdown code blocks if present
    match = _JSON_CODE_BLOCK_PATTERN.search(response)
    text = match.group(1).strip() if match else response.strip()

    # Step 2: Try json.loads on cleaned text -- array first, then object
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except (json.JSONDecodeError, ValueError):
        pass

    # Step 3: Try extracting individual JSON objects via regex
    objects: list[dict] = []
    for obj_match in _JSON_OBJECT_PATTERN.finditer(text):
        try:
            obj = json.loads(obj_match.group())
            if isinstance(obj, dict):
                objects.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue

    if objects:
        return objects

    # Step 4: Complete failure
    logger.warning("Failed to extract JSON from LLM response (length=%d)", len(response))
    return []
