"""Benchmark harness for closed-loop evaluation of the audio pipeline.

Renders corpus MIDI to audio via FluidSynth, round-trips through
separation + transcription, and diffs output MIDI against ground truth
using mir_eval. Results are stored as structured JSON for systematic
model comparison.
"""

from engrave.benchmark.evaluator import MidiDiffResult, diff_midi
from engrave.benchmark.harness import BenchmarkHarness
from engrave.benchmark.models import AggregateScore, BenchmarkRun, StemMetrics
from engrave.benchmark.renderer import render_midi_to_audio

__all__ = [
    "AggregateScore",
    "BenchmarkHarness",
    "BenchmarkRun",
    "MidiDiffResult",
    "StemMetrics",
    "diff_midi",
    "render_midi_to_audio",
]
