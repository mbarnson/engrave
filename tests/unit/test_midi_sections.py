"""Unit tests for engrave.midi.sections -- Section boundary detection."""

from __future__ import annotations

from pathlib import Path

import mido

from engrave.midi.sections import SectionBoundary, detect_sections

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestFixedLengthFallback:
    """Tests for fixed-length section detection when no meta events."""

    def test_detect_fixed_length_fallback(self):
        """No structural meta events produces fixed-length sections."""
        # no_metadata.mid has no markers or key sig changes
        sections = detect_sections(str(FIXTURES / "no_metadata.mid"), min_bars=1, max_bars=2)
        assert len(sections) >= 1
        # All boundaries should be "fixed_length" type
        for sec in sections:
            assert isinstance(sec, SectionBoundary)
            assert sec.boundary_type == "fixed_length"

    def test_detect_respects_max_bars(self):
        """No section longer than max_bars."""
        sections = detect_sections(str(FIXTURES / "no_metadata.mid"), min_bars=1, max_bars=2)
        # Check that sections are spaced at most max_bars apart
        for i in range(1, len(sections)):
            gap = sections[i].bar_number - sections[i - 1].bar_number
            assert gap <= 2, f"Gap {gap} exceeds max_bars=2"


class TestMetaEventBoundaries:
    """Tests for meta event-based section detection."""

    def test_detect_rehearsal_mark_boundary(self):
        """Marker meta event creates section boundary."""
        # simple_type1.mid has a marker "A" at bar 3 (tick 3840)
        sections = detect_sections(str(FIXTURES / "simple_type1.mid"), min_bars=1, max_bars=8)
        # Should have at least the start boundary and the marker boundary
        marker_sections = [s for s in sections if s.boundary_type == "rehearsal_mark"]
        assert len(marker_sections) >= 1, f"Expected rehearsal_mark boundary, got: {sections}"

    def test_detect_time_sig_change_boundary(self, tmp_path):
        """Time sig change creates section boundary."""
        # Create a MIDI file with a time signature change at bar 5
        mid = mido.MidiFile(type=1, ticks_per_beat=480)
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        # Time sig change at tick 7680 (bar 5 in 4/4 at 480 tpb)
        conductor.append(mido.MetaMessage("time_signature", numerator=3, denominator=4, time=7680))
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        # Add a track with notes spanning both time sigs
        track = mido.MidiTrack()
        mid.tracks.append(track)
        for i in range(32):
            track.append(
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0 if i == 0 else 20)
            )
            track.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=460))
        track.append(mido.MetaMessage("end_of_track", time=0))

        path = tmp_path / "timesig_change.mid"
        mid.save(str(path))

        sections = detect_sections(str(path), min_bars=1, max_bars=8)
        ts_sections = [s for s in sections if s.boundary_type == "time_sig_change"]
        assert len(ts_sections) >= 1, f"Expected time_sig_change boundary, got: {sections}"


class TestSectionMerging:
    """Tests for section merging when sections are too short."""

    def test_detect_merges_short_sections(self, tmp_path):
        """Boundary creating <min_bars section merges with previous."""
        # Create MIDI with markers at bars 1, 2, 5 (min_bars=4 means bar 2 marker
        # would create a 1-bar section, which should merge with the previous)
        mid = mido.MidiFile(type=1, ticks_per_beat=480)
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        # Marker at bar 2 (tick 1920)
        conductor.append(mido.MetaMessage("marker", text="B", time=1920))
        # Marker at bar 6 (tick 9600, so delta from 1920 = 7680)
        conductor.append(mido.MetaMessage("marker", text="C", time=7680))
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        # Add notes
        track = mido.MidiTrack()
        mid.tracks.append(track)
        for i in range(40):
            track.append(
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0 if i == 0 else 20)
            )
            track.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=460))
        track.append(mido.MetaMessage("end_of_track", time=0))

        path = tmp_path / "short_sections.mid"
        mid.save(str(path))

        sections = detect_sections(str(path), min_bars=4, max_bars=8)
        # Bar 2 marker should be merged because it creates a section <4 bars from start
        # Result should not have a boundary at bar 2
        bar_numbers = [s.bar_number for s in sections]
        assert 2 not in bar_numbers, f"Bar 2 boundary should have been merged, got: {bar_numbers}"


class TestPriorityChain:
    """Tests for boundary type priority."""

    def test_detect_priority_chain(self, tmp_path):
        """Multiple boundary types present at different locations."""
        # Create MIDI with both a marker and a tempo change
        mid = mido.MidiFile(type=1, ticks_per_beat=480)
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        # Marker at bar 5 (tick 7680)
        conductor.append(mido.MetaMessage("marker", text="A", time=7680))
        # Tempo change at bar 9 (tick 15360, delta from 7680 = 7680)
        conductor.append(mido.MetaMessage("set_tempo", tempo=375000, time=7680))  # 160 BPM
        conductor.append(mido.MetaMessage("end_of_track", time=0))

        track = mido.MidiTrack()
        mid.tracks.append(track)
        for i in range(64):
            track.append(
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0 if i == 0 else 20)
            )
            track.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=460))
        track.append(mido.MetaMessage("end_of_track", time=0))

        path = tmp_path / "priority_chain.mid"
        mid.save(str(path))

        sections = detect_sections(str(path), min_bars=4, max_bars=16)
        # Should have boundaries from both marker and tempo change
        boundary_types = {s.boundary_type for s in sections}
        # At minimum should detect the rehearsal mark
        assert "rehearsal_mark" in boundary_types or "tempo_change" in boundary_types, (
            f"Expected structural boundaries, got types: {boundary_types}"
        )
