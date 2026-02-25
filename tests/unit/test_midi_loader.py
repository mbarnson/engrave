"""Unit tests for engrave.midi.loader -- MIDI loading and normalization."""

from __future__ import annotations

from pathlib import Path

import mido
import pytest

from engrave.midi.loader import NoteEvent, load_midi

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadType0:
    """Tests for MIDI type 0 loading and channel splitting."""

    def test_load_type0_splits_by_channel(self):
        """Type 0 file produces separate MidiTrackInfo per active channel."""
        tracks, meta = load_midi(str(FIXTURES / "simple_type0.mid"))
        assert meta["type"] == 0
        # Should have 3 channels: 0 (piano), 1 (bass), 9 (drums)
        channels = {t.channel for t in tracks}
        assert 0 in channels
        assert 1 in channels
        assert 9 in channels

    def test_load_type0_drums_channel_9(self):
        """Channel 9 track has is_drum=True."""
        tracks, _ = load_midi(str(FIXTURES / "simple_type0.mid"))
        drum_tracks = [t for t in tracks if t.channel == 9]
        assert len(drum_tracks) == 1
        assert drum_tracks[0].is_drum is True
        # Non-drum tracks should not be flagged
        non_drum = [t for t in tracks if t.channel != 9]
        for t in non_drum:
            assert t.is_drum is False

    def test_load_type0_program_change(self):
        """Instrument names populated from GM lookup via program_change."""
        tracks, _ = load_midi(str(FIXTURES / "simple_type0.mid"))
        piano_track = next(t for t in tracks if t.channel == 0)
        bass_track = next(t for t in tracks if t.channel == 1)
        assert piano_track.program == 0
        assert piano_track.instrument_name == "Acoustic Grand Piano"
        assert bass_track.program == 32
        assert bass_track.instrument_name == "Acoustic Bass"

    def test_load_type0_note_events_exist(self):
        """Each non-empty channel has NoteEvent objects with correct fields."""
        tracks, _ = load_midi(str(FIXTURES / "simple_type0.mid"))
        piano_track = next(t for t in tracks if t.channel == 0)
        assert len(piano_track.notes) == 16  # 4 bars * 4 quarter notes
        for note in piano_track.notes:
            assert isinstance(note, NoteEvent)
            assert 0 <= note.pitch <= 127
            assert note.duration_ticks > 0
            assert note.velocity > 0


class TestLoadType1:
    """Tests for MIDI type 1 loading with multi-track."""

    def test_load_type1_separate_tracks(self):
        """Type 1 file preserves track separation."""
        tracks, meta = load_midi(str(FIXTURES / "simple_type1.mid"))
        assert meta["type"] == 1
        # Should have 2 tracks (conductor track has no notes, should be skipped)
        assert len(tracks) >= 2

    def test_load_type1_track_names(self):
        """Instrument names from track_name meta messages."""
        tracks, _ = load_midi(str(FIXTURES / "simple_type1.mid"))
        names = {t.instrument_name for t in tracks}
        assert "Trumpet" in names
        assert "Trombone" in names

    def test_load_type1_skips_empty_tracks(self):
        """Tracks with no note events are excluded from result."""
        tracks, _ = load_midi(str(FIXTURES / "simple_type1.mid"))
        # Conductor track has no notes -- should not appear
        for t in tracks:
            assert len(t.notes) > 0


class TestLoadEdgeCases:
    """Edge case and error handling tests."""

    def test_load_no_metadata_still_works(self):
        """File without metadata produces tracks with None instrument_name."""
        tracks, _meta = load_midi(str(FIXTURES / "no_metadata.mid"))
        assert len(tracks) >= 2
        for t in tracks:
            # No program_change and no track names in this file
            assert t.instrument_name is None
            assert len(t.notes) > 0

    def test_load_unsupported_type_raises(self, tmp_path):
        """Type 2 MIDI raises ValueError."""
        # Create a type 2 MIDI file
        mid = mido.MidiFile(type=2, ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("end_of_track", time=0))
        path = tmp_path / "type2.mid"
        mid.save(str(path))

        with pytest.raises(ValueError, match="not supported"):
            load_midi(str(path))

    def test_note_events_have_correct_timing(self):
        """start_tick and duration_ticks are accurate for type 0 piano notes."""
        tracks, meta = load_midi(str(FIXTURES / "simple_type0.mid"))
        piano_track = next(t for t in tracks if t.channel == 0)
        tpb = meta["ticks_per_beat"]

        # First note should start near tick 0
        first_note = piano_track.notes[0]
        assert first_note.start_tick == 0

        # Second note should start at ~480 ticks (one quarter note later)
        second_note = piano_track.notes[1]
        assert second_note.start_tick == tpb  # 480

        # Duration should be ~450 ticks (slightly less than a quarter note)
        assert first_note.duration_ticks == 450

    def test_metadata_contains_ticks_per_beat(self):
        """Global metadata includes ticks_per_beat."""
        _, meta = load_midi(str(FIXTURES / "simple_type0.mid"))
        assert meta["ticks_per_beat"] == 480
        assert meta["num_tracks"] >= 1
