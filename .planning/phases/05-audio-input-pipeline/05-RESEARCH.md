# Phase 5: Audio Input Pipeline - Research

**Researched:** 2026-02-24
**Domain:** Audio source separation, AMT (automatic music transcription), audio ingestion, benchmarking harness
**Confidence:** MEDIUM (libraries verified via PyPI/GitHub; hierarchical separation and ONNX spike need empirical validation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Experimentation Harness:**
  - Primary comparison unit: MIDI diff -- note accuracy, onset timing, phantom notes, missed notes between output MIDI and reference MIDI
  - Closed-loop test design: Corpus MIDI (from Phase 2 PDMX/Mutopia) -> render to audio (FluidSynth/timidity) -> run separation -> run transcription -> diff output MIDI against original source MIDI
  - Two test loops: FluidSynth/timidity (deterministic regression) and Suno-generated big band tracks (realistic quality assessment)
  - Pipeline-integrated harness (runs as a mode of the pipeline, not standalone)
  - LLM judge for large-scale evaluation (200K+ corpus)
  - Results storage: structured JSON per run + CLI summary (`engrave benchmark --compare`)
  - Include FluidSynth/timidity MIDI-to-audio rendering as a utility in Phase 5
- **Separation Strategy:**
  - Per-stem model routing via engrave.toml
  - Multi-model per stem: config accepts a list, run ALL, save ALL as separate artifacts
  - Hierarchical separation: ordered list of (model, input_stem, output_stems) operations
  - Optimization metric: downstream MIDI transcription accuracy, NOT SDR
- **Transcription Approach:**
  - Pluggable `Transcriber` protocol: WAV in, MIDI out
  - First backend: Basic Pitch via subprocess to isolated Python 3.10 venv (research spike for ONNX on Python 3.12 first)
  - Quality metadata annotations: numerical scores per stem (note density, pitch range violations, onset clustering, velocity variance, duration distribution)
  - No automatic fallback in v1 -- quality metadata travels downstream
  - The LLM IS the fallback (Stage 4 interprets ambiguous MIDI through audio description + context)

### Claude's Discretion
- Audio format normalization details (sample rate, channel handling, bit depth)
- YouTube extraction implementation (yt-dlp API vs CLI)
- File size limits and handling of very long recordings
- FluidSynth vs timidity choice for MIDI-to-audio rendering
- Exact JSON schema for benchmark result files
- MIDI post-processing details (pitch bend handling, drum map normalization)

### Deferred Ideas (OUT OF SCOPE)
- Ensemble/merge combination logic for multi-model stems (Phase 5.1)
- Alternative transcription backends (YourMT3+, future AMT models) -- Transcriber protocol enables this later
- Post-Phase 5 spike: separator -> AMT -> MIDI vs ground truth benchmark (already noted in memory)
- Suno-sourced test corpus curation (user generates tracks, not automated)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FNDN-02 | System accepts audio files (MP3, WAV, AIFF, FLAC) as input and routes them through the full audio processing pipeline | Audio normalization via pydub/soundfile, format detection, pipeline routing architecture |
| FNDN-03 | System accepts YouTube URLs as input via yt-dlp, extracts audio, and routes through audio processing pipeline | yt-dlp Python API with FFmpegExtractAudio postprocessor |
| AUDP-01 | System performs source separation on audio input via best-available model per stem using audio-separator | audio-separator Separator class with per-stem model routing, hierarchical cascade pattern |
| AUDP-02 | System transcribes separated stems to MIDI via Basic Pitch, extracting pitch, timing, and velocity per voice | basic-pitch predict() API returning pretty_midi.PrettyMIDI + note_events with pitch bends, ONNX spike for Python 3.12 |
</phase_requirements>

## Summary

Phase 5 builds the forward audio pipeline: audio files or YouTube URLs enter the system, get separated into stems, and each stem is transcribed to MIDI that feeds into the existing Phase 3 MIDI-to-LilyPond pipeline. Alongside this, an experimentation harness enables closed-loop benchmarking of the separation and transcription chain.

The core technical challenges are: (1) orchestrating `audio-separator` in a hierarchical cascade where outputs of one separation pass become inputs to the next, (2) integrating `basic-pitch` despite its Python 3.10 constraint on Apple Silicon (with a spike to test ONNX on Python 3.12 first), (3) building the benchmark harness that renders corpus MIDI to audio via FluidSynth and diffs the round-tripped MIDI back against ground truth using `mir_eval`, and (4) making the entire separation and transcription chain configurable per-stem via `engrave.toml`.

**Primary recommendation:** Build the pipeline as a sequence of protocol-based stages (`Normalizer -> Separator -> Transcriber -> QualityAnnotator`) where each stage is independently configurable and testable. Start with the ONNX spike for basic-pitch -- if ONNX works on Python 3.12 (onnxruntime supports it), the isolated venv subprocess path becomes unnecessary. If not, implement subprocess invocation with JSON-over-stdin/stdout for clean IPC.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| audio-separator | latest (PyPI) | Multi-model source separation | Wraps BS-RoFormer, Mel-Band RoFormer, HTDemucs ft, MDX-NET, SCNet under one API. Per-stem model selection. Auto-downloads model weights on first use. |
| basic-pitch | 0.4.0 | Audio-to-MIDI transcription | Spotify's lightweight CNN AMT. Returns `pretty_midi.PrettyMIDI` + note events with pitch bends. <20MB model, <17K params. Best for single-instrument stems. |
| yt-dlp | 2026.02.x | YouTube audio extraction | `YoutubeDL` Python API with `FFmpegExtractAudio` postprocessor. Weekly releases, actively maintained. |
| mir_eval | 0.8.x | MIDI transcription evaluation | `precision_recall_f1_overlap()` computes note-level accuracy with configurable onset/pitch tolerance. Industry standard for AMT benchmarks. |
| midi2audio | 0.4.0 | MIDI-to-audio rendering (FluidSynth wrapper) | `FluidSynth().midi_to_audio(midi_path, wav_path)`. Requires FluidSynth system binary + SoundFont file. Used for benchmark harness ground-truth audio generation. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydub | 0.25.x | Audio format normalization | Read MP3/AIFF/FLAC, normalize to WAV mono 44.1kHz. Wraps ffmpeg. Handles channel downmixing, sample rate conversion. |
| soundfile | 0.12.x | WAV/FLAC read/write | Lower-level alternative to pydub for WAV/FLAC when ffmpeg subprocess overhead matters. Wraps libsndfile. |
| pretty_midi | 0.2.11 | MIDI manipulation/analysis | Already in project. basic-pitch returns `pretty_midi.PrettyMIDI` objects directly. Use for post-transcription MIDI inspection and quality annotation. |
| onnxruntime | 1.24.x | ONNX model inference | Supports Python 3.12+. If basic-pitch ONNX backend works on Python 3.12 with onnxruntime, no isolated venv needed. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| midi2audio (FluidSynth) | timidity++ CLI | timidity is subprocess-only, no Python API. FluidSynth has midi2audio wrapper. Both produce deterministic output. Use FluidSynth for simplicity. |
| pydub | soundfile + ffmpeg subprocess | soundfile can't read MP3/AIFF natively. pydub handles all formats via ffmpeg with a clean API. |
| basic-pitch | basic-pitch-torch | PyTorch port (gudgud96/basic-pitch-torch). Only 2 commits, no pitch bend support mentioned, unclear maintenance. Too risky for primary backend. |
| basic-pitch subprocess | basic-pitch ONNX in-process | ONNX spike may eliminate the subprocess boundary entirely. Spike first, decide after. |

**Installation:**
```bash
# Main project dependencies (Python 3.12)
uv add audio-separator yt-dlp pydub midi2audio mir-eval

# If ONNX spike succeeds (basic-pitch runs in-process):
uv add basic-pitch onnxruntime

# If ONNX spike fails (isolated venv):
# Create Python 3.10 venv externally, install basic-pitch there
# Invoke via subprocess from main project

# System dependencies
brew install ffmpeg fluidsynth
# Download a GM SoundFont (e.g., FluidR3_GM.sf2 or MuseScore_General.sf3)
```

## Architecture Patterns

### Recommended Project Structure
```
src/engrave/
├── audio/
│   ├── __init__.py           # Public API: process_audio, extract_youtube
│   ├── normalizer.py         # Audio format detection, normalization to WAV
│   ├── separator.py          # SeparationConfig, run_separation (hierarchical cascade)
│   ├── transcriber.py        # Transcriber protocol, BasicPitchTranscriber
│   ├── quality.py            # Post-transcription quality annotation metrics
│   ├── youtube.py            # YouTube URL extraction via yt-dlp
│   └── pipeline.py           # AudioPipeline orchestration: normalize -> separate -> transcribe -> annotate
├── benchmark/
│   ├── __init__.py           # Public API: run_benchmark, compare_results
│   ├── renderer.py           # MIDI-to-audio via FluidSynth (ground truth generation)
│   ├── evaluator.py          # mir_eval MIDI diff (precision, recall, F1)
│   ├── harness.py            # Closed-loop benchmark orchestration
│   └── models.py             # BenchmarkRun, StemResult, AggregateScore data models
└── ...
```

### Pattern 1: Protocol-Based Stage Pipeline
**What:** Each pipeline stage defines a Protocol (structural subtyping) with a `__call__` or `process` method. Stages compose via sequential invocation.
**When to use:** All audio processing orchestration.
**Example:**
```python
from typing import Protocol, runtime_checkable
from pathlib import Path
from dataclasses import dataclass

@runtime_checkable
class Transcriber(Protocol):
    """WAV path in, MIDI path out."""
    def transcribe(self, wav_path: Path, output_dir: Path) -> Path:
        """Transcribe audio to MIDI, return path to output .mid file."""
        ...

@dataclass
class BasicPitchTranscriber:
    """Basic Pitch backend, invoked via subprocess or in-process."""
    venv_python: Path | None = None  # None = in-process (ONNX), Path = subprocess

    def transcribe(self, wav_path: Path, output_dir: Path) -> Path:
        midi_path = output_dir / f"{wav_path.stem}.mid"
        if self.venv_python:
            # Subprocess path for Python 3.10 venv
            self._transcribe_subprocess(wav_path, midi_path)
        else:
            # In-process path (ONNX on Python 3.12)
            self._transcribe_inprocess(wav_path, midi_path)
        return midi_path
```

### Pattern 2: Hierarchical Separation Cascade
**What:** Separation config defines an ordered list of operations. Each operation specifies (model, input_stem, output_stems). The cascade feeds outputs of one pass as inputs to the next.
**When to use:** Big band or dense ensemble separation where the 4-stem "other" bin needs further splitting.
**Example:**
```python
@dataclass
class SeparationStep:
    """One step in a hierarchical separation cascade."""
    model: str                    # Model filename for audio-separator
    input_stem: str               # Which stem to process ("mix" for original, or stem name from prior step)
    output_stems: list[str]       # Expected output stem names

# Example big band config (from engrave.toml):
# [[audio.separation.steps]]
# model = "htdemucs_ft.yaml"
# input_stem = "mix"
# output_stems = ["drums", "bass", "vocals", "other"]
#
# [[audio.separation.steps]]
# model = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
# input_stem = "other"
# output_stems = ["piano", "residual"]
```

### Pattern 3: Job Directory Structure
**What:** Each pipeline invocation creates a timestamped job directory containing all intermediate artifacts. Enables inspection, debugging, and multi-model comparison.
**When to use:** All pipeline runs (both normal and benchmark).
**Example:**
```
jobs/
└── 2026-02-24T15-30-00_my-song/
    ├── input.wav                          # Normalized input
    ├── separation/
    │   ├── step-01_htdemucs_ft/
    │   │   ├── drums.wav
    │   │   ├── bass.wav
    │   │   ├── vocals.wav
    │   │   └── other.wav
    │   └── step-02_bs_roformer/
    │       ├── piano.wav
    │       └── residual.wav
    ├── transcription/
    │   ├── drums.mid
    │   ├── bass.mid
    │   ├── vocals.mid
    │   ├── piano.mid
    │   └── residual.mid
    ├── quality/
    │   └── stem_quality.json              # Per-stem quality annotations
    └── metadata.json                      # Pipeline config, timing, versions
```

### Pattern 4: Subprocess IPC for Isolated Venv
**What:** When basic-pitch must run in a Python 3.10 venv, use subprocess with JSON communication over stdin/stdout.
**When to use:** Only if ONNX spike fails (basic-pitch cannot run in-process on Python 3.12).
**Example:**
```python
import json
import subprocess
from pathlib import Path

def _transcribe_subprocess(self, wav_path: Path, midi_path: Path) -> None:
    """Run basic-pitch in isolated Python 3.10 venv via subprocess."""
    cmd = [
        str(self.venv_python),
        "-m", "basic_pitch",
        str(midi_path.parent),  # output directory
        str(wav_path),
        "--model-serialization", "onnx",  # Force ONNX even on macOS
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"basic-pitch failed: {result.stderr}")
```

### Anti-Patterns to Avoid
- **Loading audio-separator models globally:** Models are 4-6GB each. Load per-step, unload after. The Separator class handles this -- instantiate once, call `load_model()` per step, then `separate()`. Do not keep multiple models resident.
- **Running basic-pitch predict() without the Model() pre-load:** If processing multiple stems, load the Model once and pass it to each `predict()` call. Avoids redundant model initialization.
- **Storing benchmark WAV files in git:** Job directories contain large WAV intermediates. Use `.gitignore` for job directories; only commit JSON results.
- **Hardcoding model filenames:** All model names go in `engrave.toml` config. The code should never contain a model filename literal.
- **Skipping normalization:** audio-separator and basic-pitch have specific sample rate expectations (44.1kHz). Always normalize input audio before pipeline entry.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio format detection/conversion | Custom ffmpeg wrapper | `pydub.AudioSegment.from_file()` | Handles MP3/WAV/AIFF/FLAC/OGG automatically, detects format from header, wraps ffmpeg correctly |
| MIDI transcription accuracy metrics | Custom note-matching algorithm | `mir_eval.transcription.precision_recall_f1_overlap()` | Configurable onset tolerance (50ms default), pitch tolerance, offset matching. Industry standard. Edge cases around overlapping notes, grace notes, ties are all handled. |
| MIDI-to-audio rendering | Custom FluidSynth subprocess | `midi2audio.FluidSynth().midi_to_audio()` | Handles SoundFont loading, sample rate, gain. One-liner. |
| YouTube audio extraction | Custom yt-dlp subprocess | `yt_dlp.YoutubeDL(opts).download([url])` | Python API handles format selection, postprocessing, error handling. Much more robust than subprocess. |
| Audio source separation | Custom model loading | `audio_separator.separator.Separator` | Auto-downloads models, handles GPU/CPU selection, normalizes output format. |

**Key insight:** Every "simple wrapper" in audio processing hides 10+ edge cases (sample rate mismatch, channel count, bit depth, silence padding, clipping). Use established libraries.

## Common Pitfalls

### Pitfall 1: basic-pitch Python Version Mismatch
**What goes wrong:** Installing basic-pitch in the main Python 3.12 venv fails or produces silent errors on Apple Silicon.
**Why it happens:** basic-pitch 0.4.0 officially supports Python 3.8-3.11 only. On Apple Silicon Macs, only Python 3.10 is officially supported. The TensorFlow dependency is the root cause.
**How to avoid:** Run the ONNX spike first. If `pip install basic-pitch onnxruntime` in Python 3.12 works and `predict()` produces correct output using `--model-serialization onnx`, use in-process. If not, create a Python 3.10 venv (`python3.10 -m venv .venvs/basic-pitch`) and invoke via subprocess. Test both paths in CI.
**Warning signs:** Import errors mentioning TensorFlow, CoreML, or `tensorflow.lite`. Silently wrong MIDI output (all zeros, no notes detected).

### Pitfall 2: audio-separator Model Memory Exhaustion
**What goes wrong:** Loading multiple separation models simultaneously exhausts unified memory on Apple Silicon.
**Why it happens:** Each model is 4-6GB. The hierarchical cascade needs to run sequentially, not in parallel.
**How to avoid:** Load one model at a time via `separator.load_model()`. After separation, the Separator class internally handles model lifecycle. Do NOT instantiate multiple Separator objects simultaneously.
**Warning signs:** macOS memory pressure warnings, process killed by OOM, swap thrashing.

### Pitfall 3: Sample Rate Mismatch in Pipeline
**What goes wrong:** audio-separator outputs at one sample rate, basic-pitch expects another, and the MIDI timing is wrong.
**Why it happens:** Different models expect different sample rates. BS-RoFormer processes at 44.1kHz. basic-pitch expects 22.05kHz internally (resamples from input).
**How to avoid:** Normalize all audio to 44.1kHz WAV mono at pipeline entry. audio-separator's `sample_rate` parameter controls output. basic-pitch handles internal resampling from its input.
**Warning signs:** MIDI notes with systematically wrong onset times (all shifted by a constant factor like 2x).

### Pitfall 4: FluidSynth SoundFont Not Found
**What goes wrong:** `midi2audio.FluidSynth()` raises an error because no default SoundFont is configured.
**Why it happens:** FluidSynth needs a `.sf2` or `.sf3` SoundFont file. midi2audio looks at `~/.fluidsynth/default_sound_font.sf2`.
**How to avoid:** Download a GM SoundFont (FluidR3_GM.sf2 or MuseScore_General.sf3) and either symlink to the default path or pass explicitly: `FluidSynth('/path/to/soundfont.sf2')`. Configure the SoundFont path in `engrave.toml`.
**Warning signs:** `FileNotFoundError` or `RuntimeError` from FluidSynth on first benchmark run.

### Pitfall 5: yt-dlp Output Path Unpredictability
**What goes wrong:** yt-dlp downloads to an unexpected location or with an unexpected filename.
**Why it happens:** The default output template includes video title (which can contain special characters, unicode, etc.).
**How to avoid:** Always specify `outtmpl` in options: `'outtmpl': str(output_dir / '%(id)s.%(ext)s')`. Use the video ID (deterministic, ASCII) not the title.
**Warning signs:** FileNotFoundError when trying to read the downloaded audio, or files with unicode/special chars in names breaking downstream processing.

### Pitfall 6: Benchmark Ground Truth MIDI vs Rendered-then-Transcribed MIDI Format Mismatch
**What goes wrong:** mir_eval comparison produces 0% accuracy because reference and estimated MIDI use different pitch representations or timing bases.
**Why it happens:** MIDI files from the corpus use ticks, mir_eval needs seconds + Hz. pretty_midi converts between these but you must use the same conversion for both reference and estimated.
**How to avoid:** Convert both reference and estimated MIDI through `pretty_midi.PrettyMIDI` to extract `(interval, pitch_hz)` arrays. Use `pretty_midi.note_number_to_hz()` for consistent pitch representation.
**Warning signs:** F1 scores near 0.0 even on trivially simple test cases (single note, known pitch).

## Code Examples

Verified patterns from official sources:

### Audio Normalization
```python
# Source: pydub documentation
from pydub import AudioSegment
from pathlib import Path

def normalize_audio(input_path: Path, output_path: Path,
                    target_sr: int = 44100, channels: int = 1) -> Path:
    """Normalize any audio format to WAV mono at target sample rate."""
    audio = AudioSegment.from_file(str(input_path))
    audio = audio.set_frame_rate(target_sr).set_channels(channels)
    audio.export(str(output_path), format="wav")
    return output_path
```

### YouTube Audio Extraction
```python
# Source: yt-dlp Python API documentation
import yt_dlp
from pathlib import Path

def extract_youtube_audio(url: str, output_dir: Path) -> Path:
    """Download and extract audio from YouTube URL."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '0',  # best quality
        }],
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info['id']
    return output_dir / f"{video_id}.wav"
```

### Source Separation (Single Model)
```python
# Source: audio-separator README
from audio_separator.separator import Separator
from pathlib import Path

def separate_stems(audio_path: Path, model_name: str,
                   output_dir: Path) -> list[Path]:
    """Separate audio into stems using specified model."""
    separator = Separator(
        output_dir=str(output_dir),
        output_format="WAV",
        sample_rate=44100,
    )
    separator.load_model(model_filename=model_name)
    output_files = separator.separate(str(audio_path))
    return [Path(f) for f in output_files]
```

### basic-pitch Transcription (In-Process)
```python
# Source: basic-pitch README + inference.py
from basic_pitch.inference import predict, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
from pathlib import Path

def transcribe_stem(wav_path: Path, output_dir: Path) -> Path:
    """Transcribe a single-instrument WAV to MIDI."""
    model = Model(ICASSP_2022_MODEL_PATH)
    model_output, midi_data, note_events = predict(
        audio_path=str(wav_path),
        model_or_model_path=model,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=58,  # ms
    )
    midi_path = output_dir / f"{wav_path.stem}.mid"
    midi_data.write(str(midi_path))
    return midi_path
```

### MIDI-to-Audio Rendering (Benchmark)
```python
# Source: midi2audio README
from midi2audio import FluidSynth
from pathlib import Path

def render_midi_to_audio(midi_path: Path, wav_path: Path,
                         soundfont: str | None = None) -> Path:
    """Render MIDI to WAV via FluidSynth for benchmark ground truth."""
    fs = FluidSynth(soundfont) if soundfont else FluidSynth()
    fs.midi_to_audio(str(midi_path), str(wav_path))
    return wav_path
```

### MIDI Diff with mir_eval
```python
# Source: mir_eval documentation
import mir_eval
import pretty_midi
import numpy as np
from pathlib import Path
from dataclasses import dataclass

@dataclass
class MidiDiffResult:
    """Result of comparing two MIDI files."""
    precision: float
    recall: float
    f1: float
    avg_overlap: float

def diff_midi(reference_path: Path, estimated_path: Path,
              onset_tolerance: float = 0.05) -> MidiDiffResult:
    """Compare two MIDI files using mir_eval transcription metrics."""
    ref_midi = pretty_midi.PrettyMIDI(str(reference_path))
    est_midi = pretty_midi.PrettyMIDI(str(estimated_path))

    # Extract intervals and pitches from all instruments
    def _extract(pm: pretty_midi.PrettyMIDI):
        intervals, pitches = [], []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                intervals.append([note.start, note.end])
                pitches.append(pretty_midi.note_number_to_hz(note.pitch))
        return np.array(intervals), np.array(pitches)

    ref_intervals, ref_pitches = _extract(ref_midi)
    est_intervals, est_pitches = _extract(est_midi)

    if len(ref_intervals) == 0 or len(est_intervals) == 0:
        return MidiDiffResult(0.0, 0.0, 0.0, 0.0)

    precision, recall, f1, avg_overlap = (
        mir_eval.transcription.precision_recall_f1_overlap(
            ref_intervals, ref_pitches,
            est_intervals, est_pitches,
            onset_tolerance=onset_tolerance,
        )
    )
    return MidiDiffResult(precision, recall, f1, avg_overlap)
```

### Quality Metadata Annotations
```python
# Pattern for post-transcription quality checks
import pretty_midi
import numpy as np
from dataclasses import dataclass
from pathlib import Path

@dataclass
class StemQuality:
    """Quality metrics for a single transcribed stem."""
    stem_name: str
    note_count: int
    note_density_per_bar: float     # Notes per bar (too high = garbage)
    pitch_range_violations: int     # Notes outside instrument's physical range
    onset_cluster_score: float      # 0-1, high = suspicious simultaneous onsets
    velocity_variance: float        # Low variance = suspicious flat dynamics
    duration_cv: float              # Coefficient of variation of durations (low = grid)

def annotate_quality(midi_path: Path, stem_name: str,
                     tempo_bpm: float = 120.0,
                     expected_range: tuple[int, int] = (0, 127)) -> StemQuality:
    """Compute quality heuristics on transcribed MIDI."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    all_notes = [n for inst in pm.instruments for n in inst.notes if not inst.is_drum]

    if not all_notes:
        return StemQuality(stem_name, 0, 0.0, 0, 0.0, 0.0, 0.0)

    # Note density
    duration_sec = pm.get_end_time()
    bars = (duration_sec / 60.0) * tempo_bpm / 4.0  # Approximate
    density = len(all_notes) / max(bars, 1.0)

    # Pitch range violations
    violations = sum(1 for n in all_notes
                     if n.pitch < expected_range[0] or n.pitch > expected_range[1])

    # Onset clustering (fraction of notes within 10ms of another)
    onsets = sorted(n.start for n in all_notes)
    clustered = sum(1 for i in range(1, len(onsets))
                    if onsets[i] - onsets[i-1] < 0.01)
    cluster_score = clustered / max(len(onsets) - 1, 1)

    # Velocity variance
    velocities = [n.velocity for n in all_notes]
    vel_var = float(np.std(velocities))

    # Duration coefficient of variation
    durations = [n.end - n.start for n in all_notes]
    dur_mean = np.mean(durations)
    dur_cv = float(np.std(durations) / dur_mean) if dur_mean > 0 else 0.0

    return StemQuality(
        stem_name=stem_name,
        note_count=len(all_notes),
        note_density_per_bar=density,
        pitch_range_violations=violations,
        onset_cluster_score=cluster_score,
        velocity_variance=vel_var,
        duration_cv=dur_cv,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| demucs (original package) | audio-separator (wraps BS-RoFormer, Mel-Band RoFormer, etc.) | 2024 | BS-RoFormer ~12.9 dB SDR vocals vs HTDemucs ~9.0 dB. But SDR is wrong metric for Engrave -- downstream MIDI accuracy is what matters. |
| basic-pitch TF backend | basic-pitch ONNX backend | 2024 (0.4.0) | ONNX via onnxruntime runs on Python 3.12+. Eliminates TF dependency if it works on macOS Apple Silicon. |
| Standalone benchmark scripts | Pipeline-integrated harness | Phase 5 design | Captures metrics at each stage boundary, enables systematic model comparison. |
| SDR as separation quality metric | Downstream MIDI accuracy | User decision | False positives (duplicated energy) preferred over false negatives (lost notes) for transcription. |

**Deprecated/outdated:**
- demucs (original PyPI): Abandoned Sept 2023. Do not use.
- htdemucs_6s: Known poor piano quality. Use hierarchical cascade with dedicated models instead.
- basic-pitch TensorFlow backend on Python 3.12+: Does not work. Use ONNX or isolated venv.

## Open Questions

1. **ONNX Spike: Does basic-pitch work in-process on Python 3.12 with onnxruntime?**
   - What we know: onnxruntime 1.24.x supports Python 3.12. basic-pitch 0.4.0 ships ONNX model files. The `Model` class tries TF -> CoreML -> TFLite -> ONNX sequentially.
   - What's unclear: Whether forcing ONNX-only loading works on macOS Apple Silicon Python 3.12 without TF/CoreML installed. The Model class has no explicit "force ONNX" flag -- it tries backends in sequence and uses the first that succeeds.
   - Recommendation: Run the spike early (Wave 0). If it works, in-process is simpler. If not, subprocess to Python 3.10 venv. Test with a known audio file and verify MIDI output matches expected notes.

2. **audio-separator output file naming convention**
   - What we know: `separator.separate()` returns a list of output file paths. Model-specific stem naming varies by architecture.
   - What's unclear: Exact filenames for different model architectures (BS-RoFormer outputs "Vocals"/"Instrumental"; HTDemucs outputs "drums"/"bass"/"vocals"/"other"). The hierarchical cascade needs to map output names to the next step's input.
   - Recommendation: Run each model once to capture its output naming convention. Build a stem-name mapping in config.

3. **SoundFont selection for benchmark determinism**
   - What we know: FluidSynth requires a SoundFont. Different SoundFonts produce different audio. Benchmark regression tests need deterministic audio.
   - What's unclear: Which free SoundFont produces the most "realistic" output for big band instruments. FluidR3_GM is standard but sounds synthetic.
   - Recommendation: Pick one SoundFont (FluidR3_GM.sf2 is widely available, ~141MB) and freeze it. The benchmark tests regression, not realism. Suno tracks test realism separately.

4. **File size limits for audio uploads**
   - What we know: Big band recordings can be 5-10 minutes. At 44.1kHz 16-bit stereo WAV, that's ~50-100MB. Source separation models process entire files in memory.
   - What's unclear: Whether audio-separator handles very long recordings efficiently or needs chunking.
   - Recommendation: Set a configurable limit (default: 15 minutes, ~150MB WAV). For the benchmark harness, corpus pieces are typically 1-4 minutes. Address long recordings if they become a real issue.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-bdd + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x --timeout=30` |
| Full suite command | `uv run pytest tests/ --timeout=120 --cov=engrave` |
| Estimated runtime | ~15-30 seconds (unit), ~60-90 seconds (integration with mocked audio) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FNDN-02 | Accept MP3/WAV/AIFF/FLAC, route through pipeline | integration | `pytest tests/integration/test_audio_pipeline.py -x` | No -- Wave 0 gap |
| FNDN-03 | Accept YouTube URL, extract audio, route through pipeline | integration | `pytest tests/integration/test_youtube_extract.py -x` | No -- Wave 0 gap |
| AUDP-01 | Source separation via audio-separator per-stem model routing | unit + integration | `pytest tests/unit/test_separator.py tests/integration/test_separation.py -x` | No -- Wave 0 gap |
| AUDP-02 | Transcribe stems to MIDI via basic-pitch | unit + integration | `pytest tests/unit/test_transcriber.py tests/integration/test_transcription.py -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `uv run pytest tests/ -x --timeout=30`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15-30 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_normalizer.py` -- covers audio format normalization (FNDN-02)
- [ ] `tests/unit/test_separator.py` -- covers SeparationConfig, hierarchical cascade logic (AUDP-01)
- [ ] `tests/unit/test_transcriber.py` -- covers Transcriber protocol, BasicPitchTranscriber (AUDP-02)
- [ ] `tests/unit/test_quality.py` -- covers quality annotation metrics
- [ ] `tests/unit/test_youtube.py` -- covers yt-dlp extraction (FNDN-03)
- [ ] `tests/unit/test_benchmark_evaluator.py` -- covers mir_eval MIDI diff
- [ ] `tests/unit/test_benchmark_renderer.py` -- covers FluidSynth MIDI-to-audio
- [ ] `tests/integration/test_audio_pipeline.py` -- covers end-to-end audio -> MIDI flow (FNDN-02, AUDP-01, AUDP-02)
- [ ] `tests/integration/test_youtube_extract.py` -- covers YouTube URL -> audio extraction (FNDN-03)
- [ ] `tests/fixtures/audio/` -- small test WAV files (sine wave, simple melody, ~1 second each)
- [ ] `tests/conftest.py` additions -- audio pipeline fixtures (mock separator, mock transcriber)

## Sources

### Primary (HIGH confidence)
- [audio-separator GitHub README](https://github.com/nomadkaraoke/python-audio-separator) - Python API, Separator class, model loading, output format
- [basic-pitch GitHub](https://github.com/spotify/basic-pitch) - predict() API, Model class, backend priority, CLI usage
- [basic-pitch inference.py](https://github.com/spotify/basic-pitch/blob/main/basic_pitch/inference.py) - predict() signature, Model backend loading sequence
- [mir_eval transcription docs](https://mir-eval.readthedocs.io/latest/api/transcription.html) - precision_recall_f1_overlap() signature, parameters
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp) - YoutubeDL Python API, postprocessor options
- [midi2audio GitHub](https://github.com/bzamecnik/midi2audio) - FluidSynth().midi_to_audio() API
- [pretty_midi docs](https://craffel.github.io/pretty-midi/) - PrettyMIDI class, note_number_to_hz()
- [onnxruntime PyPI](https://pypi.org/project/onnxruntime/) - Python 3.12+ support confirmed

### Secondary (MEDIUM confidence)
- [basic-pitch issue #188](https://github.com/spotify/basic-pitch/issues/188) - Python 3.12 compatibility status (open, unresolved)
- [basic-pitch-torch](https://github.com/gudgud96/basic-pitch-torch) - PyTorch port, minimal maintenance, no pitch bend support mentioned
- [pydub GitHub](https://github.com/jiaaro/pydub) - AudioSegment API for format conversion

### Tertiary (LOW confidence)
- ONNX spike outcome (untested -- basic-pitch ONNX on Python 3.12 macOS Apple Silicon needs empirical validation)
- audio-separator hierarchical cascade (verified API supports sequential model loading, but multi-step cascade pattern is our own design, not an audio-separator feature)

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - Libraries verified via PyPI/GitHub, APIs confirmed, but ONNX spike is untested
- Architecture: MEDIUM - Pipeline patterns are well-established, but hierarchical separation cascade is novel composition
- Pitfalls: HIGH - Python version constraints, memory management, sample rate mismatches are well-documented known issues

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (audio-separator and basic-pitch are relatively stable; yt-dlp changes weekly but API is stable)
