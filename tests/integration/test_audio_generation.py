"""Integration tests for audio description + hints in generation pipeline.

Tests the three-tier prompt structure (DEFINITIVE/CONTEXTUAL/RAW INPUT)
with both audio+MIDI and pure MIDI paths, and verifies audit log output.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from engrave.audio.description import AudioDescription, SectionDescription
from engrave.generation.pipeline import generate_from_midi
from engrave.lilypond.compiler import RawCompileResult


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_audio_description() -> AudioDescription:
    """Create a test AudioDescription with sections."""
    return AudioDescription(
        tempo_bpm=142,
        time_signature="4/4",
        key="Bb major",
        instruments=["trumpet", "trombone", "piano", "bass", "drums"],
        style_tags=["swing", "big band"],
        energy_arc="mp -> mf -> f -> ff -> mf",
        sections=[
            SectionDescription(
                label="intro",
                start_bar=1,
                end_bar=8,
                key="Bb major",
                active_instruments=["piano", "bass", "drums"],
                texture="walking bass under piano chords",
                dynamics="mp",
            ),
            SectionDescription(
                label="head-in",
                start_bar=9,
                end_bar=24,
                key="Bb major",
                active_instruments=["trumpet", "trombone", "piano", "bass", "drums"],
                texture="full ensemble block chords",
                dynamics="mf",
            ),
        ],
    )


def _make_mock_router_that_captures_prompts() -> tuple[AsyncMock, list[str]]:
    """Create a mock router that captures prompt content for inspection.

    Returns:
        Tuple of (mock_router, captured_prompts_list).
    """
    import re

    captured_prompts: list[str] = []

    router = AsyncMock()

    def _generate_response(*args, **kwargs):
        messages = kwargs.get("messages", args[0] if args else [])
        prompt = ""
        if messages:
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")
                    break

        captured_prompts.append(prompt)

        # Parse variable names from the template in the prompt
        var_pattern = re.compile(r"^([a-zA-Z]\w*)\s*=\s*\{", re.MULTILINE)
        var_names = var_pattern.findall(prompt)

        if not var_names:
            var_names = ["piano", "bass"]

        # Build response with instrument blocks
        blocks = []
        for var_name in var_names:
            blocks.append(f"% {var_name}\nc'4 d'4 e'4 f'4 | g'2 g'2 |")

        return "\n\n".join(blocks)

    router.complete.side_effect = _generate_response
    return router, captured_prompts


def _make_mock_compiler_success() -> MagicMock:
    """Create a mock compiler that always succeeds."""
    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


class TestPipelineWithAudioDescription:
    """Tests for audio description + hints flowing through the pipeline."""

    def test_pipeline_with_audio_description_and_hints(
        self,
        sample_midi_type1,
    ):
        """Audio description and user hints appear in the generation prompt."""
        router, captured_prompts = _make_mock_router_that_captures_prompts()
        compiler = _make_mock_compiler_success()
        audio_desc = _make_audio_description()

        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=router,
                compiler=compiler,
                rag_retriever=None,
                audio_description=audio_desc,
                user_hints="shout chorus at bar 17",
            )
        )

        assert result.success is True

        # Check that at least one prompt was captured
        assert len(captured_prompts) >= 1

        # The first prompt should contain the DEFINITIVE section with user hints
        first_prompt = captured_prompts[0]
        assert "=== DEFINITIVE" in first_prompt
        assert "shout chorus at bar 17" in first_prompt

        # The first prompt should contain the CONTEXTUAL section with audio description
        assert "=== CONTEXTUAL" in first_prompt
        # Audio description NL text should include track summary on first section
        assert "Bb major" in first_prompt or "142 BPM" in first_prompt


class TestMidiOnlyPath:
    """Tests for pure MIDI path (no audio description, no hints)."""

    def test_midi_only_path_three_tier(self, sample_midi_type1):
        """Pure MIDI path produces three-tier prompt with placeholder text."""
        router, captured_prompts = _make_mock_router_that_captures_prompts()
        compiler = _make_mock_compiler_success()

        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=router,
                compiler=compiler,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert len(captured_prompts) >= 1

        first_prompt = captured_prompts[0]
        assert "No user hints provided." in first_prompt
        assert "No audio analysis available." in first_prompt
        assert "=== DEFINITIVE" in first_prompt
        assert "=== CONTEXTUAL" in first_prompt
        assert "=== RAW INPUT" in first_prompt


class TestAuditLog:
    """Tests for audit log written after generation."""

    def test_audit_log_written_after_generation(self, sample_midi_type1, tmp_path):
        """Audit log JSON file exists after pipeline run with output_dir."""
        router, _ = _make_mock_router_that_captures_prompts()
        compiler = _make_mock_compiler_success()

        output_dir = tmp_path / "job_output"
        output_dir.mkdir()

        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=router,
                compiler=compiler,
                rag_retriever=None,
                output_dir=str(output_dir),
            )
        )

        assert result.success is True

        audit_path = output_dir / "audit_log.json"
        assert audit_path.exists()

        data = json.loads(audit_path.read_text(encoding="utf-8"))
        assert "entries" in data
        assert len(data["entries"]) > 0

        # Each entry should have resolutions for key fields
        entry = data["entries"][0]
        field_names = [r["field"] for r in entry["resolutions"]]
        assert "key" in field_names
        assert "tempo" in field_names
        assert "time_signature" in field_names
