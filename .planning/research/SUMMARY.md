# Project Research Summary

**Project:** Engrave - AI-powered audio-to-sheet-music engraving pipeline
**Domain:** Music engraving and transcription (audio/MIDI to publication-quality parts)
**Researched:** 2026-02-24
**Confidence:** MEDIUM-HIGH

## Executive Summary

Engrave is an AI-powered music engraving pipeline that transforms audio recordings or MIDI files into publication-quality, transposed sheet music parts. The system combines source separation (Demucs), MIDI transcription (Basic Pitch), audio understanding (Qwen3-Omni-Captioner), and RAG-augmented LLM code generation (Qwen3-Coder-Next/Claude) to produce LilyPond output. The primary use case is big band arrangements, where the key differentiator is "convergent sight-reading" -- generating section parts jointly so articulations, dynamics, and beam groupings co-vary, enabling musicians to sound like a unified section on first read.

The recommended approach is to build a stage-based pipeline (Ingest -> Separate -> Transcribe -> Describe -> Generate -> Render) with artifact passing through the filesystem. Start with MIDI input to validate the code generation pipeline before tackling the harder audio input path. Use LiteLLM for unified LLM provider routing, ChromaDB for RAG-based few-shot prompting, and section-by-section generation with coherence state passing to handle long scores. Store all music in concert pitch internally and apply transposition deterministically at render time.

The key risks are: (1) LilyPond compilation failures from LLM-generated code -- mitigate with compile-check-fix loops, (2) Demucs cannot separate individual brass/woodwind instruments -- design around 4-stem limitation from day one, (3) convergent sight-reading requires joint section generation -- independent part generation will fail, (4) context window overflow on full scores -- use chunked generation with coherence state. RAG quality depends entirely on corpus curation, and Audiveris OMR output quality is too low to use as ground truth without manual verification.

## Key Findings

### Recommended Stack

The stack is PyTorch-centric with Python 3.12 as the runtime. FastAPI handles the web UI, Demucs v4 (htdemucs) for source separation, Basic Pitch for MIDI transcription, Qwen3-Omni-30B-A3B-Captioner for local audio understanding (served via vllm-mlx on Apple Silicon), and Qwen3-Coder-Next (80B MoE, 3B active) for LilyPond code generation. LiteLLM provides unified LLM routing across Anthropic, OpenAI, and LMStudio local endpoints. LlamaIndex + ChromaDB handle RAG retrieval, and LilyPond 2.24.4 renders final PDFs. The M4 Max 128GB provides sufficient memory for concurrent model execution, though sequential execution is recommended for thermal management.

**Core technologies:**
- **Python 3.12 + PyTorch 2.10.0**: FastAPI, Pydantic v2, MPS acceleration for Apple Silicon
- **demucs-infer 4.1.2**: Source separation into drums/bass/vocals/other stems (htdemucs_ft model)
- **basic-pitch 0.4.0**: Lightweight CNN-based MIDI transcription (post-separation, per-stem)
- **Qwen3-Omni-30B-A3B-Captioner**: Local audio LM for structured musical descriptions (key, tempo, style, articulation intent) — served via vllm-mlx on Apple Silicon
- **Qwen3-Coder-Next 80B**: Primary local code generation LLM (3B active, 256K context, runs at 100+ tok/s)
- **LiteLLM**: Unified interface for Anthropic/OpenAI/LMStudio with OpenAI-compatible API
- **LlamaIndex + ChromaDB**: RAG retrieval of curated LilyPond examples for few-shot prompting
- **LilyPond 2.24.4**: Text-based music engraving with publication-quality PDF output
- **uv + ruff**: Modern Python tooling (package management, linting, formatting)

**Critical version notes:**
- Avoid `demucs` (original PyPI package, abandoned Sept 2023) -- use `demucs-infer` instead
- basic-pitch requires Python 3.10 isolated venv on Apple Silicon (hard constraint, not a workaround)
- Abjad requires LilyPond 2.25.26+ (dev branch); install alongside stable 2.24.4 for rendering

### Expected Features

**Must have (table stakes):**
- PDF output of individual transposed parts (one per instrument)
- Full conductor score PDF (landscape A3/Tabloid for big band)
- Correct transpositions for all instruments (Bb trumpet, Eb alto sax, etc.)
- Proper clef assignment, key signatures per transposed part
- Rehearsal marks, measure numbers, multi-bar rests
- Multi-format input (MP3, WAV, MIDI, YouTube URL)
- Correct rhythmic notation and beaming per style conventions
- Dynamic markings (with restatement after multi-bar rests)
- Tempo and style markings (swing, bossa nova, ballad)
- Repeat signs and endings (D.S. al Coda, first/second endings)
- Chord symbols for rhythm section parts
- Cues during long rests (8+ bars)

**Should have (competitive differentiators):**
- **Convergent sight-reading (section-joint generation)**: The key differentiator -- generate section parts together so articulations, dynamics, and beam groupings co-vary
- **Natural language intent layer**: User types "Soli at bar 17, brass shout chorus bar 33" and the system encodes this as structural metadata
- **Audio LM understanding**: Beyond pitch/rhythm -- understand musical character, articulation intent, section roles
- **Ensemble presets with deep knowledge**: Big band score order, transpositions, voicing conventions, part layout norms (Tim Davies, Evan Rogers, Gould)
- **Automated evaluation pipeline**: MusicXML structural diff, audio envelope comparison, visual PDF comparison
- **RAG-augmented code generation**: Few-shot examples from curated corpus dramatically improve LLM output quality
- **Source separation pipeline**: Demucs separates mixed recordings into stems before transcription
- **LilyPond source output**: Editable text-based format, version-controllable
- **MusicXML export**: Escape hatch for editing in Dorico/Sibelius/MuseScore

**Defer (v2+):**
- Interactive notation editor (use MuseScore/Dorico/Frescobaldi for editing)
- Real-time playback with audio engine (export MIDI, play in DAW)
- Arrangement completion / AI composition (v1 takes arrangement as given)
- Fine-tuning custom models (RAG-first is sufficient for v1)
- Mobile app (inherently desktop workflow)
- Real-time collaboration (single-user for v1)
- Support for every ensemble type at launch (start with big band, piano solo, small combo)

### Architecture Approach

The architecture is a stage-based pipeline with artifact passing through the filesystem. Each stage is a pure function: `(job_context, stage_input_dir) -> stage_output_dir`. The orchestrator manages job directories and routes between stages. Stages: (0) Ingest (file/URL intake, normalization), (1) Source Separation (Demucs 4-stem), (2) MIDI Transcription (Basic Pitch per stem), (3) Audio Understanding (Qwen3-Omni-Captioner structured description), (4) LilyPond Generation (RAG-augmented LLM with section-by-section coherence state passing), (5) Rendering (LilyPond CLI to PDF + ZIP packaging).

**Major components:**
1. **Pipeline Orchestrator** -- Routes jobs through stages, manages state machine, handles MIDI-skip path, retries failures. In-process async pipeline with stage functions.
2. **Inference Router (LiteLLM)** -- Unified LLM interface for Anthropic/OpenAI/LMStudio. Maps model preferences (code, audio, local) to configured providers.
3. **RAG System (ChromaDB + LlamaIndex)** -- Stores (LilyPond source, MIDI tokens, text description) triples from curated corpus. Retrieves similar examples for few-shot prompting at Stage 4.
4. **Stage 4: LilyPond Generation** -- Generates code section-by-section with coherence state passing. Joint section-part generation for convergent sight-reading (all 4 trumpets in one LLM call, not independently).
5. **Rendering Engine** -- LilyPond CLI subprocess execution, part extraction with deterministic transposition, ZIP packaging of outputs (PDFs, .ly source, MusicXML).
6. **Corpus Manager** -- Ingests scores via OMR (Audiveris), indexes training triples, versions data. Handles Mutopia, PDMX, Sam's 350 charts.

**Key patterns:**
- Section-by-section generation with coherence state (prevents context overflow, maintains consistency)
- Joint section-part generation (all trumpets together, not independently -- enables convergent sight-reading)
- Multi-provider inference via LiteLLM (seamless swapping between local and cloud models)
- RAG with structured metadata filtering (embed text descriptions, not raw LilyPond)
- Monolith with clean module boundaries (not microservices -- single-user prototype)

### Critical Pitfalls

1. **LilyPond compilation failures from LLM-generated code** -- LLMs generate uncompilable syntax (unmatched braces, incorrect durations, misused `\relative`). Mitigation: compile-check-fix loop with 3-5 retries, use structural templates (provide boilerplate, LLM fills music only), include 3-5 compilable examples in RAG context, validate brace matching before invoking LilyPond.

2. **Demucs cannot separate brass, woodwinds, or individual instruments** -- Demucs v4 separates into only 4 stems (drums, bass, vocals, other). Entire horn section comes out as one "other" stem. Mitigation: accept Demucs as preprocessing helper, rely on MIDI transcription + audio LM for instrument assignment, design pipeline around "mixed horn section audio" from day one, prefer MIDI input path when available.

3. **MT3 instrument leakage fragments transcriptions across wrong instruments** -- MT3 splits audio into segments and transcribes independently, causing melody notes to be labeled as different instruments across segments. Mitigation: use MT3/Basic Pitch for pitch/rhythm only (ignore instrument labels), use audio LM for instrument identification, separate "note transcription" from "instrument assignment" stages.

4. **Convergent sight-reading treated as independent part generation** -- Generating each part separately causes articulations, dynamics, and beam groupings to diverge. Mitigation: generate section parts jointly (all 4 trumpets in one LLM call), explicit articulation/dynamics constraints in prompt, post-process section coherence validation, curate RAG examples showing section writing.

5. **Transposition errors in instrument parts** -- Wrong key signatures, wrong intervals, double-transposition from storing transposed pitch + applying `\transpose`. Mitigation: store ALL music in concert pitch, build verified transposition table as config artifact, never let LLM decide transposition, validate with C major scale test per instrument.

6. **Context window overflow on full big band scores** -- 17 instruments x 120 bars = 3,000-5,000 lines of LilyPond exceeds context limits. Mitigation: generate in phrase-sized chunks (4-8 bars) with coherence state passing, use LilyPond variable/include system, curate compact RAG examples (single phrase, not full scores), benchmark token counts early.

7. **RAG retrieval returns irrelevant or misleading LilyPond examples** -- Sparse corpus (350 examples) causes poor matches. General-purpose embeddings don't understand music domain semantics. Mitigation: use structured metadata for retrieval (instrument family, ensemble type, style), supplement with Mutopia/PDMX open-source material, chunk examples at phrase level (5K-10K chunks from 350 scores), test retrieval quality independently.

8. **Audiveris OMR quality too low for automated corpus building** -- OMR output has wrong durations, misread accidentals, missing ties/slurs, confused beams. Mitigation: do NOT use OMR as ground truth without human verification, prioritize MIDI/audio input paths, use OMR only for structural scaffolding (pitches/rhythms), manually annotate articulations/dynamics.

9. **Audio LM clip limitations miss song-level structure** -- Local audio LMs may degrade on long audio, losing song-level structure (key changes, section relationships). Qwen3-Omni-Captioner may handle longer clips than its predecessor but needs validation. Mitigation: segment audio into structural sections first, process each section with context about its role, treat user hints as authoritative for structure, use Gemini 3 Flash for long-form analysis.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation & MIDI-to-LilyPond
**Rationale:** MIDI input is the cleanest path (skips audio separation and transcription). Proves the code generation pipeline works before tackling harder audio input. Establishes core infrastructure (inference router, RAG system, compile-check-fix loop, rendering engine) that everything else depends on.

**Delivers:** Working MIDI-to-parts pipeline for big band ensemble preset. User uploads MIDI, gets transposed PDF parts + LilyPond source.

**Addresses features:**
- Individual transposed part PDFs (table stakes)
- Full conductor score PDF (table stakes)
- Big band ensemble preset with correct transpositions/clefs (table stakes)
- Basic articulation conventions (table stakes)
- Chord symbols on rhythm section parts (table stakes)
- Multi-bar rests (table stakes)
- LilyPond source output (differentiator)

**Avoids pitfalls:**
- LilyPond compilation failures (compile-check-fix loop in place from day one)
- Transposition errors (verified transposition table, concert-pitch internal storage)
- Context window overflow (chunked generation architecture established)
- RAG retrieval quality (corpus curated and tested before audio pipeline adds complexity)

**Key components:** Pipeline orchestrator (basic), Inference Router, RAG System, Stage 4 (LilyPond Generation), Rendering Engine

**Research flag:** Standard patterns for RAG and LLM code generation. May need deeper research into LilyPond conventions and big band engraving standards.

---

### Phase 2: Audio Input Pipeline
**Rationale:** After MIDI-to-parts works, add audio input (Stage 0: Ingest, Stage 1: Source Separation, Stage 2: MIDI Transcription). Audio introduces transcription error that compounds with engraving error, so tackle it only after code generation is stable.

**Delivers:** Full audio-to-parts pipeline. User uploads MP3/WAV/YouTube URL, gets transposed parts.

**Uses stack elements:**
- yt-dlp (YouTube audio extraction)
- ffmpeg (audio format conversion)
- demucs-infer 4.1.2 (source separation)
- basic-pitch 0.4.0 (MIDI transcription per stem)

**Implements architecture components:**
- Stage 0: Ingest (file handling, yt-dlp, ffmpeg normalization)
- Stage 1: Source Separation (Demucs integration)
- Stage 2: MIDI Transcription (Basic Pitch integration)
- Parallel execution: Stage 2 and Stage 3 run concurrently after Stage 1

**Addresses features:**
- Audio input (MP3, WAV, FLAC)
- YouTube URL input
- Source separation pipeline (differentiator)

**Avoids pitfalls:**
- Demucs stem limitation (pipeline designed around 4-stem output, not per-instrument)
- MT3 instrument leakage (use Basic Pitch for pitch/rhythm only, separate instrument assignment)
- basic-pitch requires Python 3.10 isolated venv on Apple Silicon (hard constraint — plan from day one)

**Research flag:** May need deeper research into Demucs parameters, Basic Pitch tuning, audio preprocessing, and stem-to-instrument mapping strategies.

---

### Phase 3: Audio Understanding & Natural Language Hints
**Rationale:** Audio LM (Stage 3) provides semantic layer beyond pitch/rhythm -- musical character, articulation intent, section roles. Natural language hints let users guide structure/style. Both inform better LilyPond generation.

**Delivers:** Enhanced generation with audio understanding and user-provided structural hints. Better articulation choices, dynamics, style markings.

**Uses stack elements:**
- Qwen3-Omni-30B-A3B-Captioner (local audio LM for structured descriptions, via vllm-mlx)
- Gemini 3 Flash (cloud API for long-form audio, optional)
- LFM2.5-Audio-1.5B (lightweight local model for fast tasks, optional)

**Implements architecture component:**
- Stage 3: Audio Understanding (Qwen3-Omni-Captioner structured description)
- Natural language hint processing and encoding into Stage 4 prompts

**Addresses features:**
- Audio LM understanding (differentiator)
- Natural language intent layer (differentiator)
- Tempo and style markings (table stakes)

**Avoids pitfalls:**
- Audio LM 30-second clip limitation (segment audio into structural sections first, process with context)
- Song-level structure loss (supplement with user hints, use Gemini for long-form)

**Research flag:** Needs deeper research into Qwen3-Omni-Captioner output format and audio segmentation approaches. Also research into NL-to-structural-metadata mapping. Validate MoE inference speed on M4 Max via vllm-mlx.

---

### Phase 4: Convergent Sight-Reading (Section-Joint Generation)
**Rationale:** This is THE differentiator. Section parts must be generated jointly (all 4 trumpets in one LLM call) so articulations, dynamics, and beam groupings co-vary. Independent generation guarantees divergence. This is the hard problem and requires dedicated phase for experimentation.

**Delivers:** Section-aware generation where parts within a section have consistent articulations, dynamics, and beam groupings. Musicians sound like a unified section on first read.

**Implements architecture pattern:**
- Joint section-part generation (all trumpets together, not independently)
- Section-level coherence validation (post-generation diff check)
- Tim Davies articulation defaults (jazz-specific conventions)

**Addresses features:**
- Convergent sight-reading (THE differentiator)
- Ensemble presets with deep knowledge (section groupings, voicing conventions)

**Avoids pitfall:**
- Convergent sight-reading failure (architectural change to joint generation required, cannot be patched onto per-instrument pipeline)

**Research flag:** Needs significant research into prompt engineering for joint part generation, section coherence validation strategies, and big band articulation conventions (Tim Davies, Evan Rogers, Gould).

---

### Phase 5: Refinement & Polish
**Rationale:** Add features that improve usability and quality: cues during long rests, repeat signs/D.S. al Coda, MusicXML export, evaluation pipeline, output packaging improvements.

**Delivers:** Production-ready features for actual rehearsal use.

**Addresses features:**
- Cues during long rests (table stakes)
- Repeat signs and endings (table stakes)
- MusicXML export (differentiator, escape hatch)
- Automated evaluation pipeline (differentiator, internal quality)

**Implements architecture components:**
- Evaluation Pipeline (MusicXML structural diff, audio envelope comparison, visual PDF comparison)
- Cue note generation (cross-part referencing)
- Repeat/coda navigation logic

**Research flag:** May need research into MusicXML generation strategies (not conversion from LilyPond), evaluation metrics for music notation quality, and LilyPond repeat syntax.

---

### Phase 6: Corpus Building & OMR
**Rationale:** Ingest Sam's 350 PDF scores and recordings to expand RAG corpus. This is deferred because OMR is time-consuming and corpus quality is a multiplier, not a blocker -- start with curated Mutopia/PDMX examples.

**Delivers:** Expanded RAG corpus with big band-specific examples (Sam's 350 charts).

**Uses stack elements:**
- Audiveris (OMR: PDF to MusicXML)
- music21 (MusicXML analysis)

**Implements architecture component:**
- Corpus Manager (ingest, OMR, triple assembly, indexing)

**Avoids pitfall:**
- Audiveris OMR quality (manual verification, spot-check 10% of output, use only for structural data)

**Research flag:** Needs research into Audiveris CLI automation, MusicXML-to-LilyPond conversion quality, and manual correction workflows.

---

### Phase Ordering Rationale

- **MIDI-first approach:** Validates code generation without audio complexity. Audio adds transcription error that compounds with engraving error -- tackle sequentially, not simultaneously.
- **Audio pipeline after MIDI:** Source separation and transcription are well-understood (Demucs, Basic Pitch) but audio quality issues are unpredictable. Prove end-to-end value with MIDI before investing in audio debugging.
- **Audio understanding after transcription:** Qwen3-Omni-Captioner provides semantic layer but is not critical for basic MIDI-to-parts. Add once transcription works.
- **Convergent sight-reading last:** This is the novel, hard problem. Requires stable foundation (Phases 1-3) before experimentation. Dedicated phase with specific evaluation criteria.
- **Corpus building deferred:** OMR is time-consuming and quality is poor without manual correction. Start with curated open-source corpus (Mutopia, PDMX), add Sam's charts later.

**Dependency chain:**
```
Foundation (Phase 1) -> Audio Pipeline (Phase 2) --+
                                                    v
                        Audio Understanding (Phase 3) -> Convergent Sight-Reading (Phase 4)
                                                    v
                                            Refinement (Phase 5)
                                                    v
                                            Corpus Building (Phase 6)
```

**Parallel opportunities:**
- Phase 2 (Audio Pipeline) and Phase 3 (Audio Understanding) can be developed in parallel after Phase 1
- Phase 5 (Refinement) and Phase 6 (Corpus Building) can be developed in parallel after Phase 4

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 (Foundation):** LilyPond engraving conventions (Tim Davies jazz defaults, big band score layout), RAG prompt engineering for code generation, compile-check-fix loop strategies
- **Phase 3 (Audio Understanding):** Qwen3-Omni-Captioner output structuring, vllm-mlx inference validation on M4 Max, audio segmentation approaches, NL-to-structural-metadata mapping
- **Phase 4 (Convergent Sight-Reading):** Joint section-part generation prompting, section coherence validation, big band articulation conventions (Tim Davies, Evan Rogers, Gould)
- **Phase 6 (Corpus Building):** Audiveris CLI automation, OMR quality assessment, MusicXML-to-LilyPond conversion

Phases with standard patterns (skip deep research):

- **Phase 2 (Audio Pipeline):** Demucs and Basic Pitch are well-documented with clear APIs. Standard audio processing patterns.
- **Phase 5 (Refinement):** MusicXML generation and evaluation are established domains with existing tools/libraries.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core technologies (FastAPI, PyTorch, Demucs, Basic Pitch, LilyPond) are mature and well-documented. LLM landscape is fast-moving but LiteLLM provides abstraction. Qwen models are recent (2025-2026) but Hugging Face releases are stable. |
| Features | MEDIUM-HIGH | Table stakes features are well-understood from established domain (music engraving conventions). Convergent sight-reading is novel -- no existing tool does this. RAG-augmented LilyPond generation is uncharted (combining existing techniques in new way). |
| Architecture | MEDIUM | Stage-based pipeline pattern is standard. Section-by-section generation with coherence state is adapted from long-form LLM generation research (Hierarchical Expansion) but not proven for music notation. Joint section-part generation is novel hypothesis -- requires validation. |
| Pitfalls | MEDIUM-HIGH | LilyPond compilation issues, Demucs limitations, MT3 instrument leakage, transposition errors are verified from multiple sources and practitioner reports. Convergent sight-reading failure mode is logical inference (not empirically tested in this domain). Audio LM limitations need revalidation with Qwen3-Omni-Captioner (successor to Qwen2-Audio). |

**Overall confidence:** MEDIUM-HIGH

The core pipeline (audio -> MIDI -> LilyPond -> PDF) is well-understood with established tools. The risk is in the novel combination: RAG-augmented LilyPond generation and convergent sight-reading (joint section-part generation) are hypotheses that need validation. The architecture is designed for rapid experimentation to validate these hypotheses.

### Gaps to Address

- **basic-pitch Python 3.10 venv (hard constraint):** basic-pitch 0.4.0 requires Python 3.10 on Apple Silicon. Package is frozen (last release Aug 2024, Snyk: "Inactive"). Plan a Python 3.10 isolated venv for basic-pitch from day one, called as subprocess from the main Python 3.12 environment.

- **Convergent sight-reading validation:** No existing tool or research demonstrates section-joint part generation for music notation. This is a novel hypothesis. Phase 4 must include specific evaluation: compare section coherence (articulation diff, dynamics alignment, beam grouping consistency) between joint generation and independent generation.

- **RAG corpus quality:** Mutopia corpus (2,124 LilyPond scores) is publication-quality but mostly classical. Big band jazz corpus is sparse. Sam's 350 charts require OMR processing. Initial corpus may not cover big band patterns well -- Phase 6 (Corpus Building) is critical for production quality, not just nice-to-have.

- **LilyPond LLM generation quality ceiling:** Unknown whether Qwen3-Coder-Next, Claude, or GPT-4 can reliably generate correct LilyPond for complex multi-instrument scores with 95%+ compilation success rate. Compile-check-fix loop is mandatory mitigation, but if base quality is <70%, the system becomes unusable. Must benchmark models early in Phase 1.

- **Demucs "other" stem quality for horn sections:** Demucs groups all brass/woodwinds/keys into "other" stem. Transcription quality from mixed horn section audio is unknown. Basic Pitch was designed for single-instrument audio -- performance on dense harmonic content is untested. May need MT3 fallback or manual MIDI input for complex horn voicings.

- **Audio LM structured output reliability:** Qwen3-Omni-Captioner produces fine-grained audio captions with low hallucination, but structured JSON output (key, tempo, form, articulation notes) may require post-processing. The Captioner variant auto-parses without prompting — validate whether its output format is directly usable or needs reformatting. Gemini 3 Flash has better structured output but is cloud-only. Local model may need format validation and correction loop similar to LilyPond compile-check-fix. On Apple Silicon, mlx_lm loads HuggingFace MoE models natively via MLX — no conversion needed.

## Sources

### Primary (HIGH confidence)
- LilyPond Official Documentation (v2.24, v2.25) -- notation reference, common errors, transpositions, beams, parts
- Demucs GitHub (facebookresearch/demucs, adefossez/demucs) -- v4 Hybrid Transformer, demucs-infer PyPI
- Basic Pitch GitHub (Spotify) -- PyPI 0.4.0, official repository, engineering blog post
- FastAPI PyPI (0.132.0), PyTorch PyPI (2.10.0), LiteLLM Docs -- official documentation
- Qwen3-Omni-30B-A3B-Captioner HuggingFace (Qwen/Qwen3-Omni-30B-A3B-Captioner), Sep 2025
- vllm-mlx GitHub (waybarrios/vllm-mlx) -- vLLM-like inference for Apple Silicon
- Qwen3-Coder-Next HuggingFace, LMStudio model page -- 80B MoE, 46GB 4-bit GGUF
- LlamaIndex PyPI (0.14.15), ChromaDB PyPI (1.5.1) -- official documentation
- OpenAI SDK PyPI (2.23.0), Anthropic SDK PyPI (0.83.0)
- Tim Davies - Jazz Notation: The Default (timusic.net) -- authoritative practitioner source, Grammy-nominated arranger
- Evan Rogers - Big Band Score Layout (evanrogersmusic.com) -- professional arranger
- Elaine Gould - Behind Bars (behindbarsnotation.co.uk) -- industry-standard reference

### Secondary (MEDIUM confidence)
- MT3 Paper (arxiv:2111.03017), MR-MT3 Paper (arxiv:2403.10024) -- peer-reviewed research
- MAESTRO Dataset (Google Magenta), ASAP Dataset (GitHub), MusicNet (Zenodo), Slakh2100 (Zenodo) -- peer-reviewed datasets
- Mutopia Project, PDMX Dataset (Zenodo 2025), OpenScore, KernScores, GigaMIDI (HuggingFace) -- established corpus sources
- Audiveris GitHub -- OMR tool, community discussions
- Hierarchical Expansion for Long-Form Generation (OpenCredo) -- pattern description
- Audio-to-Sheet-Music Pipeline (Music Demixer blog) -- Demucs + Basic Pitch workflow demonstration
- LilyPond-MusicXML Conversion Study (Franco Pasut blog) -- single author but verified against LilyPond docs
- Seven Failure Points When Engineering a RAG System (arxiv:2401.05856) -- RAG best practices
- Retrieval Augmented Generation of Symbolic Music with LLMs (arxiv:2311.10384v2) -- research prototype
- NotaGen: Symbolic Music Generation with LLM Training (arxiv:2502.18008v5) -- recent research
- LM Studio OpenAI Compatibility, Server Docs -- official documentation
- Gemini API Pricing, Audio Docs (ai.google.dev) -- official Google documentation
- gpt-oss-120b HuggingFace, Model Card (openai.com) -- official release Aug 2025

### Tertiary (LOW confidence)
- Comparison of Notation Software (Cotocus blog, Slant community opinions, Berklee Online) -- community perspectives, not authoritative
- AnthemScore, ScoreCloud, Klangio official sites -- vendor descriptions
- Arranger For Hire - Audio to MIDI in 2025 blog post -- practitioner review
- MusicXML Diff Procedure (ACM) -- academic paper on score comparison
- yt-dlp GitHub -- well-established tool
- Abjad GitHub (v3.31), python-ly Docs (0.9.5) -- official repositories

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
