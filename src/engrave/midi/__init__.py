"""MIDI handling subsystem for Engrave.

Provides MIDI loading, normalization, musical analysis, text tokenization,
and section boundary detection.
"""

from engrave.midi.loader import MidiTrackInfo, NoteEvent, load_midi

__all__ = [
    "MidiTrackInfo",
    "NoteEvent",
    "load_midi",
]
