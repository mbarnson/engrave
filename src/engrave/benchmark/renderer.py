"""MIDI-to-audio rendering via FluidSynth for benchmark ground truth generation.

Uses midi2audio to invoke FluidSynth, converting MIDI files to WAV audio
with a configurable SoundFont. This provides deterministic ground truth
audio from corpus MIDI for closed-loop pipeline evaluation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from midi2audio import FluidSynth

logger = logging.getLogger(__name__)


def render_midi_to_audio(
    midi_path: Path,
    wav_path: Path,
    soundfont: str | None = None,
) -> Path:
    """Render a MIDI file to WAV audio via FluidSynth.

    Args:
        midi_path: Path to the input MIDI file.
        wav_path: Path for the output WAV file.
        soundfont: Path to a SoundFont (.sf2) file. If None, uses
            FluidSynth's default SoundFont.

    Returns:
        Path to the rendered WAV file (same as ``wav_path``).

    Raises:
        FileNotFoundError: If ``midi_path`` does not exist.
    """
    if not midi_path.exists():
        msg = f"MIDI file not found: {midi_path}"
        raise FileNotFoundError(msg)

    # Create parent directory for output if needed
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Rendering MIDI to audio: %s -> %s", midi_path, wav_path)

    fs = FluidSynth(soundfont) if soundfont is not None else FluidSynth()

    fs.midi_to_audio(str(midi_path), str(wav_path))

    return wav_path
