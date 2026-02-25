"""MIDI handling subsystem for Engrave.

Provides MIDI loading, normalization, musical analysis, text tokenization,
and section boundary detection.
"""

from engrave.midi.analyzer import MidiAnalysis, analyze_midi
from engrave.midi.loader import MidiTrackInfo, NoteEvent, load_midi
from engrave.midi.sections import SectionBoundary, detect_sections
from engrave.midi.tokenizer import tokenize_section_for_prompt

__all__ = [
    "MidiAnalysis",
    "MidiTrackInfo",
    "NoteEvent",
    "SectionBoundary",
    "analyze_midi",
    "detect_sections",
    "load_midi",
    "tokenize_section_for_prompt",
]
