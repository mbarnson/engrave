<p align="center">
  <img src="logo.png" alt="Engrave logo" width="128">
</p>

# Engrave

MIDI to publication-quality sheet music. An LLM generates LilyPond notation,
a compile-fix loop corrects errors, and LilyPond produces the final PDF.

Engrave handles transposition, part extraction, and score assembly for
jazz ensembles. The built-in big band preset covers 17 instruments across
saxophones, trumpets, trombones, and rhythm section.

## How it works

Engrave runs a multi-stage pipeline:

1. **Input** -- MIDI file, audio recording (MP3/WAV/FLAC/AIFF), or YouTube URL.
2. **Audio processing** (if audio/YouTube input) -- Normalize, separate stems,
   transcribe each stem to MIDI.
3. **MIDI analysis** -- Load tracks, detect section boundaries, tokenize for
   the LLM prompt.
4. **LilyPond generation** -- An LLM produces LilyPond source for each
   section and instrument. A retrieval-augmented generation (RAG) corpus
   provides few-shot examples from real scores.
5. **Compile-fix loop** -- LilyPond compiles the source. If it fails, the LLM
   reads the error output and rewrites the broken passage. Up to 5 attempts.
6. **Assembly** -- Sections are joined into a complete score with proper
   transposition, key/time signatures, rehearsal marks, and dynamics.
7. **Rendering** -- LilyPond compiles the final score PDF, individual part
   PDFs, and MIDI output. Everything is packaged into a ZIP archive.

## Install

### Desktop app (macOS / Windows)

Download the latest release from the
[GitHub Releases](../../releases) page. The desktop app is built with
Tauri and bundles the Python pipeline.

### CLI (developers)

Requires Python 3.12+ and [LilyPond](https://lilypond.org/) 2.24+.

```
# Clone and install
git clone <repo-url>
cd engrave
make setup
```

This runs `uv sync` to install Python dependencies and `pre-commit install`
to set up hooks.

LilyPond install:

- macOS: `brew install lilypond`
- Debian/Ubuntu: `sudo apt-get install lilypond`
- Alpine: `apk add lilypond`
- Windows: download from [lilypond.org](https://lilypond.org/download.html)

## Auth

Engrave uses an LLM for notation generation and error fixing. You need
access to at least one inference provider.

### Claude (desktop app users)

Enter your Anthropic API key in the desktop app settings. The key is stored
securely in your OS keychain (macOS Keychain, Windows Credential Manager,
or Linux Secret Service). Get a key at https://console.anthropic.com/settings/keys

### API keys (CLI users)

Copy `.env.example` to `.env` and fill in your keys:

```
cp .env.example .env
```

Supported providers:

| Provider | Env variable | Notes |
|----------|-------------|-------|
| Anthropic | `ENGRAVE_PROVIDERS__ANTHROPIC_API_KEY` | Claude models |
| OpenAI | `ENGRAVE_PROVIDERS__OPENAI_API_KEY` | GPT models |
| RunPod | `ENGRAVE_PROVIDERS__RUNPOD__API_KEY` | Self-hosted vLLM |
| LM Studio | (none -- local) | Local models at localhost:1234 |

Provider routing and model selection are configured in `engrave.toml`.
Each LLM role (generator, compile_fixer, describer) maps to a specific
provider and model.

## CLI usage

```
engrave generate song.mid                  # MIDI to LilyPond
engrave generate song.mid -o output.ly     # Custom output path
engrave generate song.mid --no-rag         # Skip RAG retrieval
engrave generate song.mid --hints "swing feel, key of Bb"
engrave compile output.ly                  # Compile .ly to PDF
engrave compile output.ly --no-fix         # Compile without LLM fixing
engrave render ./output-dir                # Render parts + score to ZIP
engrave render ./output-dir --title "Birdland"
engrave process-audio recording.mp3        # Full audio pipeline
engrave process-audio "https://youtube.com/watch?v=..."  # YouTube URL
engrave check all                          # Test all LLM connections
engrave version                            # Print version
```

### Corpus commands

Engrave uses a vector database of LilyPond snippets for RAG retrieval:

```
engrave corpus query "jazz ballad for alto sax"
engrave corpus stats
```

### Benchmark

Evaluate pipeline accuracy against reference MIDI files:

```
engrave benchmark run reference.mid
engrave benchmark compare result1.json result2.json
```

### Smoke tests

Run structural checks on audio/MIDI inputs:

```
engrave smoke-test ./test-inputs/
engrave smoke-test ./test-inputs/ --json results.json
```

### Web UI

A minimal web interface for testing:

```
engrave serve                    # http://127.0.0.1:8000
engrave serve --port 3000
```

## Supported instruments

The built-in big band preset includes:

**Saxophones** -- Alto Sax 1-2, Tenor Sax 1-2, Baritone Sax

**Trumpets** -- Trumpet 1-4

**Trombones** -- Trombone 1-3, Bass Trombone

**Rhythm** -- Piano, Guitar, Bass, Drums

All transposing instruments are stored in concert pitch internally.
Transposition to written pitch happens at render time. The conductor
score shows all instruments; individual parts are extracted with proper
transposition and chord symbols where applicable.

## Architecture

```
src/engrave/
  audio/         Audio processing: normalize, separate, transcribe, YouTube
  benchmark/     Accuracy evaluation harness
  cli.py         Typer CLI entry point
  config/        Settings via pydantic-settings + engrave.toml
  corpus/        ChromaDB vector store for RAG retrieval
  generation/    LLM prompt building, section-group dispatch, assembly
  hints/         User hint loading (inline text or .hints files)
  lilypond/      Compiler wrapper, error parser, fix loop
  llm/           Inference router with multi-provider support
  midi/          MIDI loading, analysis, section detection, tokenization
  musicxml/      MusicXML export
  rendering/     Ensemble presets, part rendering, score packaging
  smoke/         Structural smoke test runner
  web/           FastAPI web UI
desktop/
  src-tauri/     Tauri desktop app (Rust backend)
  src/           Frontend
```

### Pipeline stages in detail

**Audio processing**: Normalizes input audio, runs stem separation
(audio-separator), transcribes each stem to MIDI (basic-pitch or
similar), and annotates quality metrics (pitch range violations, note
count).

**Generation**: The MIDI analyzer detects section boundaries. For each
section, instruments sharing a section group (e.g. all 4 trumpets) are
generated by a single LLM call. This reduces a 17-instrument big band
from 17 calls to 7 per section (3 section groups + 4 rhythm instruments).

**Compile-fix loop**: Each generated snippet is compiled through LilyPond.
On failure, the error output and surrounding context are sent back to
the LLM for correction. The loop runs up to 5 iterations.

**Rendering**: The packager compiles a conductor score, extracts individual
parts with transposition, generates MIDI, and optionally exports MusicXML.
Everything goes into a ZIP.

### LLM roles

| Role | Purpose | Default model |
|------|---------|---------------|
| generator | LilyPond notation from MIDI | Qwen3-Coder-30B (local) |
| compile_fixer | Fix LilyPond compilation errors | Qwen3-Coder-30B (local) |
| describer | Audio description for context | Claude Opus |

Roles are configured in `engrave.toml` under `[roles.*]`. Each role maps
to a provider, model, and token limit.

## Configuration

Runtime configuration lives in `engrave.toml`. API keys go in `.env`
(gitignored). Settings follow the pydantic-settings convention with the
`ENGRAVE_` prefix and `__` nested delimiter for environment variables.

Key sections:

- `[providers.*]` -- API base URLs and default models
- `[roles.*]` -- LLM role assignments (model, max_tokens, tags)
- `[lilypond]` -- Compiler timeout, max fix attempts, context window
- `[pipeline]` -- Concurrency limits
- `[corpus]` -- Embedding model, DB path, collection name

See `engrave.toml.example` for a complete reference.

## Development

```
make setup       # Install deps + pre-commit hooks
make test        # Run tests with coverage
make lint        # Check with ruff
make format      # Auto-fix with ruff
```

Tests use pytest with pytest-bdd for behavior specs and pytest-asyncio
for async pipeline tests.

## License

MIT
