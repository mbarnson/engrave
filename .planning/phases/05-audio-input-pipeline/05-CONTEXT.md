# Phase 5: Audio Input Pipeline - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

User can upload audio files (MP3, WAV, AIFF, FLAC) or paste a YouTube URL and the system extracts MIDI data through source separation and transcription. This phase builds the forward path (audio in → MIDI out) plus the experimentation harness needed to empirically validate model choices. The resulting MIDI feeds into the existing MIDI-to-LilyPond pipeline from Phase 3.

Audio understanding (Stage 3: structured descriptions from audio LM) and natural language hints are Phase 6. Chord symbol generation on rhythm section parts is Phase 4/7.

</domain>

<decisions>
## Implementation Decisions

### Experimentation Harness
- **Primary comparison unit:** MIDI diff — note accuracy, onset timing, phantom notes, missed notes between output MIDI and reference MIDI
- **Closed-loop test design:** Corpus MIDI (from Phase 2 PDMX/Mutopia) → render to audio (FluidSynth/timidity) → run separation → run transcription → diff output MIDI against original source MIDI
- **Two test loops, different purposes:**
  - FluidSynth/timidity loop: deterministic regression detection with exact ground truth (soundfont audio = easy mode, but catches regressions precisely)
  - Suno-generated big band tracks: realistic quality assessment (closer to real recordings, fuzzier ground truth, spot-check rather than exact diff)
- **Pipeline-integrated:** Harness runs as a mode of the pipeline, not a standalone tool — captures metrics at each stage boundary
- **LLM judge:** At scale (200K+ corpus pieces), use an LLM judge to evaluate and rank results automatically — no manual listening
- **Results storage:** Structured JSON per run (model config, per-track metrics, aggregate scores) + CLI summary command (`engrave benchmark --compare`). Git-trackable, scriptable
- Include FluidSynth/timidity MIDI-to-audio rendering as a utility in Phase 5 — it's test infrastructure, costs almost nothing to build

### Separation Strategy
- **Per-stem model routing:** Fully configurable via engrave.toml — each stem target maps to a model name. Defaults to current best-known picks but any audio-separator model can be swapped in
- **Multi-model per stem:** Config accepts a list of models per stem (not just one). When multiple models are listed, run ALL and save ALL outputs as separate artifacts in the job directory (e.g., `vocals_bs_roformer.wav`, `vocals_demucs.wav`). No combination/merge logic in v1 — the harness compares them independently through transcription
- **Hierarchical separation plan:** Config defines an ordered list of (model, input_stem, output_stems) operations, not just "pick 4 or 6 stems." Example for big band:
  1. Run 4-stem model → drums, bass, vocals, other
  2. Run dedicated piano model on "other" → piano, residual
  3. Run dedicated guitar model on residual → guitar, horns-only
- **Rationale for hierarchical:** Big band's "other" bin contains 11+ melodic instruments with overlapping frequencies — worst case for AMT. Isolating piano/guitar (rhythm section instruments needed for chord symbols) from horns dramatically reduces polyphonic complexity in the horn stem
- **Optimization metric:** Downstream MIDI transcription accuracy, NOT SDR. False positives (duplicated energy across stems) preferred over false negatives (lost notes). SDR benchmarks optimize for remix fidelity which is the wrong objective for Engrave

### Transcription Approach
- **Pluggable `Transcriber` protocol:** WAV path in, MIDI path out. Designed so alternative backends are a config change, not a refactor
- **First backend:** Basic Pitch via subprocess to isolated Python 3.10 venv. Research spike first: test whether `basic-pitch --model-serialization onnx` (ONNX backend via onnxruntime) works in Python 3.12, bypassing the TF/Apple Silicon constraint
- **Quality metadata annotations:** Post-transcription heuristic checks produce numerical scores attached as metadata to each stem's MIDI — NOT binary pass/fail fallback triggers. Metrics include:
  - Note density per bar (too many = garbage, zero = separation ate the stem)
  - Pitch range violations (notes outside physical instrument range, using ensemble preset knowledge)
  - Onset clustering (simultaneous onset clusters on monophonic stem = artifacts)
  - Velocity variance (flat velocity = suspicious)
  - Duration distribution (uniform duration = model hallucinating a grid)
- **No automatic fallback in v1:** There's nothing to fall back TO (Basic Pitch is the only mature option). Quality metadata travels downstream — Stage 4's LLM prompt uses confidence signals to weight trust in each stem's transcription (e.g., "bass transcription high-confidence, horn stem low-confidence — lean on audio description for voicings")
- **The LLM IS the fallback:** Stage 4 interprets ambiguous/noisy MIDI through the lens of audio description, user hints, ensemble conventions, and RAG examples. A wrong note that's clearly a passing tone in context gets quietly fixed

### Claude's Discretion
- Audio format normalization details (sample rate, channel handling, bit depth)
- YouTube extraction implementation (yt-dlp API vs CLI)
- File size limits and handling of very long recordings
- FluidSynth vs timidity choice for MIDI-to-audio rendering
- Exact JSON schema for benchmark result files
- MIDI post-processing details (pitch bend handling, drum map normalization)

</decisions>

<specifics>
## Specific Ideas

- "The state of the art in audio-to-MIDI transcription is kinda bad. We want maximum configurability, experimentation, and ability to try out different models and approaches"
- Suno.com can generate unlimited royalty-free big band jazz tracks for testing — synthetically perfect audio with crisper spectral boundaries than real recordings, making it a controlled baseline
- The delta between Suno-source accuracy and real-recording accuracy measures exactly how much real-world audio messiness costs the pipeline
- The irony of using Suno (the tool that frustrated the user into building Engrave) as the test data generator is noted and appreciated
- PDMX and Mutopia corpus from Phase 2 doubles as ground truth for the deterministic test loop
- For big band, piano and guitar are rhythm section instruments that comp chords — functionally distinct from the horn section. Requirements ENSM-04 needs chord symbols on rhythm section parts, which requires clean piano/guitar separation
- `htdemucs_6s` (6-stem model) has known poor piano quality — dedicated single-instrument RoFormer models produce better results than the all-in-one 6-stem approach

</specifics>

<deferred>
## Deferred Ideas

- **Ensemble/merge combination logic for multi-model stems** — Phase 5.1 optimization once the harness has data on what "better" means. Current approach: run multiple models, save all, compare independently
- **Alternative transcription backends** (YourMT3+, future pip-installable AMT models) — the `Transcriber` protocol makes this a config change when viable alternatives appear
- **Post-Phase 5 spike: separator → AMT → MIDI vs ground truth benchmark** — already noted in project memory, validates the full chain empirically
- **Suno-sourced test corpus curation** — user generates tracks on Suno.com, not automated

</deferred>

---

*Phase: 05-audio-input-pipeline*
*Context gathered: 2026-02-24*
