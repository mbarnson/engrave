"""MIDI-to-text tokenization for LLM prompts.

Converts MIDI note events into human-readable text with LilyPond pitch
names, quantized durations, dynamic markings, and explicit rests. Output
is grouped by bar number for direct use in generation prompts.
"""

from __future__ import annotations

from collections import defaultdict

from engrave.midi.loader import NoteEvent

# LilyPond pitch names (sharps only, no enharmonic context yet)
_NOTE_NAMES = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]

# Standard LilyPond durations as tick multipliers relative to a quarter note
# (duration_number, ticks_as_fraction_of_quarter)
_DURATIONS = [
    (1, 4.0),  # whole note = 4 quarter notes
    (2, 2.0),  # half note
    (4, 1.0),  # quarter note
    (8, 0.5),  # eighth note
    (16, 0.25),  # sixteenth note
]

# Dotted versions (1.5x the base duration)
_DOTTED_DURATIONS = [(d, t * 1.5) for d, t in _DURATIONS]

# Velocity to dynamic mapping
_VELOCITY_DYNAMICS = [
    (0, "\\ppp"),
    (32, "\\pp"),
    (48, "\\p"),
    (64, "\\mp"),
    (80, "\\mf"),
    (96, "\\f"),
    (112, "\\ff"),
    (127, "\\fff"),
]


def _midi_to_lilypond_pitch(midi_number: int) -> str:
    """Convert MIDI pitch number to LilyPond absolute pitch name.

    LilyPond absolute pitch convention:
    - c (no mark) = MIDI 48-59 (C3 octave)
    - c' = MIDI 60-71 (C4 / middle C octave)
    - c'' = MIDI 72-83 (C5 octave)
    - c, = MIDI 36-47 (C2 octave)
    - c,, = MIDI 24-35 (C1 octave)
    """
    pitch_class = midi_number % 12
    octave = midi_number // 12

    name = _NOTE_NAMES[pitch_class]

    # LilyPond octave reference: c (no mark) = octave 3 (MIDI 48-59)
    # Octave 0 = MIDI 0-11, so LilyPond octave offset = midi_octave - 3
    # MIDI octave numbering: octave = midi_number // 12
    # MIDI 48 = octave 4 in MIDI standard, but in mido/pretty_midi:
    # MIDI note 60 = C4, octave = 60 // 12 = 5
    # So reference octave for c (no mark) is 4 (MIDI 48-59 range)
    ly_octave_offset = octave - 4

    if ly_octave_offset > 0:
        name += "'" * ly_octave_offset
    elif ly_octave_offset < 0:
        name += "," * abs(ly_octave_offset)

    return name


def _quantize_duration(duration_ticks: int, ticks_per_beat: int) -> str:
    """Quantize a tick duration to the nearest LilyPond duration string.

    Returns the duration as a string like "4" (quarter), "8" (eighth),
    "4." (dotted quarter), etc.
    """
    # Convert ticks to quarter-note fraction
    quarter_fraction = duration_ticks / ticks_per_beat

    # Try dotted durations first (they're more specific)
    best_dur = "4"
    best_diff = float("inf")

    for dur_num, dur_fraction in _DOTTED_DURATIONS:
        diff = abs(quarter_fraction - dur_fraction)
        if diff < best_diff:
            best_diff = diff
            best_dur = f"{dur_num}."

    # Try standard durations
    for dur_num, dur_fraction in _DURATIONS:
        diff = abs(quarter_fraction - dur_fraction)
        if diff < best_diff:
            best_diff = diff
            best_dur = str(dur_num)

    return best_dur


def _velocity_to_dynamic(velocity: int) -> str:
    """Map velocity to LilyPond dynamic marking."""
    result = "\\mf"  # default
    for threshold, dynamic in _VELOCITY_DYNAMICS:
        if velocity >= threshold:
            result = dynamic
    return result


def _tick_to_bar(tick: int, ticks_per_beat: int, beats_per_bar: int) -> int:
    """Convert a tick position to a 1-based bar number."""
    ticks_per_bar = ticks_per_beat * beats_per_bar
    return (tick // ticks_per_bar) + 1


def tokenize_section_for_prompt(
    notes: list[NoteEvent],
    time_sig: tuple[int, int],
    key: str,
    bars: tuple[int, int],
    ticks_per_beat: int,
) -> str:
    """Convert MIDI notes to LLM-readable text representation.

    Output format per bar:
        bar N: pitch(duration, dynamic) pitch(duration) ...

    Args:
        notes: List of NoteEvent objects to tokenize.
        time_sig: Time signature as (numerator, denominator).
        key: Key signature string (unused for now, reserved for enharmonic).
        bars: Tuple of (start_bar, end_bar) inclusive.
        ticks_per_beat: MIDI ticks per quarter note.

    Returns:
        Human-readable text representation of the notes.
    """
    numerator, denominator = time_sig
    # Beats per bar in terms of quarter notes
    # e.g., 4/4 = 4 beats, 3/4 = 3 beats, 6/8 = 3 quarter-note equivalents
    beats_per_bar = numerator * (4 / denominator)
    ticks_per_bar = int(ticks_per_beat * beats_per_bar)

    start_bar, end_bar = bars

    # Group notes by bar
    bar_notes: dict[int, list[NoteEvent]] = defaultdict(list)
    for note in notes:
        bar_num = _tick_to_bar(note.start_tick, ticks_per_beat, int(beats_per_bar))
        if start_bar <= bar_num <= end_bar:
            bar_notes[bar_num].append(note)

    # Sort notes within each bar by start_tick
    for bar_num in bar_notes:
        bar_notes[bar_num].sort(key=lambda n: n.start_tick)

    # Build output
    output_lines: list[str] = []
    prev_velocity: int | None = None

    for bar_num in range(start_bar, end_bar + 1):
        tokens: list[str] = []
        bar_start_tick = (bar_num - 1) * ticks_per_bar
        notes_in_bar = bar_notes.get(bar_num, [])

        current_tick = bar_start_tick

        for note in notes_in_bar:
            # Insert rest if there's a gap before this note
            gap = note.start_tick - current_tick
            if gap > ticks_per_beat // 8:  # Ignore tiny gaps (< 32nd note)
                rest_dur = _quantize_duration(gap, ticks_per_beat)
                tokens.append(f"r{rest_dur}")

            # Build note token
            pitch_name = _midi_to_lilypond_pitch(note.pitch)
            duration = _quantize_duration(note.duration_ticks, ticks_per_beat)

            # Include dynamic only when velocity changes
            if prev_velocity is None or abs(note.velocity - prev_velocity) > 8:
                dynamic = _velocity_to_dynamic(note.velocity)
                tokens.append(f"{pitch_name}{duration}{dynamic}")
                prev_velocity = note.velocity
            else:
                tokens.append(f"{pitch_name}{duration}")

            current_tick = note.start_tick + note.duration_ticks

        # Fill remaining bar with rest if notes don't fill it
        bar_end_tick = bar_num * ticks_per_bar
        remaining = bar_end_tick - current_tick
        if remaining > ticks_per_beat // 8 and tokens:
            rest_dur = _quantize_duration(remaining, ticks_per_beat)
            tokens.append(f"r{rest_dur}")

        if tokens:
            output_lines.append(f"bar {bar_num}: {' '.join(tokens)}")
        else:
            # Empty bar = full rest
            whole_rest_dur = _quantize_duration(ticks_per_bar, ticks_per_beat)
            output_lines.append(f"bar {bar_num}: r{whole_rest_dur}")

    return "\n".join(output_lines)
