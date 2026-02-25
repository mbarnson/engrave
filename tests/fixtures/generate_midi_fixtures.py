"""Generate deterministic MIDI test fixtures programmatically.

Creates small, well-defined MIDI files for testing the loader, analyzer,
tokenizer, and section detection modules.
"""

from __future__ import annotations

from pathlib import Path

import mido


def _fixtures_dir() -> Path:
    return Path(__file__).parent


def generate_simple_type0(path: Path | None = None) -> Path:
    """Create a type 0 MIDI file with 2 channels (piano ch0 + bass ch1), 4 bars.

    480 ticks per beat, 4/4 time, tempo 120 BPM.
    Piano (ch0, program 0) plays quarter notes C4-D4-E4-F4 repeated.
    Bass (ch1, program 32) plays whole notes C2-F2-G2-C2.
    Channel 9 gets a single kick drum hit for drum detection testing.
    """
    if path is None:
        path = _fixtures_dir() / "simple_type0.mid"

    mid = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Tempo: 120 BPM = 500000 microseconds per beat
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    # Time signature: 4/4
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    # Key signature: C major
    track.append(mido.MetaMessage("key_signature", key="C", time=0))

    # Program change: channel 0 = Acoustic Grand Piano (program 0)
    track.append(mido.Message("program_change", channel=0, program=0, time=0))
    # Program change: channel 1 = Acoustic Bass (program 32)
    track.append(mido.Message("program_change", channel=1, program=32, time=0))

    # Build interleaved events: piano quarter notes + bass whole notes
    # 4 bars of 4/4 at 480 tpb = 4 * 4 * 480 = 7680 total ticks
    piano_notes = [60, 62, 64, 65] * 4  # C4, D4, E4, F4 repeated
    bass_notes = [36, 41, 43, 36]  # C2, F2, G2, C2 (one per bar)

    # We'll build events as (abs_tick, msg) pairs, then sort and compute deltas
    events: list[tuple[int, mido.Message]] = []

    # Piano: quarter notes (480 ticks each)
    for i, pitch in enumerate(piano_notes):
        start = i * 480
        events.append((start, mido.Message("note_on", channel=0, note=pitch, velocity=80, time=0)))
        events.append(
            (start + 450, mido.Message("note_off", channel=0, note=pitch, velocity=0, time=0))
        )

    # Bass: whole notes (1920 ticks each)
    for i, pitch in enumerate(bass_notes):
        start = i * 1920
        events.append((start, mido.Message("note_on", channel=1, note=pitch, velocity=70, time=0)))
        events.append(
            (start + 1800, mido.Message("note_off", channel=1, note=pitch, velocity=0, time=0))
        )

    # Drum hit on channel 9 (kick drum, note 36) at tick 0
    events.append((0, mido.Message("note_on", channel=9, note=36, velocity=100, time=0)))
    events.append((240, mido.Message("note_off", channel=9, note=36, velocity=0, time=0)))

    # Sort by absolute time, then convert to delta times
    events.sort(key=lambda e: e[0])
    prev_tick = 0
    for abs_tick, msg in events:
        msg.time = abs_tick - prev_tick
        track.append(msg)
        prev_tick = abs_tick

    # End of track
    track.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(str(path))
    return path


def generate_simple_type1(path: Path | None = None) -> Path:
    """Create a type 1 MIDI file with 2 instrument tracks, 4 bars.

    Track 0: conductor track (tempo + time sig only, no notes)
    Track 1: "Trumpet" (program 56), quarter notes
    Track 2: "Trombone" (program 57), half notes
    """
    if path is None:
        path = _fixtures_dir() / "simple_type1.mid"

    mid = mido.MidiFile(type=1, ticks_per_beat=480)

    # Track 0: conductor
    conductor = mido.MidiTrack()
    mid.tracks.append(conductor)
    conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("key_signature", key="C", time=0))
    # Add a marker for section detection testing
    conductor.append(mido.MetaMessage("marker", text="A", time=3840))  # bar 3
    conductor.append(mido.MetaMessage("end_of_track", time=0))

    # Track 1: Trumpet
    trumpet = mido.MidiTrack()
    mid.tracks.append(trumpet)
    trumpet.append(mido.MetaMessage("track_name", name="Trumpet", time=0))
    trumpet.append(mido.Message("program_change", channel=0, program=56, time=0))
    # 16 quarter notes: C5, D5, E5, F5 repeated
    notes = [72, 74, 76, 77] * 4
    for i, pitch in enumerate(notes):
        trumpet.append(
            mido.Message("note_on", channel=0, note=pitch, velocity=90, time=0 if i == 0 else 30)
        )
        trumpet.append(mido.Message("note_off", channel=0, note=pitch, velocity=0, time=450))
    trumpet.append(mido.MetaMessage("end_of_track", time=0))

    # Track 2: Trombone
    trombone = mido.MidiTrack()
    mid.tracks.append(trombone)
    trombone.append(mido.MetaMessage("track_name", name="Trombone", time=0))
    trombone.append(mido.Message("program_change", channel=1, program=57, time=0))
    # 8 half notes: C3, E3, G3, C3 repeated
    notes_tb = [48, 52, 55, 48] * 2
    for i, pitch in enumerate(notes_tb):
        trombone.append(
            mido.Message("note_on", channel=1, note=pitch, velocity=75, time=0 if i == 0 else 60)
        )
        trombone.append(mido.Message("note_off", channel=1, note=pitch, velocity=0, time=900))
    trombone.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(str(path))
    return path


def generate_no_metadata(path: Path | None = None) -> Path:
    """Create a type 1 MIDI file with NO track names and NO program_change.

    Tests the "no metadata" fallback path.
    2 tracks with notes but no instrument identification.
    """
    if path is None:
        path = _fixtures_dir() / "no_metadata.mid"

    mid = mido.MidiFile(type=1, ticks_per_beat=480)

    # Conductor track
    conductor = mido.MidiTrack()
    mid.tracks.append(conductor)
    conductor.append(mido.MetaMessage("set_tempo", tempo=600000, time=0))  # 100 BPM
    conductor.append(mido.MetaMessage("time_signature", numerator=3, denominator=4, time=0))
    conductor.append(mido.MetaMessage("end_of_track", time=0))

    # Track 1: high range (treble), no name, no program
    high = mido.MidiTrack()
    mid.tracks.append(high)
    for i in range(6):  # 6 quarter notes in 3/4 = 2 bars
        high.append(
            mido.Message(
                "note_on", channel=0, note=72 + (i % 5), velocity=80, time=0 if i == 0 else 20
            )
        )
        high.append(mido.Message("note_off", channel=0, note=72 + (i % 5), velocity=0, time=460))
    high.append(mido.MetaMessage("end_of_track", time=0))

    # Track 2: low range (bass), no name, no program
    low = mido.MidiTrack()
    mid.tracks.append(low)
    for i in range(6):
        low.append(
            mido.Message(
                "note_on", channel=1, note=36 + (i % 5), velocity=70, time=0 if i == 0 else 20
            )
        )
        low.append(mido.Message("note_off", channel=1, note=36 + (i % 5), velocity=0, time=460))
    low.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(str(path))
    return path


def generate_all():
    """Generate all test fixtures."""
    fixtures_dir = _fixtures_dir()
    generate_simple_type0(fixtures_dir / "simple_type0.mid")
    generate_simple_type1(fixtures_dir / "simple_type1.mid")
    generate_no_metadata(fixtures_dir / "no_metadata.mid")
    print(f"Generated MIDI fixtures in {fixtures_dir}")


if __name__ == "__main__":
    generate_all()
