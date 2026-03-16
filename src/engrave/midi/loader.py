"""MIDI loading and type 0/1 normalization using mido.

Loads MIDI files and normalizes both type 0 (single track, interleaved channels)
and type 1 (multi-track) into a consistent list of MidiTrackInfo objects with
NoteEvent data and instrument metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import mido
import mido.midifiles.meta as _mido_meta

logger = logging.getLogger(__name__)


# Monkey-patch mido's key signature lookup to tolerate invalid values.
# Some DAW-exported MIDI files contain out-of-range key signature bytes
# (e.g. 18 sharps) that mido cannot decode, causing a hard crash.
class _LenientKeySignatureDict(dict):
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            logger.warning("Unknown MIDI key signature %s, defaulting to C major", key)
            return "C"


_mido_meta._key_signature_decode = _LenientKeySignatureDict(_mido_meta._key_signature_decode)

# General MIDI instrument names (program 0-127)
GM_INSTRUMENTS: dict[int, str] = {
    0: "Acoustic Grand Piano",
    1: "Bright Acoustic Piano",
    2: "Electric Grand Piano",
    3: "Honky-tonk Piano",
    4: "Electric Piano 1",
    5: "Electric Piano 2",
    6: "Harpsichord",
    7: "Clavinet",
    8: "Celesta",
    9: "Glockenspiel",
    10: "Music Box",
    11: "Vibraphone",
    12: "Marimba",
    13: "Xylophone",
    14: "Tubular Bells",
    15: "Dulcimer",
    16: "Drawbar Organ",
    17: "Percussive Organ",
    18: "Rock Organ",
    19: "Church Organ",
    20: "Reed Organ",
    21: "Accordion",
    22: "Harmonica",
    23: "Tango Accordion",
    24: "Acoustic Guitar (nylon)",
    25: "Acoustic Guitar (steel)",
    26: "Electric Guitar (jazz)",
    27: "Electric Guitar (clean)",
    28: "Electric Guitar (muted)",
    29: "Overdriven Guitar",
    30: "Distortion Guitar",
    31: "Guitar Harmonics",
    32: "Acoustic Bass",
    33: "Electric Bass (finger)",
    34: "Electric Bass (pick)",
    35: "Fretless Bass",
    36: "Slap Bass 1",
    37: "Slap Bass 2",
    38: "Synth Bass 1",
    39: "Synth Bass 2",
    40: "Violin",
    41: "Viola",
    42: "Cello",
    43: "Contrabass",
    44: "Tremolo Strings",
    45: "Pizzicato Strings",
    46: "Orchestral Harp",
    47: "Timpani",
    48: "String Ensemble 1",
    49: "String Ensemble 2",
    50: "Synth Strings 1",
    51: "Synth Strings 2",
    52: "Choir Aahs",
    53: "Voice Oohs",
    54: "Synth Choir",
    55: "Orchestra Hit",
    56: "Trumpet",
    57: "Trombone",
    58: "Tuba",
    59: "Muted Trumpet",
    60: "French Horn",
    61: "Brass Section",
    62: "Synth Brass 1",
    63: "Synth Brass 2",
    64: "Soprano Sax",
    65: "Alto Sax",
    66: "Tenor Sax",
    67: "Baritone Sax",
    68: "Oboe",
    69: "English Horn",
    70: "Bassoon",
    71: "Clarinet",
    72: "Piccolo",
    73: "Flute",
    74: "Recorder",
    75: "Pan Flute",
    76: "Blown Bottle",
    77: "Shakuhachi",
    78: "Whistle",
    79: "Ocarina",
    80: "Lead 1 (square)",
    81: "Lead 2 (sawtooth)",
    82: "Lead 3 (calliope)",
    83: "Lead 4 (chiff)",
    84: "Lead 5 (charang)",
    85: "Lead 6 (voice)",
    86: "Lead 7 (fifths)",
    87: "Lead 8 (bass + lead)",
    88: "Pad 1 (new age)",
    89: "Pad 2 (warm)",
    90: "Pad 3 (polysynth)",
    91: "Pad 4 (choir)",
    92: "Pad 5 (bowed)",
    93: "Pad 6 (metallic)",
    94: "Pad 7 (halo)",
    95: "Pad 8 (sweep)",
    96: "FX 1 (rain)",
    97: "FX 2 (soundtrack)",
    98: "FX 3 (crystal)",
    99: "FX 4 (atmosphere)",
    100: "FX 5 (brightness)",
    101: "FX 6 (goblins)",
    102: "FX 7 (echoes)",
    103: "FX 8 (sci-fi)",
    104: "Sitar",
    105: "Banjo",
    106: "Shamisen",
    107: "Koto",
    108: "Kalimba",
    109: "Bagpipe",
    110: "Fiddle",
    111: "Shanai",
    112: "Tinkle Bell",
    113: "Agogo",
    114: "Steel Drums",
    115: "Woodblock",
    116: "Taiko Drum",
    117: "Melodic Tom",
    118: "Synth Drum",
    119: "Reverse Cymbal",
    120: "Guitar Fret Noise",
    121: "Breath Noise",
    122: "Seashore",
    123: "Bird Tweet",
    124: "Telephone Ring",
    125: "Helicopter",
    126: "Applause",
    127: "Gunshot",
}


@dataclass
class NoteEvent:
    """Single note extracted from MIDI."""

    pitch: int  # MIDI pitch (0-127)
    start_tick: int  # Start time in ticks
    duration_ticks: int  # Duration in ticks
    velocity: int  # Velocity (0-127)
    channel: int  # MIDI channel (0-15)


@dataclass
class MidiTrackInfo:
    """Normalized track with instrument metadata."""

    track_index: int
    channel: int | None
    program: int | None
    instrument_name: str | None
    notes: list[NoteEvent] = field(default_factory=list)
    is_drum: bool = False


def _gm_instrument_name(program: int) -> str:
    """Lookup General MIDI instrument name from program number."""
    return GM_INSTRUMENTS.get(program, f"Program {program}")


def load_midi(path: str) -> tuple[list[MidiTrackInfo], dict]:
    """Load MIDI file and return normalized tracks + global metadata.

    Args:
        path: Path to the MIDI file.

    Returns:
        Tuple of (list of MidiTrackInfo, metadata dict).
        Metadata contains: type, ticks_per_beat, num_tracks.

    Raises:
        ValueError: If MIDI type is not 0 or 1.
    """
    mid = mido.MidiFile(path)
    metadata = {
        "type": mid.type,
        "ticks_per_beat": mid.ticks_per_beat,
        "num_tracks": len(mid.tracks),
    }

    if mid.type == 0:
        tracks = _split_type0_by_channel(mid.tracks[0])
    elif mid.type == 1:
        tracks = _parse_type1_tracks(mid.tracks)
    else:
        raise ValueError(f"MIDI type {mid.type} not supported (only type 0 and 1)")

    return tracks, metadata


def _split_type0_by_channel(track: mido.MidiTrack) -> list[MidiTrackInfo]:
    """Split a type 0 single track into separate tracks by MIDI channel."""
    channel_notes: dict[int, list[NoteEvent]] = {}
    channel_programs: dict[int, int] = {}
    abs_time = 0
    # Track pending note-on events: (channel, pitch) -> (start_tick, velocity)
    pending: dict[tuple[int, int], tuple[int, int]] = {}

    for msg in track:
        abs_time += msg.time
        if msg.type == "program_change":
            channel_programs[msg.channel] = msg.program
        elif msg.type == "note_on" and msg.velocity > 0:
            pending[(msg.channel, msg.note)] = (abs_time, msg.velocity)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            if key in pending:
                start_tick, velocity = pending.pop(key)
                channel_notes.setdefault(msg.channel, []).append(
                    NoteEvent(
                        pitch=msg.note,
                        start_tick=start_tick,
                        duration_ticks=abs_time - start_tick,
                        velocity=velocity,
                        channel=msg.channel,
                    )
                )

    tracks = []
    for idx, ch in enumerate(sorted(channel_notes.keys())):
        program = channel_programs.get(ch)
        tracks.append(
            MidiTrackInfo(
                track_index=idx,
                channel=ch,
                program=program,
                instrument_name=_gm_instrument_name(program) if program is not None else None,
                notes=sorted(channel_notes[ch], key=lambda n: n.start_tick),
                is_drum=(ch == 9),
            )
        )

    return tracks


def _parse_type1_tracks(tracks: list[mido.MidiTrack]) -> list[MidiTrackInfo]:
    """Parse type 1 MIDI tracks, skipping empty (conductor) tracks."""
    result = []
    track_idx = 0

    for track in tracks:
        track_name: str | None = None
        program: int | None = None
        channel: int | None = None
        notes: list[NoteEvent] = []
        abs_time = 0
        pending: dict[tuple[int, int], tuple[int, int]] = {}

        for msg in track:
            abs_time += msg.time

            if msg.type == "track_name":
                track_name = msg.name
            elif msg.type == "program_change":
                program = msg.program
                channel = msg.channel
            elif msg.type == "note_on" and msg.velocity > 0:
                if channel is None:
                    channel = msg.channel
                pending[(msg.channel, msg.note)] = (abs_time, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in pending:
                    start_tick, velocity = pending.pop(key)
                    if channel is None:
                        channel = msg.channel
                    notes.append(
                        NoteEvent(
                            pitch=msg.note,
                            start_tick=start_tick,
                            duration_ticks=abs_time - start_tick,
                            velocity=velocity,
                            channel=msg.channel,
                        )
                    )

        # Skip tracks with no notes (conductor/tempo tracks)
        if not notes:
            continue

        # Determine instrument name: prefer track_name, then GM lookup
        instrument_name = track_name
        if instrument_name is None and program is not None:
            instrument_name = _gm_instrument_name(program)

        result.append(
            MidiTrackInfo(
                track_index=track_idx,
                channel=channel,
                program=program,
                instrument_name=instrument_name,
                notes=sorted(notes, key=lambda n: n.start_tick),
                is_drum=(channel == 9) if channel is not None else False,
            )
        )
        track_idx += 1

    if not result:
        logger.warning("No tracks with note events found in MIDI file")

    return result
