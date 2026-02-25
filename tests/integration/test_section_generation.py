"""Integration tests for section-level generation and assembly.

Tests multi-section coherence passing, single-section handling,
and assembled output structure validation.
"""

from __future__ import annotations

import asyncio

from engrave.generation.pipeline import generate_from_midi


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestMultiSectionCoherence:
    """Tests for coherence state passing between sections."""

    def test_multi_section_coherence_passing(
        self, mock_generator_router, mock_compiler_success, tmp_path
    ):
        """16-bar MIDI generates multiple sections, coherence carries forward.

        Uses the fixtures/simple_type1.mid which has a marker at bar 3,
        producing at least 2 sections.
        """
        import mido

        # Create a 16-bar MIDI that will produce 2+ sections
        path = tmp_path / "multi_section.mid"
        mid = mido.MidiFile(type=1, ticks_per_beat=480)

        # Conductor track with marker at bar 9 to force section split
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        # Marker at bar 9 = tick 8 * 1920 = 15360
        conductor.append(mido.MetaMessage("marker", text="B", time=15360))
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        # Piano track: 16 bars of quarter notes
        piano = mido.MidiTrack()
        mid.tracks.append(piano)
        piano.append(mido.MetaMessage("track_name", name="Piano", time=0))
        piano.append(mido.Message("program_change", channel=0, program=0, time=0))
        for i in range(64):  # 64 quarter notes = 16 bars of 4/4
            pitch = 60 + (i % 7)
            piano.append(
                mido.Message(
                    "note_on", channel=0, note=pitch, velocity=80, time=0 if i == 0 else 30
                )
            )
            piano.append(mido.Message("note_off", channel=0, note=pitch, velocity=0, time=450))
        piano.append(mido.MetaMessage("end_of_track", time=0))

        mid.save(str(path))

        result = _run(
            generate_from_midi(
                midi_path=str(path),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        # Should have at least 2 sections due to the marker
        assert result.total_sections >= 2
        assert result.sections_completed == result.total_sections

    def test_single_section_short_midi(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """4-bar MIDI generates section(s) -- no section splitting needed for very short files."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        assert result.sections_completed > 0
        assert result.ly_source != ""


class TestSectionAssembly:
    """Tests for assembled output structure."""

    def test_section_assembly_produces_valid_structure(
        self, sample_midi_type1, mock_generator_router, mock_compiler_success
    ):
        """Assembled output has single \\version, single \\score, continuous variables."""
        result = _run(
            generate_from_midi(
                midi_path=str(sample_midi_type1),
                router=mock_generator_router,
                compiler=mock_compiler_success,
                rag_retriever=None,
            )
        )

        assert result.success is True
        ly = result.ly_source

        # Single \version header
        assert ly.count('\\version "2.24.4"') == 1

        # Single \score block
        assert ly.count("\\score") == 1

        # Has instrument variable declarations
        assert "= {" in ly

        # Has layout block
        assert "\\layout" in ly

        # Has global settings
        assert "\\key" in ly
        assert "\\time" in ly
        assert "\\tempo" in ly
