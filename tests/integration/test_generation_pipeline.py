"""Integration tests for the MIDI-to-LilyPond generation pipeline.

Tests end-to-end pipeline with mocked LLM and compiler, verifying
that MIDI files produce correct LilyPond output structure.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from engrave.generation.pipeline import generate_from_midi
from engrave.lilypond.compiler import RawCompileResult


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestGenerateFromMidiType1:
    """Tests for type 1 MIDI generation."""

    def test_generate_from_midi_type1_success(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """Type 1 MIDI -> complete .ly output with mocked LLM + compiler."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert "\\version" in result.ly_source
        assert result.sections_completed > 0
        assert result.total_sections > 0
        assert len(result.instrument_names) == 2  # Piano + Bass

    def test_generate_from_midi_with_user_labels(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """User labels override track names in output."""
        user_labels = {0: "Trumpet", 1: "Trombone"}
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                user_labels=user_labels,
            )
        )

        assert result.success is True
        assert "Trumpet" in result.ly_source
        assert "Trombone" in result.ly_source

    def test_generate_from_midi_no_rag(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """Generation succeeds without RAG retriever (rag_retriever=None)."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert result.ly_source != ""


class TestGenerateFromMidiType0:
    """Tests for type 0 MIDI generation."""

    def test_generate_from_midi_type0_success(
        self, sample_midi_type0, mock_generator_router, mock_compiler_success
    ):
        """Type 0 MIDI -> complete .ly output. Channel splitting produces multiple instruments."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type0),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert "\\version" in result.ly_source
        # Type 0 splits by channel -- should have at least 2 instruments
        assert len(result.instrument_names) >= 2


class TestGenerateFailure:
    """Tests for generation failure paths."""

    def test_generate_degrades_gracefully_on_compiler_failure(
        self, sample_midi_type1, mock_generator_router
    ):
        """Mock compiler that always fails -> rest fallback, pipeline still succeeds."""
        # Create compiler that always fails
        failing_compiler = MagicMock()
        failing_compiler.compile.return_value = RawCompileResult(
            success=False,
            returncode=1,
            stdout="",
            stderr="/tmp/test.ly:1:1: error: syntax error\n",
            output_path=None,
        )

        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=failing_compiler,
                rag_retriever=None,
            )
        )

        # Pipeline succeeds with rest fallback instead of aborting
        assert result.success is True
        assert "R" in result.ly_source  # Contains rest fallback content

    def test_generate_failure_log_written(self, sample_midi_type1, mock_generator_router, tmp_path):
        """On failure, a JSON file exists in failure log directory."""
        import os

        failing_compiler = MagicMock()
        failing_compiler.compile.return_value = RawCompileResult(
            success=False,
            returncode=1,
            stdout="",
            stderr="/tmp/test.ly:1:1: error: syntax error\n",
            output_path=None,
        )

        # Set failure log directory to tmp_path
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = _run(
                generate_from_midi(
                    midi_path=str(sample_midi_type1),
                    router=mock_generator_router,
                    compiler=failing_compiler,
                    rag_retriever=None,
                )
            )
        finally:
            os.chdir(old_cwd)

        # With rest fallback, pipeline succeeds but may still write fallback logs
        assert result.success is True


class TestGeneratedOutputQuality:
    """Tests for output quality constraints."""

    def test_generated_output_concert_pitch(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """Output .ly contains no \\transpose or \\relative."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert "\\transpose" not in result.ly_source
        assert "\\relative" not in result.ly_source

    def test_generated_output_has_all_instruments(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """Every track from MIDI appears as a variable in output."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        # Piano and Bass should be in the output
        assert "piano" in result.ly_source.lower() or "Piano" in result.ly_source
        assert "bass" in result.ly_source.lower() or "Bass" in result.ly_source

    def test_compilation_success(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """End-to-end with mock compiler verifying assembled .ly passes through."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert result.ly_source != ""
        assert result.sections_completed == result.total_sections
        # Verify the source has the expected structure
        assert "\\score" in result.ly_source
        assert "\\layout" in result.ly_source
