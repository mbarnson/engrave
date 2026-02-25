# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** When Sam uploads a recording and describes his ensemble, his players can sight-read the extracted parts at rehearsal and the brass section sounds like a section.
**Current focus:** Phase 05.1 in progress -- Promote ADVN-01 into v1 scope for Dorico

## Current Position

Phase: 05.1 of 9 (Promote ADVN-01 into v1 scope for Dorico)
Plan: 2 of 4 in current phase
Status: Plan 02 complete. Continuing with Plan 03.
Last activity: 2026-02-25 -- Completed 05.1-02-PLAN.md (Parallel LilyPond + JSON fan-out)

Progress: [######....] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: 5.5 min
- Total execution time: 1.7 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 12 min | 6 min |
| 2 | 4 | 27 min | 7 min |
| 3 | 3 | 22 min | 7 min |
| 4 | 3 | 13 min | 4 min |
| 5 | 4 | 19 min | 5 min |

**Recent Trend:**
- Last 5 plans: 04-02 (5 min), 04-03 (5 min), 05-02 (4 min), 05-04 (6 min), 05-05 (5 min)
- Trend: Consistent

*Updated after each plan completion*
| Phase 05 P01 | 4 min | 1 task | 4 files |
| Phase 05 P02 | 4 min | 1 task | 4 files |
| Phase 05 P03 | 4 min | 1 task | 2 files |
| Phase 05 P04 | 6 min | 2 tasks | 4 files |
| Phase 05 P05 | 5 min | 2 tasks | 7 files |
| Phase 05 P06 | 8 min | 2 tasks | 10 files |
| Phase 05.1 P02 | 4 min | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: MIDI-first strategy -- prove code generation with clean MIDI input before adding audio complexity
- Roadmap: 9 phases derived from natural pipeline component boundaries at comprehensive depth
- Roadmap: Convergent sight-reading (Phase 7) deferred until rendering and audio understanding are stable
- 01-01: hatchling build backend for src layout support with uv
- 01-01: pydantic-settings v2 requires settings_customise_sources for TOML (not just model_config)
- 01-01: TestSettings subclass pattern for TOML path isolation in tests
- 01-01: typer (not typer[all]) -- the [all] extra removed in v0.24.x
- 01-02: Error context window: ~20 lines centered on error, full source also in prompt for complete return
- 01-02: extract_lilypond_from_response handles markdown code blocks, generic code blocks, and plain text
- 01-02: Repeated error hash detection after first occurrence triggers early loop exit
- 02-02: 1-bar overlap between adjacent chunks for pickup/cadential continuity
- 02-02: Repeats expanded (unrolled) before chunking -- linear chunks match performer reading order
- 02-02: 8-bar fallback chunking when no structural boundaries detected
- 02-02: Deterministic regex metadata extraction -- no LLM involvement per user decision
- 02-02: python-ly 0.9.9 works on Python 3.13 despite PyPI listing 3.8-3.11
- 02-01: ChromaDB Rust bindings reject None metadata values -- filter before add()
- 02-01: chromadb.Client() is process-wide singleton -- unique collection names per test
- 02-01: nomic-embed-text as default embedding model (configurable via engrave.toml)
- 02-03: MIDI compiled from our own LilyPond source (not pre-existing archive MIDI) via ensure_midi_block injection
- 02-03: Degenerate case filtering: <10 chars or <2 notes skipped before compilation
- 02-03: PDMX originals stored alongside converted LilyPond for provenance
- 02-03: Instrument family classification via case-insensitive lookup table (70+ instruments)
- 02-03: Era inference from Mutopia style field or date-based ranges
- 02-04: retrieve() convenience wrapper with lazy store creation and optional store injection for testing/batch
- 02-04: Public API exports both retrieval and ingestion from engrave.corpus package
- 02-04: CLI corpus ingest is placeholder -- full CLI ingestion deferred until needed
- [Phase quick]: audio-separator replaces demucs-infer as primary source separation package; per-stem model routing strategy documented
- 03-01: NoteEvent velocity from note_on (not note_off) for accurate dynamics
- 03-01: Krumhansl-Kessler profiles for key estimation via chroma correlation
- 03-01: Sharps-only pitch naming (no enharmonic context yet); LilyPond absolute octave: c = MIDI 48-59
- 03-01: Velocity-to-dynamic mapping with hysteresis (>8 velocity change threshold)
- 03-01: Section boundary dedup by bar number, highest priority wins
- 03-01: Programmatic MIDI fixture generation for deterministic tests
- 03-02: CoherenceState carries 12 musical context fields; summary capped at 1200 chars with simple oldest-content truncation
- 03-02: Prompt budget 32K total with RAG-first truncation priority (RAG > coherence > MIDI)
- 03-02: Variable-per-instrument LilyPond templates: LLM fills music content, never generates score structure
- 03-02: Failure records stored as individual JSON files with timestamp-based filenames for TUNE-02
- 03-03: Pipeline uses async throughout; section failure halts entire generation (no partial output)
- 03-03: Assembler concatenates per-instrument music across sections into continuous variables
- 03-03: RAG retriever optional callable (query, limit) -> list[str]; graceful fallback to empty
- 03-03: Analysis proxy bridges MidiAnalysis (lists) to CoherenceState (scalar fields)
- 03-03: Mock generator router dynamically parses template variables from prompt for realistic test responses
- 03-03: CLI engrave generate with --output, --labels, --no-rag, --role options
- [Phase quick]: SDR benchmarks measure remix fidelity, NOT transcription accuracy — wrong metric for Engrave. Post-Phase 5 spike: run separation→transcription→MIDI comparison against ground truth charts to find best separator *for engraving*. Needs Sam's tracks (not yet available). No mandatory human review gates before Phase 7 demo.
- 04-01: Piano is a single InstrumentSpec with is_grand_staff=True; generator handles PianoStaff context
- 04-01: Baritone sax transpose_to='a' (A below middle C), octave lower than alto's 'a''
- 04-01: Staff size 14 for conductor score via layout-set-staff-size inside layout block
- 04-01: Header constants use Python format strings ({title}, {composer}) not Jinja templates
- 04-02: restate_dynamics uses token-walking regex (not full LilyPond parser) for dynamic/rest pattern recognition
- 04-02: Piano PianoStaff splits into upper/lower staves with separate variable refs (piano, pianoLeft)
- 04-02: Non-transposing instruments omit \transpose wrapper entirely (no no-op \transpose c' c')
- 04-02: Conductor score concert pitch throughout with no \transpose commands
- 04-03: python-slugify for Unicode-safe song title slugification (instrument names are ASCII-only)
- 04-03: RenderPipeline sets compiler.timeout before score (300s) vs part (60s) compilation
- 04-03: Partial compilation: .ly source files always included in ZIP even for failed parts
- 04-03: CLI render command uses regex variable extraction from music-definitions.ly as placeholder
- 05-01: pydub for format detection/conversion via AudioSegment.from_file() -- lightweight wrapper around ffmpeg
- 05-01: stdlib wave module for test fixture creation -- no pydub dependency in test setup
- 05-01: SeparationConfig.default_steps() class method returns big band cascade (htdemucs_ft + bs_roformer)
- 05-02: yt-dlp Python API with context manager (not subprocess CLI) for YouTube extraction
- 05-02: Video ID-based output filenames (not title) for deterministic pipeline runs
- 05-02: FFmpegExtractAudio postprocessor with preferredcodec=wav
- 05-04: TranscriptionConfig dataclass local to transcriber.py (not yet in settings.py) -- integrate when audio pipeline config is complete
- 05-04: Quality metrics are informational metadata for LLM, not binary pass/fail gates ("LLM IS the fallback")
- 05-04: Onset cluster threshold 10ms matching neural transcription temporal resolution
- 05-04: Drum tracks excluded from quality analysis (pitched content only)
- 05-05: Pipeline stages run sequentially (not async) -- simplifies error handling and job directory state
- 05-05: Transcriber injected into AudioPipeline constructor for testability
- 05-05: Config SeparationStep (Pydantic) converted to separator.SeparationStep (frozen dataclass) at pipeline boundary
- 05-05: jobs/ gitignored to prevent large WAV intermediates from being committed
- 05-06: PipelineProtocol decouples harness from concrete AudioPipeline for independent testing
- 05-06: mir_eval used directly in evaluator tests (pure Python, safe for unit tests)
- 05-06: Per-stem comparison against full reference MIDI -- precision meaningful, recall expected low per-stem
- 05-06: BenchmarkConfig as local dataclass separate from settings.py pydantic model
- 05.1-02: JSON extraction three-stage fallback: json.loads array, json.loads object wrapped, regex individual objects -- never raises
- 05.1-02: _request_json_notation isolated coroutine so JSON failure cannot affect LilyPond generation
- 05.1-02: asyncio.gather with NotImplementedError fallback to sequential for non-async routers
- 05.1-02: Training pairs saved as section_{N}.json with ly_source and json_notation fields

### Roadmap Evolution

- Phase 05.1 inserted after Phase 5: Promote ADVN-01 into v1 scope for Dorico (URGENT)

### Pending Todos

1. Standalone LilyPond-to-MusicXML converter via fine-tuned Qwen3-4B (v2 scope, data collection in Phase 05.1)

### Blockers/Concerns

- basic-pitch HARD CONSTRAINT: requires Python 3.10 isolated venv on Apple Silicon (official support 3.8-3.11 only, frozen since Aug 2024). Phase 5 must implement subprocess invocation or venv isolation to run basic-pitch alongside the Python 3.12 project.
- LilyPond LLM generation quality ceiling unknown -- benchmark models early in Phase 3
- RAG corpus is mostly classical (Mutopia); big band jazz coverage is sparse until Sam's charts are added (v1.1)

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Update planning docs to replace demucs with audio-separator/RoFormer SOTA stem-splitting models | 2026-02-25 | c39562e | [1-update-planning-docs-to-replace-demucs-w](./quick/1-update-planning-docs-to-replace-demucs-w/) |

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 05.1-02-PLAN.md (Parallel LilyPond + JSON fan-out)
Resume file: .planning/phases/05.1-promote-advn-01-into-v1-scope-for-dorico/05.1-03-PLAN.md
