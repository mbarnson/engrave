"""Unit tests for prompt budget management."""

from __future__ import annotations

from engrave.generation.coherence import CoherenceState
from engrave.generation.prompts import (
    PromptBudget,
    build_section_prompt,
    estimate_tokens,
    fit_within_budget,
)


class TestEstimateTokens:
    """Test rough token estimation."""

    def test_estimate_tokens_rough_accuracy(self):
        """Token estimate should be within 2x of actual for typical text."""
        text = "Hello world, this is a test of token estimation."
        estimate = estimate_tokens(text)
        # Typical tokenizer produces ~10-12 tokens for this
        # Our chars/4 estimate should be in a reasonable range
        assert 5 <= estimate <= 25


class TestFitWithinBudget:
    """Test budget fitting with graceful truncation."""

    def test_fit_within_budget_no_truncation(self):
        """Components within budget should be returned unchanged."""
        budget = PromptBudget(total_limit=100000)  # Very large budget
        midi_text = "bar 1: c4(q) d4(q) e4(q) f4(q)"
        rag_examples = ["example 1", "example 2"]
        coherence_text = "Key: c major, Time: 4/4"

        fitted_midi, fitted_rag, fitted_coherence = fit_within_budget(
            budget, midi_text, rag_examples, coherence_text
        )
        assert fitted_midi == midi_text
        assert fitted_rag == rag_examples
        assert fitted_coherence == coherence_text

    def test_fit_within_budget_reduces_rag_first(self):
        """When over budget, RAG examples should be reduced before other components."""
        budget = PromptBudget(
            total_limit=200,
            system_instructions=50,
            template_tokens=20,
            coherence_tokens=20,
            rag_tokens=30,
            midi_tokens=30,
            output_reserve=30,
            safety_margin=20,
        )
        midi_text = "short midi"
        rag_examples = [
            "example " * 20,
            "another " * 20,
            "third " * 20,
            "fourth " * 20,
            "fifth " * 20,
        ]
        coherence_text = "Key: c major"

        fitted_midi, fitted_rag, _fitted_coherence = fit_within_budget(
            budget, midi_text, rag_examples, coherence_text
        )
        # RAG examples should be reduced (fewer examples)
        assert len(fitted_rag) < len(rag_examples)
        # MIDI should still be intact (it's small)
        assert fitted_midi == midi_text

    def test_fit_within_budget_truncates_coherence_second(self):
        """After RAG reduction, coherence should be truncated."""
        budget = PromptBudget(
            total_limit=150,
            system_instructions=30,
            template_tokens=20,
            coherence_tokens=20,
            rag_tokens=20,
            midi_tokens=30,
            output_reserve=20,
            safety_margin=10,
        )
        midi_text = "m" * 100
        rag_examples = []  # Already empty
        coherence_text = "c" * 500  # Very long

        _fitted_midi, _fitted_rag, fitted_coherence = fit_within_budget(
            budget, midi_text, rag_examples, coherence_text
        )
        # Coherence should be truncated
        assert len(fitted_coherence) < len(coherence_text)

    def test_fit_within_budget_truncates_midi_last(self):
        """MIDI text should be truncated only as last resort."""
        budget = PromptBudget(
            total_limit=100,
            system_instructions=20,
            template_tokens=10,
            coherence_tokens=10,
            rag_tokens=10,
            midi_tokens=20,
            output_reserve=20,
            safety_margin=10,
        )
        midi_text = "m" * 1000  # Very long
        rag_examples = []  # Already empty
        coherence_text = "short"

        fitted_midi, _fitted_rag, _fitted_coherence = fit_within_budget(
            budget, midi_text, rag_examples, coherence_text
        )
        # MIDI should be truncated
        assert len(fitted_midi) < len(midi_text)


class TestBuildSectionPrompt:
    """Test full prompt construction."""

    def test_build_section_prompt_has_all_sections(self):
        """Output should contain all major prompt sections."""
        section_midi = {"trumpet": "bar 1: c4(q) d4(q)"}
        coherence = CoherenceState()
        rag_examples = ["\\version \"2.24.4\"\nc''4 d'' e'' f''"]
        template = "trumpet = {\n  \n}\n\n\\score {\n  <<\n  >>\n}"

        prompt = build_section_prompt(
            section_midi=section_midi,
            coherence=coherence,
            rag_examples=rag_examples,
            template=template,
        )
        assert "RULES" in prompt
        assert "MUSICAL STATE" in prompt or "CURRENT MUSICAL STATE" in prompt
        assert "TEMPLATE" in prompt or "LILYPOND TEMPLATE" in prompt
        assert "EXAMPLES" in prompt or "SIMILAR EXAMPLES" in prompt
        assert "MIDI" in prompt

    def test_build_section_prompt_rules_absolute_pitch(self):
        """RULES section should mention absolute pitch."""
        prompt = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        rules_idx = prompt.index("RULES")
        rules_section = prompt[rules_idx : rules_idx + 500]
        assert "absolute" in rules_section.lower() or "ABSOLUTE" in rules_section

    def test_build_section_prompt_rules_concert_pitch(self):
        """RULES section should mention concert pitch."""
        prompt = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        rules_idx = prompt.index("RULES")
        rules_section = prompt[rules_idx : rules_idx + 500]
        assert "concert" in rules_section.lower() or "CONCERT" in rules_section

    def test_build_section_prompt_rules_no_score_block(self):
        """RULES section should say not to generate \\score."""
        prompt = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        rules_idx = prompt.index("RULES")
        rules_section = prompt[rules_idx : rules_idx + 600]
        assert "\\score" in rules_section or "\\version" in rules_section
