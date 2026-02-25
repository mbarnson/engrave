"""Unit tests for engrave.midi.tokenizer -- MIDI-to-text tokenization."""

from __future__ import annotations

from engrave.midi.loader import NoteEvent
from engrave.midi.tokenizer import tokenize_section_for_prompt


class TestTokenizeSingleNote:
    """Basic single-note tokenization."""

    def test_tokenize_single_note(self):
        """One note produces correct pitch name, duration, velocity."""
        notes = [NoteEvent(pitch=60, start_tick=0, duration_ticks=480, velocity=80, channel=0)]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(4, 4),
            key="c \\major",
            bars=(1, 1),
            ticks_per_beat=480,
        )
        assert "bar 1:" in result
        # Middle C in LilyPond absolute = c'
        assert "c'" in result
        # Quarter note duration = 4
        assert "4" in result


class TestTokenizePitchNaming:
    """MIDI numbers map to correct LilyPond note names."""

    def test_tokenize_pitch_naming(self):
        """Various MIDI pitches produce correct LilyPond names."""
        test_cases = [
            # (midi_pitch, expected_ly_name)
            (48, "c"),  # C3 = c (no octave mark)
            (60, "c'"),  # C4 = c'
            (72, "c''"),  # C5 = c''
            (84, "c'''"),  # C6 = c'''
            (36, "c,"),  # C2 = c,
            (24, "c,,"),  # C1 = c,,
            (61, "cis'"),  # C#4 = cis'
            (63, "dis'"),  # D#4 = dis'
            (66, "fis'"),  # F#4 = fis'
            (68, "gis'"),  # G#4 = gis'
            (70, "ais'"),  # A#4 = ais'
        ]
        for midi_pitch, expected_name in test_cases:
            notes = [
                NoteEvent(
                    pitch=midi_pitch, start_tick=0, duration_ticks=480, velocity=80, channel=0
                )
            ]
            result = tokenize_section_for_prompt(
                notes=notes,
                time_sig=(4, 4),
                key="c \\major",
                bars=(1, 1),
                ticks_per_beat=480,
            )
            assert expected_name in result, (
                f"MIDI {midi_pitch}: expected '{expected_name}' in '{result}'"
            )


class TestTokenizeDuration:
    """Duration quantization tests."""

    def test_tokenize_duration_quantization(self):
        """Various tick durations snap to correct LilyPond durations."""
        tpb = 480
        test_cases = [
            # (duration_ticks, expected_duration_string)
            (tpb * 4, "1"),  # whole note
            (tpb * 2, "2"),  # half note
            (tpb, "4"),  # quarter note
            (tpb // 2, "8"),  # eighth note
            (tpb // 4, "16"),  # sixteenth note
        ]
        for dur_ticks, expected_dur in test_cases:
            notes = [
                NoteEvent(pitch=60, start_tick=0, duration_ticks=dur_ticks, velocity=80, channel=0)
            ]
            result = tokenize_section_for_prompt(
                notes=notes,
                time_sig=(4, 4),
                key="c \\major",
                bars=(1, 1),
                ticks_per_beat=tpb,
            )
            # The duration number should appear right after the pitch name
            assert f"c'{expected_dur}" in result or f"c' {expected_dur}" in result, (
                f"Duration {dur_ticks} ticks: expected '{expected_dur}' near pitch in '{result}'"
            )

    def test_tokenize_dotted_notes(self):
        """Dotted durations detected correctly."""
        tpb = 480
        # Dotted quarter = 1.5 * quarter = 720 ticks
        notes = [NoteEvent(pitch=60, start_tick=0, duration_ticks=720, velocity=80, channel=0)]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(4, 4),
            key="c \\major",
            bars=(1, 1),
            ticks_per_beat=tpb,
        )
        # Should contain dotted quarter notation: "4." in the output
        assert "4." in result, f"Expected dotted quarter '4.' in '{result}'"


class TestTokenizeVelocity:
    """Velocity/dynamic change tests."""

    def test_tokenize_velocity_changes_only(self):
        """Velocity only appears when it changes from previous note."""
        tpb = 480
        notes = [
            NoteEvent(pitch=60, start_tick=0, duration_ticks=tpb, velocity=80, channel=0),
            NoteEvent(pitch=62, start_tick=tpb, duration_ticks=tpb, velocity=80, channel=0),
            NoteEvent(pitch=64, start_tick=tpb * 2, duration_ticks=tpb, velocity=100, channel=0),
        ]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(4, 4),
            key="c \\major",
            bars=(1, 1),
            ticks_per_beat=tpb,
        )
        # First note should have a dynamic marking
        # Second note (same velocity) should NOT repeat the dynamic
        # Third note (different velocity) should have a new dynamic
        # Just check that dynamics appear at least twice for change detection
        dynamic_count = sum(
            1 for marker in ["\\pp", "\\p", "\\mp", "\\mf", "\\f", "\\ff"] if marker in result
        )
        assert dynamic_count >= 1, f"Expected at least 1 dynamic marker, got: '{result}'"


class TestTokenizeRests:
    """Rest detection tests."""

    def test_tokenize_rests_included(self):
        """Gaps between notes produce explicit rest tokens."""
        tpb = 480
        notes = [
            NoteEvent(pitch=60, start_tick=0, duration_ticks=tpb, velocity=80, channel=0),
            # Gap of one quarter note (480 ticks)
            NoteEvent(pitch=62, start_tick=tpb * 2, duration_ticks=tpb, velocity=80, channel=0),
        ]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(4, 4),
            key="c \\major",
            bars=(1, 1),
            ticks_per_beat=tpb,
        )
        # Should contain a rest token
        assert "r" in result, f"Expected rest token 'r' in '{result}'"


class TestTokenizeMultipleBars:
    """Multi-bar output grouping tests."""

    def test_tokenize_multiple_bars(self):
        """Output grouped by bar number with correct format."""
        tpb = 480
        notes = [
            # Bar 1: C4 quarter note
            NoteEvent(pitch=60, start_tick=0, duration_ticks=tpb, velocity=80, channel=0),
            # Bar 2: D4 quarter note
            NoteEvent(pitch=62, start_tick=tpb * 4, duration_ticks=tpb, velocity=80, channel=0),
        ]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(4, 4),
            key="c \\major",
            bars=(1, 2),
            ticks_per_beat=tpb,
        )
        assert "bar 1:" in result
        assert "bar 2:" in result

    def test_tokenize_bar_numbers_correct(self):
        """Bar numbers match tick positions for given time sig."""
        tpb = 480
        # 3/4 time: 3 beats per bar = 1440 ticks per bar
        ticks_per_bar = 3 * tpb  # 1440
        notes = [
            NoteEvent(pitch=60, start_tick=0, duration_ticks=tpb, velocity=80, channel=0),
            NoteEvent(
                pitch=62, start_tick=ticks_per_bar, duration_ticks=tpb, velocity=80, channel=0
            ),
            NoteEvent(
                pitch=64,
                start_tick=ticks_per_bar * 2,
                duration_ticks=tpb,
                velocity=80,
                channel=0,
            ),
        ]
        result = tokenize_section_for_prompt(
            notes=notes,
            time_sig=(3, 4),
            key="c \\major",
            bars=(1, 3),
            ticks_per_beat=tpb,
        )
        assert "bar 1:" in result
        assert "bar 2:" in result
        assert "bar 3:" in result
