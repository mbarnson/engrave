# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** When Sam uploads a recording and describes his ensemble, his players can sight-read the extracted parts at rehearsal and the brass section sounds like a section.
**Current focus:** Phase 3: LilyPond Code Generation

## Current Position

Phase: 3 of 9 (LilyPond Code Generation)
Plan: 1 of ? in current phase
Status: Ready
Last activity: 2026-02-25 -- Completed 02-04-PLAN.md (retrieval interface: public API + CLI)

Progress: [###.......] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 6.3 min
- Total execution time: 0.6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 12 min | 6 min |
| 2 | 4 | 27 min | 7 min |

**Recent Trend:**
- Last 5 plans: 01-02 (6 min), 02-02 (7 min), 02-01 (9 min), 02-03 (7 min), 02-04 (4 min)
- Trend: Consistent

*Updated after each plan completion*

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
- [Phase quick]: SDR benchmarks measure remix fidelity, NOT transcription accuracy — wrong metric for Engrave. Post-Phase 5 spike: run separation→transcription→MIDI comparison against ground truth charts to find best separator *for engraving*. Needs Sam's tracks (not yet available). No mandatory human review gates before Phase 7 demo.

### Pending Todos

None yet.

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
Stopped at: Completed 02-04-PLAN.md -- retrieval interface (Phase 2 complete)
Resume file: .planning/phases/02-rag-corpus-retrieval/02-04-SUMMARY.md
