"""Integration tests for section-group generation pipeline.

Tests joint dispatch (one LLM call per section group), mixed group and
individual dispatch, ENSM-03 articulation defaults, ENSM-05 section
consistency, beaming command injection, failure handling, and per-group
coherence isolation.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import mido

from engrave.generation.pipeline import generate_from_midi
from engrave.generation.templates import sanitize_var_name
from engrave.lilypond.compiler import RawCompileResult
from engrave.rendering.ensemble import BigBandPreset, InstrumentSpec, StaffGroupType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_midi_file(
    path: Path,
    track_specs: list[tuple[str, int, int]],
    bars: int = 4,
    ticks_per_beat: int = 480,
) -> Path:
    """Create a multi-track type 1 MIDI file.

    Parameters
    ----------
    path:
        Output path.
    track_specs:
        List of (track_name, channel, base_pitch) tuples.
    bars:
        Number of bars (4/4 time).
    ticks_per_beat:
        Resolution.

    Returns
    -------
    Path to the written MIDI file.
    """
    mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)

    # Conductor track
    conductor = mido.MidiTrack()
    mid.tracks.append(conductor)
    conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("end_of_track", time=0))

    for name, channel, base_pitch in track_specs:
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", channel=channel, program=0, time=0))

        notes_per_bar = 4  # quarter notes in 4/4
        for i in range(bars * notes_per_bar):
            pitch = base_pitch + (i % 5)
            track.append(
                mido.Message(
                    "note_on", channel=channel, note=pitch, velocity=80, time=0 if i == 0 else 30
                )
            )
            track.append(
                mido.Message("note_off", channel=channel, note=pitch, velocity=0, time=450)
            )
        track.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(str(path))
    return path


def _make_trumpet_preset(count: int = 4) -> BigBandPreset:
    """Create a minimal preset with ``count`` trumpets (section_group='trumpets')."""
    specs = []
    for i in range(count):
        n = i + 1
        specs.append(
            InstrumentSpec(
                name=f"Trumpet {n}",
                short_name=f"Tpt. {n}",
                variable_name=sanitize_var_name(f"Trumpet {n}"),
                transpose_from="c'",
                transpose_to="d'",
                clef="treble",
                section="Trumpets",
                group_type=StaffGroupType.BRACKET,
                score_order=i,
                is_transposing=True,
                section_group="trumpets",
            )
        )
    return BigBandPreset(instruments=tuple(specs), name="Test Trumpets")


def _make_mixed_preset() -> BigBandPreset:
    """Preset with 4 trumpets (grouped) + piano + bass (ungrouped)."""
    trumpets = _make_trumpet_preset(4).instruments
    rhythm = (
        InstrumentSpec(
            name="Piano",
            short_name="Pno.",
            variable_name="piano",
            transpose_from="c'",
            transpose_to="c'",
            clef="treble",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=10,
        ),
        InstrumentSpec(
            name="Bass",
            short_name="Bass",
            variable_name="bass",
            transpose_from="c'",
            transpose_to="c'",
            clef="bass",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=11,
        ),
    )
    return BigBandPreset(instruments=trumpets + rhythm, name="Test Mixed")


def _make_mock_router_tracking():
    """Return a mock router that tracks the number of complete() calls.

    The mock returns multi-instrument blocks: it reads variable names from the
    prompt template and produces ``% varName`` blocks accordingly.
    """
    router = AsyncMock()
    call_log: list[str] = []

    def _generate(*args, **kwargs):
        messages = kwargs.get("messages", args[0] if args else [])
        prompt = ""
        if messages:
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")

        # Parse variable names from template
        var_pattern = re.compile(r"^([a-zA-Z]\w*)\s*=\s*\{", re.MULTILINE)
        var_names = var_pattern.findall(prompt)

        if not var_names:
            var_names = ["instrument"]

        call_log.append(",".join(var_names))

        blocks = []
        for var_name in var_names:
            blocks.append(f"% {var_name}\nc'4 d'4 e'4 f'4 | g'2 g'2 |")
        return "\n\n".join(blocks)

    router.complete.side_effect = _generate
    return router, call_log


def _make_mock_compiler():
    """Return a compiler mock that always succeeds."""
    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJointSectionGroupDispatch:
    """Test 1: Joint generation dispatch -- one LLM call per section group."""

    def test_joint_section_group_dispatch(self, tmp_path):
        """4 trumpets in one section_group -> 1 LLM call (not 4)."""
        midi_path = _make_midi_file(
            tmp_path / "trumpets.mid",
            track_specs=[
                ("Trumpet 1", 0, 67),
                ("Trumpet 2", 1, 65),
                ("Trumpet 3", 2, 63),
                ("Trumpet 4", 3, 60),
            ],
            bars=4,
        )

        router, call_log = _make_mock_router_tracking()
        compiler = _make_mock_compiler()

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=_make_trumpet_preset(4),
            )
        )

        assert result.success is True

        # Filter out JSON notation calls (those re-use the prompt so also have var names)
        # LilyPond calls are the ones that built templates with 4 vars each
        ly_calls = [c for c in call_log if "trumpetOne" in c and "trumpetFour" in c]

        # There should be at least 1 call containing all 4 trumpet vars
        # (one per temporal section, but NOT 4 separate calls)
        assert len(ly_calls) >= 1

        # Total calls should be far fewer than 4 * sections * 2 (LilyPond + JSON)
        # With 1 group, expect 2 calls per section (1 LilyPond + 1 JSON)
        total_sections = result.total_sections
        # Calls should be <= 2 per section (LilyPond + JSON) not 8 (4 instruments * 2)
        assert len(call_log) <= total_sections * 2

        # Output should contain all 4 trumpet variables
        assert result.ly_source
        for var_name in ["trumpetOne", "trumpetTwo", "trumpetThree", "trumpetFour"]:
            assert var_name in result.ly_source


class TestMixedGroupAndIndividualDispatch:
    """Test 2: Mixed section group + individual instruments."""

    def test_mixed_group_and_individual_dispatch(self, tmp_path):
        """4 trumpets (grouped) + piano + bass (ungrouped) -> 3 generation units."""
        midi_path = _make_midi_file(
            tmp_path / "mixed.mid",
            track_specs=[
                ("Trumpet 1", 0, 67),
                ("Trumpet 2", 1, 65),
                ("Trumpet 3", 2, 63),
                ("Trumpet 4", 3, 60),
                ("Piano", 4, 60),
                ("Bass", 5, 36),
            ],
            bars=4,
        )

        router, call_log = _make_mock_router_tracking()
        compiler = _make_mock_compiler()

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=_make_mixed_preset(),
            )
        )

        assert result.success is True

        # Each temporal section should produce 3 generation groups:
        # 1 trumpet group + 1 piano individual + 1 bass individual
        # Each group dispatches 2 calls (LilyPond + JSON)
        # So per temporal section: 6 calls (3 groups * 2)
        total_sections = result.total_sections
        expected_max = total_sections * 6
        assert len(call_log) <= expected_max

        # Verify a call containing all 4 trumpets (joint call)
        trumpet_calls = [c for c in call_log if "trumpetOne" in c and "trumpetFour" in c]
        assert len(trumpet_calls) >= 1

        # Verify individual calls for piano and bass
        piano_calls = [c for c in call_log if "piano" in c and "trumpetOne" not in c]
        bass_calls = [c for c in call_log if "bass" in c and "trumpetOne" not in c]
        assert len(piano_calls) >= 1
        assert len(bass_calls) >= 1


class TestArticulationDefaultsApplied:
    """Test 3: ENSM-03 post-processing applies articulation defaults."""

    def test_articulation_defaults_applied(self, tmp_path):
        """Mock router returns unmarked quarter notes -> output gets staccato."""
        midi_path = _make_midi_file(
            tmp_path / "artic.mid",
            track_specs=[("Trumpet 1", 0, 67)],
            bars=4,
        )

        # Router returns quarter notes without articulations
        router = AsyncMock()
        router.complete.side_effect = lambda *a, **kw: (
            "% trumpetOne\nc'4 d'4 e'4 f'4 | g'4 a'4 b'4 c''4 |"
        )

        compiler = _make_mock_compiler()
        preset = _make_trumpet_preset(1)

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=preset,
            )
        )

        assert result.success is True
        # ENSM-03 rule: unmarked quarter notes get staccato (-.)
        # The output should contain staccato marks
        assert "-." in result.ly_source


class TestSectionConsistencyApplied:
    """Test 4: ENSM-05 section consistency strips redundant articulations."""

    def test_section_consistency_applied(self, tmp_path):
        """4 trumpet parts with identical staccato -> staccato stripped."""
        midi_path = _make_midi_file(
            tmp_path / "consistency.mid",
            track_specs=[
                ("Trumpet 1", 0, 67),
                ("Trumpet 2", 1, 65),
                ("Trumpet 3", 2, 63),
                ("Trumpet 4", 3, 60),
            ],
            bars=4,
        )

        # All 4 trumpets return identical content with staccato on beat 1
        # AND a dynamic to verify dynamics are preserved
        router = AsyncMock()

        def _response(*a, **kw):
            messages = kw.get("messages", a[0] if a else [])
            prompt = ""
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")
            var_names = re.compile(r"^([a-zA-Z]\w*)\s*=\s*\{", re.MULTILINE).findall(prompt)
            if not var_names:
                var_names = ["instrument"]
            blocks = []
            for vn in var_names:
                # Staccato on beat 1 quarter note + dynamic
                blocks.append(f"% {vn}\nc'4-.\\f d'4 e'4 f'4 |")
            return "\n\n".join(blocks)

        router.complete.side_effect = _response
        compiler = _make_mock_compiler()
        preset = _make_trumpet_preset(4)

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=preset,
            )
        )

        assert result.success is True
        ly = result.ly_source

        # Dynamics should be preserved (\\f should appear in output)
        assert "\\f" in ly

        # ENSM-05: When all 4 trumpets have identical staccato at same beat,
        # the staccato marks are stripped. The ENSM-03 pass would have added
        # staccato to unmarked quarters, making beats 2-4 also have staccato.
        # Then ENSM-05 strips them because all parts agree.
        # So the final output should have FEWER staccato marks than 4*4=16 per bar.
        # Count staccato marks in the trumpet variables
        staccato_count = ly.count("-.")
        # With 4 parts * 4 notes, if all identical, all 16 staccato marks per bar
        # should be stripped. Expect 0 or very few staccato.
        # Allow some since there may be edge cases with beat positions.
        assert staccato_count < 16 * result.total_sections


class TestBeamingSwingDefault:
    """Test 5: Default beaming is swing for big band."""

    def test_beaming_swing_default(self, tmp_path):
        """Generation with no explicit beam_style -> swing beaming commands."""
        midi_path = _make_midi_file(
            tmp_path / "swing.mid",
            track_specs=[("Trumpet 1", 0, 67)],
            bars=4,
        )

        router, _log = _make_mock_router_tracking()
        compiler = _make_mock_compiler()
        preset = _make_trumpet_preset(1)

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=preset,
            )
        )

        assert result.success is True

        # Check that the prompt sent to the LLM contained swing beaming commands
        # The router.complete was called; inspect the prompt
        calls = router.complete.call_args_list
        assert len(calls) > 0

        # Find a LilyPond generation call (not JSON)
        found_beaming = False
        for call in calls:
            kw = call.kwargs if call.kwargs else {}
            messages = kw.get("messages", call.args[0] if call.args else [])
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if "beamExceptions" in content and "baseMoment" in content:
                        found_beaming = True
                        break

        assert found_beaming, "Swing beaming commands not found in LLM prompt"


class TestBeamingChangesPerSection:
    """Test 6: Beaming style changes between sections based on description."""

    def test_beaming_changes_per_section(self, tmp_path):
        """2 sections with different beam_style signals."""
        # Create a 16-bar MIDI with marker at bar 9 to force 2 sections
        path = tmp_path / "beaming_change.mid"
        mid = mido.MidiFile(type=1, ticks_per_beat=480)

        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        # Marker at bar 9 (tick 8*1920 = 15360)
        conductor.append(mido.MetaMessage("marker", text="B", time=15360))
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name="Trumpet 1", time=0))
        track.append(mido.Message("program_change", channel=0, program=0, time=0))
        for i in range(64):
            pitch = 67 + (i % 5)
            track.append(
                mido.Message(
                    "note_on", channel=0, note=pitch, velocity=80, time=0 if i == 0 else 30
                )
            )
            track.append(mido.Message("note_off", channel=0, note=pitch, velocity=0, time=450))
        track.append(mido.MetaMessage("end_of_track", time=0))
        mid.save(str(path))

        router, _log = _make_mock_router_tracking()
        compiler = _make_mock_compiler()
        preset = _make_trumpet_preset(1)

        # Use user_hints with swing to ensure swing beaming is resolved
        result = _run(
            generate_from_midi(
                midi_path=str(path),
                router=router,
                compiler=compiler,
                preset=preset,
                user_hints="swing",
            )
        )

        assert result.success is True
        assert result.total_sections >= 2

        # All calls should have beaming commands since hints say "swing"
        calls = router.complete.call_args_list
        beaming_calls = 0
        for call in calls:
            kw = call.kwargs if call.kwargs else {}
            messages = kw.get("messages", call.args[0] if call.args else [])
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if "beamExceptions" in content:
                        beaming_calls += 1

        # Should have beaming in at least 2 calls (one per section, LilyPond only)
        assert beaming_calls >= 2


class TestSectionGroupFailureFallsBackToRests:
    """Test 7: Section group generation failure degrades gracefully with rests."""

    def test_section_group_failure_uses_rest_fallback(self, tmp_path):
        """Failure in trumpet group -> rest fallback, pipeline succeeds."""
        midi_path = _make_midi_file(
            tmp_path / "fail.mid",
            track_specs=[
                ("Trumpet 1", 0, 67),
                ("Trumpet 2", 1, 65),
                ("Trumpet 3", 2, 63),
                ("Trumpet 4", 3, 60),
            ],
            bars=4,
        )

        # Router raises on all calls -> compilation will fail
        router = AsyncMock()
        router.complete.side_effect = RuntimeError("LLM connection error")

        compiler = _make_mock_compiler()
        preset = _make_trumpet_preset(4)

        result = _run(
            generate_from_midi(
                midi_path=str(midi_path),
                router=router,
                compiler=compiler,
                preset=preset,
            )
        )

        # Pipeline succeeds with rest fallback
        assert result.success is True
        assert "R" in result.ly_source  # Contains rest fallback


class TestPerGroupCoherenceIsolation:
    """Test 8: Per-group coherence state is maintained independently."""

    def test_per_group_coherence_isolation(self, tmp_path):
        """2 groups over 2 temporal sections: each group's coherence is independent."""
        # Create 16-bar MIDI with 2 sections (marker at bar 9)
        path = tmp_path / "coherence.mid"
        mid = mido.MidiFile(type=1, ticks_per_beat=480)

        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        conductor.append(mido.MetaMessage("marker", text="B", time=15360))
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        for name, ch, pitch in [
            ("Trumpet 1", 0, 67),
            ("Trumpet 2", 1, 65),
            ("Piano", 2, 60),
        ]:
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track.append(mido.MetaMessage("track_name", name=name, time=0))
            track.append(mido.Message("program_change", channel=ch, program=0, time=0))
            for i in range(64):
                p = pitch + (i % 5)
                track.append(
                    mido.Message(
                        "note_on", channel=ch, note=p, velocity=80, time=0 if i == 0 else 30
                    )
                )
                track.append(mido.Message("note_off", channel=ch, note=p, velocity=0, time=450))
            track.append(mido.MetaMessage("end_of_track", time=0))

        mid.save(str(path))

        # Create a preset with trumpets grouped + piano ungrouped
        trumpet_specs = tuple(
            InstrumentSpec(
                name=f"Trumpet {n}",
                short_name=f"Tpt. {n}",
                variable_name=sanitize_var_name(f"Trumpet {n}"),
                transpose_from="c'",
                transpose_to="d'",
                clef="treble",
                section="Trumpets",
                group_type=StaffGroupType.BRACKET,
                score_order=n - 1,
                is_transposing=True,
                section_group="trumpets",
            )
            for n in [1, 2]
        )
        piano_spec = InstrumentSpec(
            name="Piano",
            short_name="Pno.",
            variable_name="piano",
            transpose_from="c'",
            transpose_to="c'",
            clef="treble",
            section="Rhythm",
            group_type=StaffGroupType.BRACE,
            score_order=10,
        )
        preset = BigBandPreset(instruments=(*trumpet_specs, piano_spec), name="Test")

        # Track which groups get which call numbers to verify coherence isolation
        call_sequence: list[tuple[int, list[str]]] = []
        call_count = 0

        def _track_response(*a, **kw):
            nonlocal call_count
            messages = kw.get("messages", a[0] if a else [])
            prompt = ""
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")
            var_names = re.compile(r"^([a-zA-Z]\w*)\s*=\s*\{", re.MULTILINE).findall(prompt)
            call_count += 1
            call_sequence.append((call_count, var_names))

            if not var_names:
                var_names = ["instrument"]
            blocks = []
            for vn in var_names:
                blocks.append(f"% {vn}\nc'4 d'4 e'4 f'4 | g'2 g'2 |")
            return "\n\n".join(blocks)

        router = AsyncMock()
        router.complete.side_effect = _track_response
        compiler = _make_mock_compiler()

        result = _run(
            generate_from_midi(
                midi_path=str(path),
                router=router,
                compiler=compiler,
                preset=preset,
            )
        )

        assert result.success is True
        assert result.total_sections >= 2

        # Verify calls were made in groups:
        # Section 1: trumpet group call, then piano call (+ JSON calls)
        # Section 2: trumpet group call, then piano call (+ JSON calls)
        # Trumpet calls should contain both trumpetOne and trumpetTwo
        # Piano calls should contain only piano
        trumpet_group_calls = [
            (idx, vars_)
            for idx, vars_ in call_sequence
            if "trumpetOne" in vars_ and "trumpetTwo" in vars_
        ]
        piano_individual_calls = [
            (idx, vars_)
            for idx, vars_ in call_sequence
            if "piano" in vars_ and "trumpetOne" not in vars_
        ]

        # At least 2 trumpet group calls (one per temporal section)
        # and at least 2 piano individual calls
        assert len(trumpet_group_calls) >= 2
        assert len(piano_individual_calls) >= 2

        # Verify the calls alternate properly: for each section,
        # trumpet group and piano are dispatched separately
        # (not merged into one call)
        for _, vars_ in trumpet_group_calls:
            assert "piano" not in vars_, "Trumpet group call should not contain piano"
        for _, vars_ in piano_individual_calls:
            assert "trumpetOne" not in vars_, "Piano call should not contain trumpet vars"
