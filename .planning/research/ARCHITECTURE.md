# Architecture Research

**Domain:** AI-powered music engraving pipeline (audio/MIDI to publication-quality sheet music)
**Researched:** 2026-02-24
**Confidence:** MEDIUM (novel domain combination; individual components well-documented, but their integration is uncharted)

## System Overview

```
                           USER INPUT
                    (audio / YouTube URL / MIDI)
                              |
                              v
 ┌─────────────────────────────────────────────────────────────────────┐
 │                         WEB UI LAYER                                │
 │  FastAPI + HTML/JS: upload, hints, ensemble config, job status      │
 └──────────────────────────────┬──────────────────────────────────────┘
                                |
                                v
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     PIPELINE ORCHESTRATOR                           │
 │  Job queue, stage routing, progress tracking, error recovery        │
 │  Decides: skip Stage 1-2 for MIDI input, retry on failure           │
 └───────┬──────────┬──────────┬──────────┬──────────┬────────────────┘
         |          |          |          |          |
         v          v          v          v          v
 ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
 │ STAGE 0  │ │ STAGE 1  │ │ STAGE 2  │ │ STAGE 3  │ │   STAGE 4    │
 │ Ingest   │ │ Separate │ │Transcribe│ │ Describe │ │  Generate    │
 │          │ │          │ │          │ │          │ │  LilyPond    │
 │ yt-dlp   │ │audio-sep │ │Basic     │ │Qwen3-   │ │  via LLM +   │
 │ ffmpeg   │ │RoFormer+ │ │Pitch    │ │Omni /   │ │  RAG         │
 │ file I/O │ │          │ │         │ │Gemini    │ │              │
 └─────┬────┘ └─────┬────┘ └────┬────┘ └─────┬────┘ └──────┬───────┘
       |            |           |             |             |
       v            v           v             v             v
   raw audio    4 stems     MIDI per      structured     .ly source
   (WAV)        (WAV)       stem          text desc.     per section
                                                              |
                                                              v
 ┌─────────────────────────────────────────────────────────────────────┐
 │                      RENDERING ENGINE                               │
 │  LilyPond CLI: .ly -> PDF (full score + transposed parts)           │
 │  Output packaging: ZIP with PDFs, .ly source, MusicXML export       │
 └─────────────────────────────────────────────────────────────────────┘
                                |
                                v
 ┌─────────────────────────────────────────────────────────────────────┐
 │                    EVALUATION PIPELINE                              │
 │  MusicXML structural diff, audio envelope comparison,               │
 │  visual PDF comparison -- fully automated, no human gate            │
 └─────────────────────────────────────────────────────────────────────┘

 CROSS-CUTTING:
 ┌─────────────────────────────────────────────────────────────────────┐
 │  RAG SYSTEM: ChromaDB vector store of curated LilyPond examples     │
 │  INFERENCE ROUTER: LiteLLM abstraction over Anthropic/OpenAI/LMS    │
 │  CORPUS MANAGER: Ingest, index, and version training triples        │
 └─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Communicates With | Typical Implementation |
|-----------|----------------|-------------------|------------------------|
| **Web UI** | File upload, user hints, ensemble config, job status display, output download | Pipeline Orchestrator (HTTP) | FastAPI endpoints + vanilla HTML/JS with SSE for progress |
| **Pipeline Orchestrator** | Route jobs through stages, manage state, handle MIDI-skip path, retry failures | All stages (in-process function calls) | Python async pipeline with stage functions |
| **Stage 0: Ingest** | Accept audio files (MP3/WAV/AIFF/FLAC), YouTube URLs, MIDI files; normalize to WAV | Orchestrator, filesystem | yt-dlp (YouTube), ffmpeg (format conversion), shutil (file copy) |
| **Stage 1: Source Separation** | Split audio into stems (drums, bass, vocals, other) | Stage 0 output (WAV), filesystem | audio-separator with per-stem model routing (BS-RoFormer for vocals, Mel-Band RoFormer for drums/other, HTDemucs ft for bass) |
| **Stage 2: MIDI Transcription** | Convert each stem to MIDI with pitch, onset, duration, velocity | Stage 1 output (stem WAVs), filesystem | Basic Pitch `predict()` per stem |
| **Stage 3: Audio Understanding** | Produce structured text description of musical content (key, tempo, form, style, dynamics, articulation patterns) | Stage 0/1 output (audio), Inference Router | Qwen3-Omni-Instruct (local via vllm-mlx) or Gemini 3 Flash (cloud API) |
| **Stage 4: LilyPond Generation** | Generate LilyPond code from MIDI + description + user hints, section by section, with joint section-part coherence | Stage 2 (MIDI), Stage 3 (description), RAG system, Inference Router | LLM code generation with RAG context |
| **Rendering Engine** | Compile .ly files to PDF, extract transposed parts, package outputs | Stage 4 output (.ly files), LilyPond CLI | `subprocess.run(["lilypond", ...])` + ZIP packaging |
| **Evaluation Pipeline** | Automated quality scoring: structural diff, audio envelope, visual comparison | Rendering output, reference corpus | MusicXML tree diff, librosa envelope comparison, PDF image diff |
| **RAG System** | Store, retrieve, and rank LilyPond code examples for few-shot prompting | Stage 4 (query), Corpus Manager (ingest) | ChromaDB + sentence-transformers embeddings |
| **Inference Router** | Unified API across Anthropic, OpenAI, LMStudio local endpoints | Stage 3, Stage 4, Evaluation | LiteLLM `completion()` with provider routing |
| **Corpus Manager** | Ingest scores (OMR via Audiveris), index training triples, version data | RAG System, Evaluation Pipeline, filesystem | Python scripts + Audiveris CLI for PDF-to-MusicXML |

## Recommended Project Structure

```
engrave/
├── engrave/                    # Main Python package
│   ├── __init__.py
│   ├── app.py                  # FastAPI application entry point
│   ├── config.py               # Settings, provider config, paths
│   ├── pipeline/               # Pipeline orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Job routing, state machine, stage dispatch
│   │   ├── job.py              # Job model (input, status, artifacts per stage)
│   │   └── stages/             # Individual pipeline stages
│   │       ├── __init__.py
│   │       ├── ingest.py       # Stage 0: file/URL intake, normalization
│   │       ├── separate.py     # Stage 1: audio-separator source separation
│   │       ├── transcribe.py   # Stage 2: Basic Pitch MIDI transcription
│   │       ├── describe.py     # Stage 3: Audio understanding via audio LM
│   │       └── generate.py     # Stage 4: LilyPond code generation
│   ├── inference/              # Multi-provider LLM abstraction
│   │   ├── __init__.py
│   │   ├── router.py           # LiteLLM wrapper, provider selection
│   │   ├── providers.py        # Provider configs (Anthropic, OpenAI, LMStudio)
│   │   └── prompts/            # Prompt templates per stage
│   │       ├── describe.py     # Stage 3 prompt templates
│   │       └── generate.py     # Stage 4 prompt templates (section, coherence)
│   ├── rag/                    # RAG system for LilyPond examples
│   │   ├── __init__.py
│   │   ├── store.py            # ChromaDB vector store operations
│   │   ├── embeddings.py       # Embedding model config
│   │   ├── retriever.py        # Query, rank, format retrieved examples
│   │   └── indexer.py          # Corpus ingestion into vector store
│   ├── rendering/              # LilyPond compilation and output packaging
│   │   ├── __init__.py
│   │   ├── compiler.py         # LilyPond subprocess execution
│   │   ├── parts.py            # Part extraction and transposition
│   │   └── packager.py         # ZIP assembly (PDFs, .ly, MusicXML)
│   ├── evaluation/             # Automated quality assessment
│   │   ├── __init__.py
│   │   ├── runner.py           # Evaluation pipeline orchestration
│   │   ├── structural.py       # MusicXML tree diff
│   │   ├── audio.py            # Audio envelope comparison
│   │   └── visual.py           # PDF visual diff (image-based)
│   ├── corpus/                 # Training data management
│   │   ├── __init__.py
│   │   ├── ingest.py           # OMR (Audiveris), MIDI parsing, triple assembly
│   │   ├── triples.py          # (LilyPond, MIDI tokens, text description) format
│   │   └── sources.py          # IMSLP, Mutopia, Sam's originals metadata
│   ├── models/                 # Data models (not ML models)
│   │   ├── __init__.py
│   │   ├── job.py              # Pydantic models for pipeline jobs
│   │   ├── ensemble.py         # Ensemble presets, instrument configs
│   │   └── music.py            # Musical domain models (key, tempo, section)
│   └── web/                    # Web UI
│       ├── __init__.py
│       ├── routes.py           # FastAPI route handlers
│       ├── sse.py              # Server-Sent Events for progress
│       └── static/             # HTML/JS/CSS assets
│           ├── index.html
│           ├── app.js
│           └── style.css
├── data/                       # Local data (gitignored except structure)
│   ├── corpus/                 # Training triples, indexed examples
│   ├── jobs/                   # Per-job working directories
│   └── chromadb/               # Vector store persistence
├── scripts/                    # CLI utilities
│   ├── ingest_corpus.py        # Bulk corpus ingestion
│   ├── benchmark_models.py     # Model comparison for Stage 4
│   └── evaluate.py             # Run evaluation pipeline on test set
├── tests/
│   ├── test_pipeline/
│   ├── test_inference/
│   ├── test_rag/
│   └── fixtures/               # Sample audio, MIDI, .ly files for tests
├── pyproject.toml
└── Makefile                    # Common commands (run, test, ingest, evaluate)
```

### Structure Rationale

- **engrave/pipeline/stages/**: Each stage is an isolated module with a clear input/output contract. The orchestrator calls them; they do not call each other. This makes it trivial to skip stages (MIDI input skips Stage 0-1) or swap implementations (different audio-separator models, MT3 for Basic Pitch).
- **engrave/inference/**: Separating inference routing from pipeline logic means any stage can call any LLM without knowing which provider serves it. Provider configs live here, not scattered across stages.
- **engrave/rag/**: The RAG system is a service consumed by Stage 4 but managed independently. Corpus changes (new examples indexed) do not require pipeline code changes.
- **engrave/rendering/**: LilyPond compilation is isolated because it is a subprocess boundary (shelling out to `lilypond` CLI). Keeping it separate makes error handling and timeout management clean.
- **data/jobs/**: Each pipeline run gets a working directory under `data/jobs/{job_id}/` with subdirectories per stage. This makes debugging trivial -- you can inspect any intermediate artifact.

## Architectural Patterns

### Pattern 1: Stage-Based Pipeline with Artifact Passing

**What:** Each pipeline stage is a pure function: `(job_context, stage_input_dir) -> stage_output_dir`. Stages communicate through the filesystem, not in-memory. The orchestrator manages the job directory and routes between stages.

**When to use:** Always. This is the core pattern for the entire pipeline.

**Trade-offs:** Filesystem I/O is slower than in-memory passing, but artifacts are inspectable, debuggable, and resumable. For audio/MIDI files that are already disk-bound, this adds negligible overhead.

**Example:**
```python
# engrave/pipeline/orchestrator.py
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class JobContext:
    job_id: str
    job_dir: Path
    input_type: str          # "audio", "youtube", "midi"
    ensemble_preset: dict
    user_hints: str
    stage_status: dict[str, StageStatus]

    def stage_dir(self, stage_name: str) -> Path:
        d = self.job_dir / stage_name
        d.mkdir(parents=True, exist_ok=True)
        return d

async def run_pipeline(ctx: JobContext) -> Path:
    """Execute pipeline stages in sequence, skipping as appropriate."""
    if ctx.input_type == "midi":
        ctx.stage_status["ingest"] = StageStatus.SKIPPED
        ctx.stage_status["separate"] = StageStatus.SKIPPED
        # MIDI goes directly to Stage 2 output format
        await stages.ingest_midi(ctx)
    else:
        await stages.ingest(ctx)       # Stage 0
        await stages.separate(ctx)     # Stage 1

    await stages.transcribe(ctx)       # Stage 2
    await stages.describe(ctx)         # Stage 3
    await stages.generate(ctx)         # Stage 4
    output = await rendering.compile_and_package(ctx)
    return output
```

### Pattern 2: Section-by-Section Generation with Coherence State

**What:** Long scores are divided into sections (by rehearsal mark, structural boundary, or fixed bar count). Each section is generated in a separate LLM call, but a running "coherence state" document is maintained and passed forward. The coherence state tracks: current key/tempo/time signature, active articulation conventions, dynamic level per instrument, voicing patterns established, and a summary of what has been generated so far.

**When to use:** Any score longer than approximately 16-32 bars. Short lead sheets can be generated in a single pass.

**Trade-offs:** More LLM calls means higher latency and cost. But single-pass generation of a 200-bar big band chart will exceed context windows and lose coherence. The coherence state acts as "memory" across calls.

**Why this works:** Research on long-form LLM generation (Hierarchical Expansion pattern) shows that maintaining a running summary of content generated so far and feeding it as context to subsequent generation calls preserves coherence far better than attempting single-pass generation. Coherence drops sharply after ~2000 tokens of generated code in a single pass.

**Example:**
```python
# engrave/pipeline/stages/generate.py

@dataclass
class CoherenceState:
    """Running state passed between section generation calls."""
    key_signature: str
    time_signature: str
    tempo: int
    section_index: int
    total_sections: int
    articulation_conventions: dict   # e.g., {"accent": "marcato", "staccato_style": "portato"}
    dynamic_levels: dict[str, str]   # instrument -> current dynamic
    voicing_patterns: list[str]      # established voicing descriptions
    generated_summary: str           # Chain-of-density summary of .ly code so far

async def generate_section(
    section_midi: dict[str, Any],     # MIDI data for this section
    audio_description: str,           # Stage 3 output for this section
    coherence: CoherenceState,
    ensemble: EnsembleConfig,
    rag_examples: list[str],
    user_hints: str,
    inference: InferenceRouter,
) -> tuple[str, CoherenceState]:
    """Generate LilyPond for one section, returning code + updated state."""

    prompt = build_section_prompt(
        section_midi=section_midi,
        description=audio_description,
        coherence=coherence,
        ensemble=ensemble,
        rag_examples=rag_examples,
        user_hints=user_hints,
    )

    ly_code = await inference.complete(prompt, model_preference="code")

    # Update coherence state for next section
    updated_coherence = extract_coherence_state(ly_code, coherence)
    return ly_code, updated_coherence
```

### Pattern 3: Joint Section-Part Generation for Convergent Sight-Reading

**What:** Within each section, all parts for an instrument group (e.g., "Trumpet 1-4") are generated in a single LLM call, not independently. The prompt explicitly instructs the LLM to co-vary articulations, align dynamics, match beam groupings, and ensure section-wide emphasis patterns. This is the core architectural decision that enables convergent sight-reading.

**When to use:** Always, for any multi-part section (brass section, sax section, etc.). Solo instruments and rhythm section instruments may be generated independently.

**Trade-offs:** Larger prompt and output per call (4 trumpet parts in one response vs. 4 separate calls). But independent generation is the primary failure mode for ensemble coherence -- if Trumpet 1 gets staccato and Trumpet 2 gets legato on the same passage, the section will not sound unified in sight-reading.

**Example:**
```python
# Within generate_section():

# BAD: Generate each part independently
for instrument in section.instruments:
    part_code = await generate_part(instrument, ...)  # NO -- parts diverge

# GOOD: Generate section groups jointly
for section_group in ensemble.section_groups:
    # e.g., section_group = ["Trumpet 1", "Trumpet 2", "Trumpet 3", "Trumpet 4"]
    joint_code = await generate_section_group(
        instruments=section_group,
        section_midi=section_midi,
        coherence=coherence,
        instruction="Generate all parts simultaneously. Articulations MUST "
                    "co-vary: if Trumpet 1 has marcato, all trumpets have marcato. "
                    "Dynamics MUST align across the section. Beam groupings MUST "
                    "reflect section-wide emphasis patterns.",
    )
    # joint_code contains all 4 trumpet parts in one LilyPond block
```

### Pattern 4: Multi-Provider Inference via LiteLLM

**What:** Use LiteLLM as a unified abstraction over Anthropic API, OpenAI API, and LMStudio local endpoints. All LLM calls go through a single `InferenceRouter` that selects the provider based on configuration, model preference, and availability. LMStudio exposes an OpenAI-compatible API at `http://localhost:1234/v1`, so LiteLLM treats it as another OpenAI-compatible endpoint.

**When to use:** Every LLM call in the system. Never call provider APIs directly.

**Trade-offs:** LiteLLM adds a thin abstraction layer. For a prototype, this is the right trade-off -- the team needs to benchmark multiple models (Qwen3, gpt-oss, Claude, GPT-4) and switch freely. LiteLLM is free, open-source, and widely adopted. For this single-user prototype, production-scale concerns (memory leaks, latency overhead) are irrelevant.

**Example:**
```python
# engrave/inference/router.py
import litellm

class InferenceRouter:
    def __init__(self, config: dict):
        self.providers = config["providers"]  # keyed by name
        self.default_provider = config["default_provider"]

    async def complete(
        self,
        prompt: str,
        model_preference: str = "default",
        temperature: float = 0.3,
    ) -> str:
        model = self._resolve_model(model_preference)
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content

    def _resolve_model(self, preference: str) -> str:
        """Map preference to actual model string.

        Examples:
          "code" -> "anthropic/claude-sonnet-4-20250514" (best at code gen)
          "audio" -> "openai/lmstudio-community/qwen2-audio-7b"
          "local" -> "openai/lmstudio-community/qwen3-30b"
          "default" -> whatever is configured
        """
        return self.providers.get(preference, self.providers[self.default_provider])
```

### Pattern 5: RAG for LilyPond Code Generation

**What:** A ChromaDB vector store holds curated LilyPond code examples as training triples: (LilyPond source, MIDI token summary, structured text description). When Stage 4 generates LilyPond for a section, the RAG retriever queries for similar examples based on the section's musical description and MIDI characteristics. Retrieved examples are injected into the prompt as few-shot context.

**When to use:** Every Stage 4 generation call.

**Trade-offs:** RAG quality depends entirely on corpus quality. Bad examples = bad generation. The initial corpus must be carefully curated. ChromaDB is the right choice for a prototype: embedded (no server), persistent, Python-native, and sufficient for thousands of examples.

**Embedding strategy:** Use `sentence-transformers/all-MiniLM-L6-v2` for text embeddings of the structured descriptions. Do NOT embed raw LilyPond code -- embed the musical descriptions, then return the associated LilyPond code. The retrieval query is the section's musical description from Stage 3 + ensemble type + user hints.

**Example:**
```python
# engrave/rag/retriever.py
import chromadb

class LilyPondRetriever:
    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="lilypond_examples",
            metadata={"hnsw:space": "cosine"},
        )

    def retrieve(
        self,
        query: str,          # Musical description of current section
        ensemble_type: str,  # e.g., "big_band"
        n_results: int = 5,
    ) -> list[dict]:
        """Retrieve similar LilyPond examples for few-shot prompting."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"ensemble_type": ensemble_type} if ensemble_type else None,
        )
        return [
            {
                "description": meta["description"],
                "lilypond": meta["lilypond_source"],
                "similarity": 1 - dist,
            }
            for meta, dist in zip(
                results["metadatas"][0], results["distances"][0]
            )
        ]
```

## Data Flow

### Primary Pipeline Flow (Audio Input)

```
User uploads audio + hints + ensemble config
    |
    v
[Stage 0: Ingest]
    Input:  raw audio file (MP3/WAV/AIFF/FLAC) or YouTube URL
    Output: normalized WAV (44.1kHz, stereo) in job_dir/ingest/
    |
    v
[Stage 1: Source Separation]
    Input:  WAV from Stage 0
    Output: 4 stem WAVs (drums.wav, bass.wav, vocals.wav, other.wav) in job_dir/separate/
    Notes:  Uses audio-separator with per-stem model routing (BS-RoFormer for vocals, Mel-Band RoFormer for drums/other, HTDemucs ft for bass). Different models may be used per stem target for optimal quality.
    |
    v
[Stage 2: MIDI Transcription]
    Input:  stem WAVs from Stage 1
    Output: MIDI files per stem (drums.mid, bass.mid, vocals.mid, other.mid) in job_dir/transcribe/
    Notes:  Basic Pitch runs independently per stem. Output includes pitch bends.
    |
    v  (in parallel with Stage 2)
[Stage 3: Audio Understanding]
    Input:  original WAV from Stage 0 (full mix for context) + stem WAVs from Stage 1
    Output: structured JSON description in job_dir/describe/description.json
            {
              "key": "Bb major",
              "tempo": 138,
              "time_signature": "4/4",
              "form": ["Intro(4)", "A(16)", "B(8)", "Soli(16)", "Shout(8)", "Tag(4)"],
              "style": "swing",
              "dynamics_arc": "mp -> mf -> f -> ff -> mf",
              "articulation_notes": "Brass: heavy marcato on hits, legato on soli lines",
              "notable_features": "Soli section at bar 17 for full sax section"
            }
    |
    v
[Stage 4: LilyPond Generation] (receives MIDI from Stage 2 + description from Stage 3)
    Input:  MIDI per stem, structured description, user hints, ensemble config
    Process:
      1. Divide score into sections using form markers from Stage 3
      2. For each section:
         a. Query RAG for similar LilyPond examples
         b. Build prompt with: MIDI data, description, RAG examples, coherence state, ensemble config
         c. Generate LilyPond for each section group (brass, saxes, rhythm) jointly
         d. Update coherence state
      3. Assemble section outputs into complete .ly file with headers, paper settings
    Output: Complete .ly files in job_dir/generate/ (score.ly + individual part .ly files)
    |
    v
[Rendering Engine]
    Input:  .ly files from Stage 4
    Process:
      1. Run `lilypond --pdf score.ly` for full conductor score
      2. Run `lilypond --pdf {part}.ly` for each transposed part
      3. Optionally convert to MusicXML via ly2musicxml or internal LilyPond export
      4. Package all outputs into ZIP
    Output: job_dir/output/ containing PDFs, .ly sources, MusicXML, ZIP bundle
```

### Alternate Flow: MIDI Input

```
User uploads MIDI file
    |
    v
[Stage 0: Ingest]
    Input:  MIDI Type 0 or Type 1 file
    Output: Parsed MIDI in job_dir/ingest/ (tracks identified, no audio needed)
    Note:   Stage 1 (separation) is SKIPPED entirely
    |
    v
[Stage 2: MIDI Transcription] -- effectively a pass-through / reformatting step
    Input:  MIDI from Stage 0
    Output: Normalized MIDI per track in job_dir/transcribe/
    Note:   May need track-to-instrument mapping from user hints
    |
    v
[Stage 3: Audio Understanding] -- runs on MIDI, not audio
    Input:  MIDI data (no audio available)
    Output: Structured description inferred from MIDI content
    Note:   Less rich than audio-based description; relies more on MIDI analysis
            (key detection, tempo, time signature from MIDI headers/content)
    |
    v
[Stage 4 -> Rendering] -- same as audio path
```

### Parallel Execution Opportunity

Stages 2 and 3 can run in parallel after Stage 1 completes. Stage 2 processes stems to MIDI while Stage 3 analyzes the audio for musical description. Stage 4 needs both outputs. This is the only parallelism opportunity in the main pipeline -- the stages are otherwise sequential.

```
Stage 0 -> Stage 1 -> [Stage 2 ┐
                       [Stage 3 ┘ -> Stage 4 -> Rendering
```

### RAG Data Flow

```
[Corpus Manager]
    Input:  Sam's 350 PDF scores + recordings, IMSLP/Mutopia scores
    Process:
      1. Audiveris OMR: PDF -> MusicXML
      2. MusicXML -> LilyPond source (via musicxml2ly or manual curation)
      3. MusicXML -> MIDI tokens (via music21 or direct parsing)
      4. Audio/MIDI -> structured text description (via Stage 3 pipeline or manual)
      5. Assemble training triple: (LilyPond, MIDI tokens, text description)
      6. Embed text description via sentence-transformers
      7. Store in ChromaDB with metadata (ensemble type, style, complexity)
    |
    v
[ChromaDB Vector Store]
    Contents: embedded descriptions + associated LilyPond code + metadata
    |
    v
[RAG Retriever] -- called by Stage 4 per section
    Query: section description + ensemble type
    Return: top-k similar LilyPond examples for few-shot prompting
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Anthropic API** | Via LiteLLM `anthropic/claude-*` | Stage 4 code generation. Requires `ANTHROPIC_API_KEY` env var. |
| **OpenAI API** | Via LiteLLM `openai/gpt-*` | Stage 4 code generation. Requires `OPENAI_API_KEY` env var. |
| **LMStudio** | Via LiteLLM `openai/...` with `api_base=http://localhost:1234/v1` | Local inference for Stage 4 (Qwen3-Coder-Next, gpt-oss). Start with `lms server start`. OpenAI-compatible endpoint. |
| **mlx_lm / mlx_vlm** | Direct Python inference or OpenAI-compatible API | Local inference for Stage 3 (Qwen3-Omni-Instruct MoE via mlx_lm) and Evaluation (Qwen3-VL via mlx_vlm). Loads HuggingFace models natively on Apple Silicon — no conversion needed. |
| **vllm-mlx** | Via OpenAI-compatible API on localhost | Alternative serving layer for Apple Silicon when an always-on OpenAI-compatible endpoint is preferred over direct mlx_lm Python calls. |
| **Gemini API** | Via LiteLLM `gemini/gemini-3-flash` | Stage 3 alternative for long-form audio understanding. Requires `GEMINI_API_KEY`. Best for audio >10 min. |
| **YouTube** | Via yt-dlp Python API | Stage 0 ingest. Requires external JS runtime (Deno) for 2025+ YouTube challenges. |
| **LilyPond CLI** | Via `subprocess.run()` | Rendering stage. Must be installed system-wide (`brew install lilypond`). |
| **Audiveris** | Via CLI subprocess (Java) | Corpus ingestion only, not runtime pipeline. PDF -> MusicXML for training data. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Web UI <-> Orchestrator | HTTP (FastAPI routes) + SSE for progress | Async: upload returns job_id, client polls or subscribes to SSE stream |
| Orchestrator <-> Stages | In-process async function calls | Stages are pure functions, not services. No RPC overhead needed for single-user prototype. |
| Stages <-> Filesystem | Direct file I/O in job directory | Each stage reads from predecessor's output dir, writes to its own output dir |
| Stage 4 <-> RAG | In-process function call to ChromaDB | ChromaDB runs embedded (no separate server). Fast for <100K documents. |
| Stage 3/4 <-> Inference Router | In-process async call to LiteLLM | LiteLLM handles HTTP to external providers internally |
| Pipeline <-> Evaluation | Separate invocation (not part of main pipeline) | Evaluation runs post-hoc on completed jobs, comparing outputs to reference corpus |

## Anti-Patterns

### Anti-Pattern 1: Independent Part Generation

**What people do:** Generate each instrument part in a separate LLM call (Trumpet 1 alone, then Trumpet 2 alone, etc.)
**Why it is wrong:** Parts diverge in articulation, dynamics, and phrasing. The whole point of "convergent sight-reading" is that section players independently arrive at the same musical interpretation. Independent generation guarantees they will not.
**Do this instead:** Generate all parts within a section group (e.g., all 4 trumpets) in a single LLM call with explicit instructions for co-varying articulations and aligned dynamics.

### Anti-Pattern 2: Single-Pass Full-Score Generation

**What people do:** Send the entire score's MIDI + description to the LLM in one call and ask for the complete LilyPond output.
**Why it is wrong:** Context windows overflow for long scores. Even within context, coherence degrades past ~2000 tokens of generated code. A 200-bar big band chart with 13+ parts will exceed any reasonable output limit.
**Do this instead:** Section-by-section generation with coherence state passing. Generate 8-32 bars per call, maintaining a running state document.

### Anti-Pattern 3: Embedding Raw LilyPond for RAG Retrieval

**What people do:** Embed LilyPond source code directly and use code similarity for retrieval.
**Why it is wrong:** LilyPond syntax is structurally repetitive -- `\relative c' { ... }` appears everywhere. Embedding raw code produces poor semantic retrieval. Two musically similar passages may have very different LilyPond syntax, and two syntactically similar passages may be musically unrelated.
**Do this instead:** Embed the structured text descriptions of the music. Retrieve based on musical similarity (key, instrumentation, style, complexity), then return the associated LilyPond code as examples.

### Anti-Pattern 4: Microservice Architecture for a Prototype

**What people do:** Deploy each stage as a separate service with message queues, API gateways, and container orchestration.
**Why it is wrong:** This is a single-user prototype running on one M4 Max machine. Microservices add enormous operational complexity with zero benefit. The pipeline runs sequentially; there is no scaling need.
**Do this instead:** Monolith with clean module boundaries. Stages are functions, not services. If this ever needs to scale, the clean boundaries make extraction into services straightforward later.

### Anti-Pattern 5: Using Abjad as an Intermediate Representation

**What people do:** Have the LLM generate Abjad Python code (which then produces LilyPond), adding an extra abstraction layer.
**Why it is wrong:** Adds a translation layer that the LLM must learn. LLMs are already excellent at generating LilyPond directly -- it is a well-documented text format with extensive training data. Abjad is useful for programmatic composition but adds unnecessary complexity when the LLM can output LilyPond directly.
**Do this instead:** Generate LilyPond syntax directly. Use Abjad only if you need to programmatically manipulate notation after generation (e.g., automated transposition), and even then, LilyPond's built-in transposition may suffice.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (Sam) | Monolith on M4 Max. Local audio-separator/Basic Pitch. LMStudio for cheap prototyping. Cloud APIs when local models underperform. No queueing needed. |
| 5-10 users | Add Celery/Redis job queue for background processing. Still single server. Multiple concurrent jobs need queuing since audio-separator models are memory-hungry (~4-6GB per model). |
| 100+ users | audio-separator/Basic Pitch on GPU workers (separate from web server). LLM calls already go to cloud APIs. ChromaDB may need migration to a hosted vector DB (Pinecone, Weaviate). |

### Scaling Priorities (if ever needed)

1. **First bottleneck:** audio-separator model memory usage. BS-RoFormer/Mel-Band RoFormer need ~4-6GB RAM per separation. On a 128GB M4 Max, this allows ~20 concurrent separations. A job queue with concurrency limits solves this without architectural changes.
2. **Second bottleneck:** LLM call latency for Stage 4. Section-by-section generation of a long score means many sequential LLM calls. Mitigation: batch sections where possible, use faster models (local Qwen3-30B-a3B is very fast on M4 Max), cache RAG retrievals per section.

## Build Order Implications

The architecture has clear dependency chains that dictate build order:

### Tier 1: Foundation (must exist before anything else)
1. **Project scaffolding** -- pyproject.toml, package structure, config system
2. **Inference Router** -- LiteLLM setup with multi-provider config. Everything downstream needs this.
3. **Stage 0: Ingest** -- File handling, yt-dlp, ffmpeg normalization. The entry point for all data.

### Tier 2: Audio-to-MIDI Pipeline (build bottom-up)
4. **Stage 1: Source Separation** -- audio-separator integration. Depends on Ingest output format.
5. **Stage 2: MIDI Transcription** -- Basic Pitch integration. Depends on Separation output format.
6. **Pipeline Orchestrator (basic)** -- Wire Stages 0-1-2 together with job directory management.

### Tier 3: Intelligence Layer (the hard part)
7. **Stage 3: Audio Understanding** -- Audio LM integration. Can be developed in parallel with Tier 2 once Ingest exists.
8. **RAG System** -- ChromaDB setup, embedding pipeline, retriever. Can be developed in parallel.
9. **Corpus Manager (initial)** -- Enough to seed RAG with a handful of curated examples.

### Tier 4: Code Generation (depends on Tiers 2+3)
10. **Stage 4: LilyPond Generation** -- The core value. Needs MIDI (Tier 2), descriptions (Tier 3), RAG (Tier 3), and Inference Router (Tier 1).
11. **Rendering Engine** -- LilyPond CLI integration, part extraction, packaging.

### Tier 5: Quality and UI
12. **Evaluation Pipeline** -- Automated quality assessment. Needs rendered output to evaluate.
13. **Web UI** -- FastAPI routes, upload flow, progress display. Can be developed in parallel with Tier 4 using mock data.

### Key Dependency: Stage 4 is the critical path
Everything before Stage 4 is plumbing -- important but well-understood. Stage 4 (LilyPond generation with section coherence and joint part generation) is where the novel value lives and where the most iteration will be needed. The architecture should be built to enable rapid experimentation at Stage 4: easy prompt iteration, quick model swapping, fast RAG updates.

## Sources

- [audio-separator PyPI](https://pypi.org/project/audio-separator/) -- HIGH confidence: multi-model source separation wrapper
- [Demucs GitHub (facebookresearch)](https://github.com/facebookresearch/demucs) -- HIGH confidence: primary source (note: development moved to adefossez/demucs, HTDemucs ft accessible via audio-separator)
- [Basic Pitch GitHub (Spotify)](https://github.com/spotify/basic-pitch) -- HIGH confidence: official repository
- [Basic Pitch PyPI](https://pypi.org/project/basic-pitch/) -- HIGH confidence: official package
- [MT3 GitHub (Magenta)](https://github.com/magenta/mt3) -- HIGH confidence: official repository
- [Qwen3-Omni-30B-A3B-Captioner (HuggingFace)](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Captioner) -- HIGH confidence: official model card
- [vllm-mlx GitHub](https://github.com/waybarrios/vllm-mlx) -- MEDIUM confidence: community project for vLLM on Apple Silicon
- [LiteLLM Documentation](https://docs.litellm.ai/docs/) -- HIGH confidence: official docs
- [LiteLLM GitHub](https://github.com/BerriAI/litellm) -- HIGH confidence: official repository
- [LM Studio OpenAI Compatibility](https://lmstudio.ai/docs/developer/openai-compat) -- HIGH confidence: official docs
- [LM Studio Server Docs](https://lmstudio.ai/docs/developer/core/server) -- HIGH confidence: official docs
- [Abjad (Python LilyPond API)](https://github.com/Abjad/abjad) -- HIGH confidence: official repository, v3.31 Oct 2025
- [ChromaDB Documentation](https://www.trychroma.com/) -- MEDIUM confidence: well-established but RAG-for-code-gen is novel application
- [Hierarchical Expansion for Long-Form Generation (OpenCredo)](https://opencredo.com/blogs/how-to-use-llms-to-generate-coherent-long-form-content-using-hierarchical-expansion) -- MEDIUM confidence: pattern description, not specific to music
- [Audio-to-Sheet-Music Pipeline (Music Demixer)](https://freemusicdemixer.com/under-the-hood/2025/03/09/Audio-to-sheet-music) -- MEDIUM confidence: demonstrates source separation + Basic Pitch combined workflow
- [MusicXML Diff Procedure (ACM)](https://dl.acm.org/doi/abs/10.1145/3358664.3358671) -- MEDIUM confidence: academic paper on score comparison
- [Audiveris OMR](https://github.com/Audiveris/audiveris) -- MEDIUM confidence: established tool, Python automation less documented
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp) -- HIGH confidence: official repository
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) -- HIGH confidence: official documentation

---
*Architecture research for: AI-powered music engraving pipeline*
*Researched: 2026-02-24*
