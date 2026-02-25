"""JSON-to-music21 builder.

Stub for TDD RED phase -- not yet implemented.
"""

ARTICULATION_MAP: dict = {}
EXPRESSION_MAP: dict = {}


def build_note(note_event):
    raise NotImplementedError


def build_measure(measure_data):
    raise NotImplementedError


def build_part(instrument_name, sections, *, key, time_sig, tempo):
    raise NotImplementedError


def build_score(*, all_sections, instruments, key, time_sig, tempo):
    raise NotImplementedError
