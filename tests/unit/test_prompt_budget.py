"""Unit tests for prompt budget management."""

from __future__ import annotations

from engrave.generation.coherence import CoherenceState
from engrave.generation.prompts import (
    PromptBudget,
    build_section_prompt,
    estimate_tokens,
    fit_within_budget,
)


def _all_content(messages: list[dict[str, str]]) -> str:
    """Concatenate all message content for assertion checks."""
    return "\n".join(m["content"] for m in messages)


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
    """Test full prompt construction (now returns list[dict])."""

    def test_build_section_prompt_returns_messages_list(self):
        """Output should be a list of message dicts with correct roles."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q) d4(q)"},
            coherence=CoherenceState(),
            rag_examples=["\\version \"2.24.0\"\nc''4 d'' e'' f''"],
            template="trumpet = {\n  \n}\n\n\\score {\n  <<\n  >>\n}",
        )
        assert isinstance(messages, list)
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"

    def test_build_section_prompt_has_all_sections(self):
        """Combined content should contain all major prompt sections."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q) d4(q)"},
            coherence=CoherenceState(),
            rag_examples=["\\version \"2.24.0\"\nc''4 d'' e'' f''"],
            template="trumpet = {\n  \n}\n\n\\score {\n  <<\n  >>\n}",
        )
        combined = _all_content(messages)
        assert "RULES" in combined
        assert "MUSICAL STATE" in combined or "CURRENT MUSICAL STATE" in combined
        assert "TEMPLATE" in combined or "LILYPOND TEMPLATE" in combined
        assert "EXAMPLES" in combined or "SIMILAR EXAMPLES" in combined
        assert "MIDI" in combined

    def test_build_section_prompt_rules_in_system(self):
        """RULES should be in the system message (shared across all requests)."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        system_content = messages[0]["content"]
        assert "RULES" in system_content
        assert "ABSOLUTE" in system_content
        assert "CONCERT PITCH" in system_content

    def test_build_section_prompt_rules_no_score_block(self):
        """System message should say not to generate \\score."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        system_content = messages[0]["content"]
        assert "\\score" in system_content or "\\version" in system_content

    def test_build_section_prompt_variable_content_in_last_user(self):
        """Template, RAG, and MIDI should be in the last user message."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=["example LilyPond"],
            template="trumpet = { }",
        )
        last_user = messages[3]["content"]
        assert "TEMPLATE" in last_user or "LILYPOND TEMPLATE" in last_user
        assert "MIDI" in last_user
        assert "EXAMPLES" in last_user or "SIMILAR EXAMPLES" in last_user


class TestThreeTierPrompt:
    """Tests for three-tier authority prompt structure."""

    def test_three_tier_prompt_has_definitive_in_system(self):
        """System message with user_hints contains DEFINITIVE section."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
            user_hints="swing feel",
        )
        system_content = messages[0]["content"]
        assert "=== DEFINITIVE" in system_content
        assert "swing feel" in system_content

    def test_three_tier_prompt_has_contextual_in_shared_user(self):
        """Shared user message with audio_description contains CONTEXTUAL section."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
            audio_description="Bb major, 142 BPM",
        )
        shared_user = messages[1]["content"]
        assert "=== CONTEXTUAL" in shared_user
        assert "Bb major, 142 BPM" in shared_user

    def test_three_tier_prompt_has_raw_input_in_last_user(self):
        """Last user message contains RAW INPUT section for MIDI content."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        last_user = messages[3]["content"]
        assert "=== RAW INPUT" in last_user

    def test_three_tier_prompt_empty_hints_placeholder(self):
        """System message without user hints contains placeholder text."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        system_content = messages[0]["content"]
        assert "No user hints provided." in system_content

    def test_three_tier_prompt_empty_audio_placeholder(self):
        """Shared user message without audio description contains placeholder text."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=[],
            template="trumpet = { }",
        )
        shared_user = messages[1]["content"]
        assert "No audio analysis available." in shared_user

    def test_three_tier_prompt_backward_compatible(self):
        """Messages with no new args still produce valid content with all required sections."""
        messages = build_section_prompt(
            section_midi={"trumpet": "bar 1: c4(q)"},
            coherence=CoherenceState(),
            rag_examples=["example 1"],
            template="trumpet = { }",
        )
        combined = _all_content(messages)
        assert "RULES" in combined
        assert "TEMPLATE" in combined or "LILYPOND TEMPLATE" in combined
        assert "EXAMPLES" in combined or "SIMILAR EXAMPLES" in combined
        assert "=== DEFINITIVE" in combined
        assert "=== CONTEXTUAL" in combined
        assert "=== RAW INPUT" in combined
        assert "No user hints provided." in combined
        assert "No audio analysis available." in combined

    def test_prompt_budget_description_tokens_field(self):
        """PromptBudget has description_tokens=800 and safety_margin=3200."""
        budget = PromptBudget()
        assert budget.description_tokens == 800
        assert budget.safety_margin == 3200
