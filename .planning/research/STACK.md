# Stack Research

**Domain:** AI-powered audio-to-sheet-music engraving pipeline
**Researched:** 2026-02-24
**Confidence:** MEDIUM (core pipeline libraries verified; some model ecosystem details based on fast-moving 2026 landscape)

## Recommended Stack

### Runtime & Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | FastAPI recommends 3.12; all ML libraries support it; 3.13/3.14 support still maturing in PyTorch ecosystem. Avoid 3.13+ until torch fully supports it. |
| FastAPI | 0.132.0 | HTTP API server | De facto Python API framework for ML apps. Async-native, Pydantic v2 integration, OpenAPI auto-docs. Install as `fastapi[standard]`. |
| Pydantic | 2.12.x | Data validation / config | Required by FastAPI. Use v2 -- significant perf gains over v1. Drives request/response schemas and pipeline config. |
| Uvicorn | latest | ASGI server | Ships with `fastapi[standard]`. Use `uvicorn[standard]` for uvloop on macOS. |
| PyTorch | 2.10.0 | ML framework | Required by Demucs, MT3, Basic Pitch, and Qwen2-Audio. MPS backend for Apple Silicon GPU acceleration. |

### Source Separation (Stage 1)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| demucs-infer | 4.1.2 | Audio source separation | Use `demucs-infer` NOT `demucs`. The original `demucs` package (4.0.1) is abandoned (last release Sep 2023, repo archived). `demucs-infer` is inference-only, optimized for PyTorch 2.x, supports Python 3.12, released Jan 2026. Uses htdemucs model (Hybrid Transformer, 9.0 dB SDR). Runs on MPS (Apple Silicon GPU). |

**Model choice:** `htdemucs_ft` (fine-tuned) for best quality. 4x slower than `htdemucs` but worth it for a non-realtime pipeline. Separates into drums, bass, vocals, other. The `htdemucs_6s` model adds piano and guitar stems but piano quality is poor -- avoid for v1.

### MIDI Transcription (Stage 2)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| basic-pitch | 0.4.0 | Primary MIDI transcription | Spotify's lightweight CNN-based AMT. <20MB memory, <17K params. Pip-installable. Polyphonic, instrument-agnostic, pitch bend detection. Best on single-instrument stems (which is exactly what Demucs produces). |
| MT3 (magenta/mt3) | research | Multi-track transcription fallback | Google's transformer-based multi-instrument AMT. SOTA accuracy on multi-instrument audio. Use as validation/comparison, not primary path. Requires T5X/JAX stack which conflicts with PyTorch ecosystem -- run in isolated environment. |

**Rationale for Basic Pitch as primary:** After Demucs separation, each stem is effectively single-instrument. Basic Pitch excels at single-instrument transcription with pitch bends. MT3's multi-track capability is redundant post-separation and its JAX dependency creates friction in a PyTorch-centric pipeline.

**Pipeline strategy:** Demucs separates -> Basic Pitch transcribes each stem individually -> merge MIDI tracks. Fall back to MT3 for validation or for pre-mixed audio where separation is skipped (e.g., piano solo recordings).

### Audio Understanding (Stage 3)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Qwen2-Audio-7B-Instruct | 7B | Local audio language model | Runs locally on M4 Max via Hugging Face transformers or GGUF. Handles audio + text input, produces structured musical descriptions (key, tempo, instrumentation, style, dynamics). 7B fits comfortably in 128GB unified memory alongside other pipeline stages. |
| Qwen2.5-Omni-7B | 7B | Upgraded audio LM (evaluate) | Successor to Qwen2-Audio with better audio reasoning. Thinker-Talker architecture. SOTA on OmniBench. Evaluate against Qwen2-Audio for music description quality. |
| Gemini 2.5 Flash | cloud API | Long-form audio understanding | Best for full-length recordings (1M token context). Use for initial audio analysis of complete tracks before separation. Cloud-only. $1.00/M audio tokens input. NOTE: Gemini 2.0 Flash retires June 2026 -- use 2.5 Flash. |
| LFM2.5-Audio-1.5B | 1.5B | Lightweight local audio model | Liquid AI's tiny audio model. 8x faster than predecessor. llama.cpp compatible GGUFs. Good for quick ASR/description tasks. Matt has prior experience with Liquid models. Use as fast-path for simple audio understanding tasks. |

**Strategy:** Use Qwen2-Audio-7B as primary local audio LM for structured music description. Use Gemini 2.5 Flash for complex/long audio when cloud is acceptable. LFM2.5-Audio for lightweight tasks. Evaluate Qwen2.5-Omni-7B as potential upgrade.

### LilyPond Code Generation (Stage 4)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Qwen3-Coder-Next | 80B (3B active) | Primary local code gen LLM | Apache 2.0 MoE model, 256K context. Only activates 3B params per token from 80B total. 70.6% SWE-Bench. Runs at 100+ tok/s on M4 Max in 4-bit GGUF (~46GB RAM). Leaves headroom in 128GB for other pipeline stages. Best open code model for LilyPond generation. |
| gpt-oss-120b | 120B (5.1B active) | Alternative local code gen LLM | OpenAI's open MoE model. Apache 2.0. Near o4-mini quality. GGUF 4-bit ~63GB. Will run on M4 Max 128GB but slower than Qwen3-Coder-Next and leaves less headroom. Use for benchmarking against Qwen3-Coder-Next. |
| gpt-oss-20b | 20B (3.6B active) | Fast local code gen | Smaller sibling. Fits in 16GB. Fast inference. Use for rapid iteration/prototyping before switching to larger models. |
| Claude (Anthropic API) | cloud API | Cloud code gen benchmark | Use via Anthropic SDK for quality ceiling benchmark. Anthropic API is a project requirement. |
| GPT-4 / GPT-4o | cloud API | Cloud code gen benchmark | Use via OpenAI SDK for quality ceiling benchmark. OpenAI API is a project requirement. |

**Strategy:** Qwen3-Coder-Next as primary local model (best quality/speed ratio on M4 Max). gpt-oss-20b for fast prototyping. Cloud APIs (Claude, GPT-4) as quality ceiling for benchmarking. gpt-oss-120b for local ceiling benchmark.

### Multi-Provider Inference Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LiteLLM | latest (Feb 2026) | Unified LLM interface | Wraps 100+ LLM APIs in OpenAI-compatible format. Call Anthropic, OpenAI, and LMStudio local endpoints through one interface. 8ms P95 latency overhead. Eliminates per-provider client code. |
| LM Studio | 0.4.x | Local model serving | MLX engine for Apple Silicon. OpenAI-compatible API on localhost:1234. `lms` CLI for model management. Drop-in replacement for OpenAI SDK by changing base_url. Supports GGUF and MLX formats. |
| openai (SDK) | 2.23.0 | OpenAI API client | Also used as client for LMStudio (OpenAI-compatible endpoint). Required project dependency. |
| anthropic (SDK) | 0.83.0 | Anthropic API client | Required for Claude API access. Used through LiteLLM or directly. |

**Architecture decision:** Use LiteLLM as the unified interface for all LLM calls. Configure providers:
- `anthropic/claude-*` -> Anthropic API
- `openai/gpt-*` -> OpenAI API
- `openai/local-*` -> LMStudio (base_url=http://localhost:1234/v1)

This means pipeline code calls `litellm.completion()` everywhere, provider selection is configuration-only.

### RAG System

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LlamaIndex | 0.14.15 | RAG framework | Superior retrieval accuracy for document-heavy RAG (35% boost in 2025). Better than LangChain for focused retrieval tasks. Modular -- use only the pieces needed. |
| ChromaDB | 1.5.1 | Vector database | Embedded (no server needed), pip-installable, Python-native. Good for datasets under 1M vectors (our LilyPond corpus will be far smaller). BM25 + vector search. Sentence Transformers default embeddings. |
| llama-index-vector-stores-chroma | latest | ChromaDB integration | Official LlamaIndex integration for ChromaDB. |

**RAG strategy:** Index curated LilyPond examples as (lilypond_source, musical_description, midi_features) triples. At generation time, retrieve similar examples as few-shot context for the code gen LLM. LlamaIndex handles chunking, embedding, retrieval. ChromaDB stores vectors locally.

**Why NOT LangChain:** LangChain is better for complex multi-tool orchestration. Our RAG is focused retrieval (find similar LilyPond examples) -- LlamaIndex is purpose-built for this. Simpler, fewer abstractions, better retrieval quality.

### Music Notation & Rendering

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LilyPond | 2.24.4 (stable) | Music engraving / PDF rendering | Text-based input = LLM-friendly. Publication-quality output. Open source. Supports all notation features needed (transposition, parts extraction, articulations, dynamics, beaming). Use stable release, not dev (2.25.x). |
| Abjad | 3.31 | Python API for LilyPond | Build LilyPond files programmatically. Iterative/incremental notation construction. Requires LilyPond 2.25.26+ (dev branch). **Use for validation/post-processing only** -- LLM generates raw LilyPond, Abjad validates/corrects structure. |
| python-ly | 0.9.5 | LilyPond file parsing | Parse and manipulate LilyPond source. Use for post-processing LLM output: syntax checking, formatting, structure validation. Mature, stable. |

**Architecture decision:** LLM generates raw LilyPond code (text). python-ly validates syntax. Abjad provides programmatic manipulation if needed (transposition, part extraction). LilyPond CLI renders to PDF via `subprocess`. Do NOT use Abjad to generate LilyPond from scratch -- let the LLM do that. Abjad is the safety net.

**LilyPond version consideration:** Abjad 3.31 requires LilyPond 2.25.26+ (dev). For production stability, install both LilyPond 2.24.4 (stable, for rendering) and 2.25.x (dev, for Abjad integration). Or skip Abjad initially and use python-ly + subprocess.

### Audio & Media Input

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| yt-dlp | 2026.02.x | YouTube audio extraction | Actively maintained (weekly releases). Extracts audio from YouTube URLs. Sam's 350 recordings are on YouTube. |
| ffmpeg | latest | Audio format conversion | Required by Demucs and most audio processing. Convert between WAV/MP3/FLAC/AIFF. Install via Homebrew. |
| mido | latest | MIDI file parsing | Lightweight Python MIDI library. Read/write Type 0 and Type 1 MIDI files. Use for MIDI input pathway and post-Basic-Pitch processing. |
| pretty_midi | latest | MIDI analysis | Higher-level MIDI analysis (tempo estimation, instrument programs, note statistics). Complements mido. |
| librosa | latest | Audio analysis | Audio feature extraction (tempo, key, onset detection, spectrograms). Use for pre-processing before Demucs and for audio feature extraction. |

### Corpus & Evaluation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Audiveris | latest | OMR (PDF to MusicXML) | Open-source optical music recognition. Converts Sam's 350 PDF scores to MusicXML. Java-based, runs as external process. Accuracy is imperfect -- plan for manual corrections. |
| music21 | latest | MusicXML analysis | MIT Music21 library for computational music analysis. Parse MusicXML, compute structural diffs, compare scores. Use in evaluation pipeline. |
| pdf2image / Pillow | latest | PDF visual comparison | Render PDFs to images for visual diff in evaluation pipeline. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager | Fast, replaces pip + venv. Use `uv init`, `uv add`, `uv run`. Modern Python project management. |
| ruff | Linting + formatting | Replaces black + isort + flake8. Single tool, fast. |
| pytest | Testing | Standard Python test framework. |
| pre-commit | Git hooks | Run ruff, type checks on commit. |
| pyright / mypy | Type checking | Type safety for pipeline code. Use pyright (faster). |

## Installation

```bash
# Create project with uv
uv init engrave
cd engrave

# Core framework
uv add fastapi[standard] pydantic uvicorn[standard]

# ML framework
uv add torch torchvision torchaudio

# Source separation (Stage 1)
uv add demucs-infer

# MIDI transcription (Stage 2)
uv add basic-pitch

# Audio processing
uv add librosa mido pretty_midi

# Audio LM (Stage 3) - Qwen2-Audio via transformers
uv add transformers accelerate

# Multi-provider LLM (Stage 4)
uv add litellm openai anthropic

# RAG
uv add llama-index llama-index-vector-stores-chroma chromadb

# LilyPond Python tools
uv add python-ly abjad

# Media input
uv add yt-dlp

# Evaluation
uv add music21

# Dev tools
uv add --dev ruff pytest pyright pre-commit

# System dependencies (Homebrew)
brew install lilypond ffmpeg

# LM Studio - download from https://lmstudio.ai/
# Then via CLI:
# lms get qwen3-coder-next
# lms get gpt-oss-120b
# lms get qwen2-audio-7b
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| demucs-infer | demucs (original) | Never. Original package abandoned, stuck on PyTorch 1.x. |
| Basic Pitch (primary) | MT3 (secondary) | When transcribing pre-mixed multi-instrument audio without prior separation. MT3 handles polyphony better but needs JAX. |
| LiteLLM | Direct SDK per provider | If LiteLLM introduces latency issues or doesn't support a needed feature. Unlikely. |
| LlamaIndex | LangChain | If pipeline needs complex multi-step agent orchestration beyond RAG retrieval. Not needed for v1. |
| ChromaDB | Qdrant / Weaviate | If vector corpus exceeds 1M documents. Won't happen for our use case. |
| Qwen3-Coder-Next | gpt-oss-120b | If benchmarks show gpt-oss generates better LilyPond. gpt-oss-120b uses more RAM and is slower on M4 Max. |
| python-ly | Abjad-only | If you need programmatic score construction from scratch. For our use case (LLM generates LilyPond, we validate), python-ly is lighter. |
| uv | pip + venv | Never. uv is strictly better (10-100x faster, built-in venv, lockfile). |
| Qwen2-Audio-7B | Qwen2.5-Omni-7B | When Qwen2.5-Omni proves better at music description in benchmarks. Evaluate both. |
| Gemini 2.5 Flash | Gemini 2.0 Flash | Never. 2.0 Flash retires June 2026. Use 2.5 Flash for cloud audio understanding. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| demucs (original PyPI package) | Abandoned Sept 2023. Incompatible with PyTorch 2.x and Python 3.12. | demucs-infer 4.1.2 |
| LangChain for RAG | Over-abstracted for focused retrieval. LlamaIndex has 35% better retrieval accuracy. | LlamaIndex |
| Gemini 2.0 Flash | Retires June 2026. | Gemini 2.5 Flash |
| pip + venv | Slow, no lockfile, no resolver. | uv |
| black + isort + flake8 | Three tools doing what one does. | ruff |
| MuseScore / Finale for rendering | GUI-based, not scriptable, not LLM-friendly. | LilyPond (text-based, subprocess) |
| TensorFlow/JAX as primary | Pipeline is PyTorch-centric (Demucs, transformers). Adding JAX fragments the stack. | PyTorch + MPS |
| Ollama for local inference | LMStudio has better MLX integration, GGUF support, and GUI for model management. Matt already uses LMStudio. | LM Studio |
| htdemucs_6s model | Piano stem quality is poor ("not working great"). | htdemucs_ft (4-stem, fine-tuned) |

## Stack Patterns by Variant

**If audio input (MP3/WAV/YouTube):**
- Full pipeline: yt-dlp (if YouTube) -> ffmpeg -> Demucs -> Basic Pitch -> Audio LM -> LLM -> LilyPond
- All stages active

**If MIDI input:**
- Skip Stages 1-2 (no separation or transcription needed)
- Pipeline: MIDI parse (mido) -> Audio LM (optional, for musical context) -> LLM -> LilyPond
- Much faster path

**If prototyping/iterating on LilyPond generation:**
- Use gpt-oss-20b locally (fast, 16GB) for rapid iteration
- Switch to Qwen3-Coder-Next for quality evaluation
- Benchmark against Claude/GPT-4 cloud APIs for ceiling

**If running full pipeline concurrently:**
- M4 Max 128GB budget: Demucs (~4GB) + Basic Pitch (~0.5GB) + Qwen2-Audio-7B (~14GB) + Qwen3-Coder-Next-4bit (~46GB) = ~65GB
- Leaves ~60GB for OS + ChromaDB + LilyPond rendering
- Feasible but avoid running all models simultaneously; pipeline is sequential anyway

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PyTorch 2.10.0 | Python 3.10-3.12 | MPS backend for Apple Silicon. Avoid Python 3.13+ until torch fully supports it. |
| demucs-infer 4.1.2 | PyTorch 2.x, Python 3.8-3.12 | Specifically built for modern PyTorch. |
| basic-pitch 0.4.0 | Python 3.8-3.11 | **WARNING: officially only supports up to Python 3.11.** May work on 3.12 but untested. Mac M1 note: "only support python 3.10." Test on 3.12 early; fall back to 3.11 venv if needed. |
| FastAPI 0.132.0 | Python >=3.10, Pydantic v2 | `fastapi-slim` dropped; use `fastapi[standard]` only. |
| Abjad 3.31 | LilyPond 2.25.26+, Python 3.12+ | Requires LilyPond *dev* branch. Install alongside stable for rendering. |
| LlamaIndex 0.14.15 | Python >=3.9 | Modular packages; install integration packages separately. |
| ChromaDB 1.5.1 | Python 3.9+ | Default embeddings use Sentence Transformers. |
| LM Studio 0.4.x | macOS (Apple Silicon) | MLX engine for Apple Silicon. OpenAI-compatible API. |
| Qwen3-Coder-Next 4-bit | >46GB unified memory | M4 Max 128GB has ample headroom. 100+ tok/s expected. |
| gpt-oss-120b 4-bit | ~63GB RAM/VRAM | Fits in 128GB but tight with other models. Slower than Qwen3-Coder-Next. |

## Critical Compatibility Warning

**basic-pitch and Python 3.12:** The basic-pitch package officially supports Python 3.8-3.11 only, with a specific note that Mac M1 (Apple Silicon) only supports Python 3.10. This is the most likely version conflict in the stack. Mitigation options:
1. Test basic-pitch on Python 3.12 early -- it may work despite official support claims
2. If it fails, run basic-pitch in a separate Python 3.10 venv, called as subprocess
3. Watch for a newer release that adds 3.12 support
4. Consider contributing a 3.12 compatibility fix upstream

**MT3 and JAX:** MT3 requires T5X which requires JAX. JAX and PyTorch in the same environment can cause CUDA/Metal conflicts. If using MT3, run it in an isolated environment (separate venv or container).

## Apple Silicon (M4 Max 128GB) Optimization Notes

- **PyTorch MPS:** Use `device = "mps"` for GPU acceleration. Not all ops supported; pipeline should gracefully fall back to CPU for unsupported ops.
- **MLX via LM Studio:** LM Studio's MLX engine is 20-30% faster than llama.cpp for Apple Silicon. Prefer MLX format models when available.
- **Unified memory:** Models share memory with OS. Budget 10-15GB for macOS + apps. Effective ML memory: ~113GB.
- **Thermal throttling:** M4 Max will throttle under sustained load. Pipeline is sequential (not concurrent model inference), which helps thermal management.
- **Memory allocation order:** Load models in pipeline order, unload when stage completes. Don't keep all models resident simultaneously.

## Sources

- [demucs-infer PyPI](https://pypi.org/project/demucs-infer/) -- Version 4.1.2, Jan 2026 (HIGH confidence)
- [demucs PyPI](https://pypi.org/project/demucs/) -- Version 4.0.1, Sept 2023, abandoned (HIGH confidence)
- [Basic Pitch GitHub](https://github.com/spotify/basic-pitch) -- Version 0.4.0, Aug 2024 (HIGH confidence)
- [MT3 GitHub](https://github.com/magenta/mt3) -- Research code, not pip-installable (HIGH confidence)
- [Qwen2-Audio HuggingFace](https://huggingface.co/Qwen/Qwen2-Audio-7B-Instruct) -- 7B model (MEDIUM confidence)
- [Qwen2.5-Omni GitHub](https://github.com/QwenLM/Qwen2.5-Omni) -- 7B model (MEDIUM confidence)
- [LFM2.5-Audio HuggingFace](https://huggingface.co/LiquidAI/LFM2.5-Audio-1.5B) -- 1.5B model (MEDIUM confidence)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) -- $1.00/M audio tokens (HIGH confidence)
- [Gemini Audio Docs](https://ai.google.dev/gemini-api/docs/audio) -- Audio understanding API (HIGH confidence)
- [Qwen3-Coder-Next HuggingFace](https://huggingface.co/Qwen/Qwen3-Coder-Next) -- 80B MoE, 3B active (HIGH confidence)
- [Qwen3-Coder-Next LMStudio](https://lmstudio.ai/models/qwen3-coder-next) -- 46GB for 4-bit, 100+ tok/s M4 Max (MEDIUM confidence)
- [gpt-oss-120b HuggingFace](https://huggingface.co/openai/gpt-oss-120b) -- 120B MoE, 5.1B active, Apache 2.0 (HIGH confidence)
- [gpt-oss-120b model card](https://openai.com/index/gpt-oss-model-card/) -- Released Aug 2025 (HIGH confidence)
- [LMStudio Docs](https://lmstudio.ai/docs/app) -- Version 0.4.x, MLX engine (HIGH confidence)
- [LMStudio OpenAI Compat](https://lmstudio.ai/docs/developer/openai-compat) -- Drop-in OpenAI replacement (HIGH confidence)
- [LiteLLM Docs](https://docs.litellm.ai/docs/) -- 100+ providers, OpenAI format (HIGH confidence)
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- Version 0.132.0, Feb 2026 (HIGH confidence)
- [LlamaIndex PyPI](https://pypi.org/project/llama-index/) -- Version 0.14.15, Feb 2026 (HIGH confidence)
- [ChromaDB PyPI](https://pypi.org/project/chromadb/) -- Version 1.5.1, Feb 2026 (HIGH confidence)
- [LilyPond Download](https://lilypond.org/download.html) -- Stable 2.24.4, Dev 2.25.34 (HIGH confidence)
- [Abjad PyPI](https://pypi.org/project/abjad/) -- Version 3.31 (HIGH confidence)
- [python-ly Docs](https://python-ly.readthedocs.io/en/latest/) -- Version 0.9.5 (HIGH confidence)
- [Audiveris GitHub](https://github.com/Audiveris/audiveris) -- OMR to MusicXML (MEDIUM confidence)
- [PyTorch PyPI](https://pypi.org/project/torch/) -- Version 2.10.0, Jan 2026 (HIGH confidence)
- [OpenAI SDK PyPI](https://pypi.org/project/openai/) -- Version 2.23.0, Feb 2026 (HIGH confidence)
- [Anthropic SDK PyPI](https://pypi.org/project/anthropic/) -- Version 0.83.0, Feb 2026 (HIGH confidence)
- [Pydantic PyPI](https://pypi.org/project/pydantic/) -- Version 2.12.5 (HIGH confidence)
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp) -- Version 2026.02.x (HIGH confidence)

---
*Stack research for: AI-powered audio-to-sheet-music engraving pipeline*
*Researched: 2026-02-24*
