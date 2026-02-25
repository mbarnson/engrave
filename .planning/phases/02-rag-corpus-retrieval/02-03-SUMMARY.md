---
phase: 02-rag-corpus-retrieval
plan: 03
subsystem: corpus
tags: [ingestion, mutopia, pdmx, musicxml, midi, lilypond, pipeline, chromadb]

# Dependency graph
requires:
  - phase: 01-project-scaffolding-inference-router
    provides: LilyPondCompiler, compile_with_fix_loop, InferenceRouter
  - phase: 02-rag-corpus-retrieval/01
    provides: CorpusStore, Chunk/ScoreMetadata models, ChromaDB wrapper
  - phase: 02-rag-corpus-retrieval/02
    provides: chunk_score, extract_metadata, generate_description
provides:
  - Shared ingestion pipeline (ingest_score) orchestrating compile -> chunk -> metadata -> index
  - Mutopia adapter (discover_mutopia_scores, extract_mutopia_header, map_mutopia_to_metadata)
  - PDMX adapter (discover_pdmx_scores, convert_musicxml_to_ly, ingest_pdmx_corpus)
  - MIDI block injection (ensure_midi_block) for scores missing \midi {}
  - Instrument family classification lookup table
  - Quality filtering for degenerate cases (empty scores, single-note files)
affects: [02-04-retrieval-interface, 03-lilypond-generation]

# Tech tracking
tech-stack:
  added: []
  patterns: [ingestion pipeline orchestration, source-specific adapters with shared core, MIDI block injection via brace counting, Mutopia header regex extraction, musicxml2ly subprocess wrapper]

key-files:
  created:
    - src/engrave/corpus/ingest/__init__.py
    - src/engrave/corpus/ingest/pipeline.py
    - src/engrave/corpus/ingest/mutopia.py
    - src/engrave/corpus/ingest/pdmx.py
    - src/engrave/corpus/ingest/midi_injection.py
    - tests/unit/test_midi_injection.py
    - tests/unit/test_mutopia_header.py
    - tests/integration/test_mutopia_ingest.py
    - tests/integration/test_pdmx_ingest.py
    - tests/fixtures/corpus/mutopia_bach.ly
    - tests/fixtures/musicxml/simple_score.musicxml
  modified:
    - tests/conftest.py

key-decisions:
  - "MIDI compiled from our own LilyPond source (not pre-existing archive MIDI) via ensure_midi_block injection"
  - "Degenerate case filtering: <10 chars or <2 notes skipped before compilation"
  - "PDMX originals stored alongside converted LilyPond for provenance and re-conversion"
  - "Instrument family classification via case-insensitive lookup table (70+ instruments mapped)"
  - "Era inference from Mutopia style field or date-based ranges (pre-1600 Renaissance through 1900+ Modern)"

patterns-established:
  - "Source adapter pattern: each corpus source (Mutopia, PDMX) has its own discovery/conversion module that feeds into the shared ingest_score() pipeline"
  - "MIDI injection via brace counting: find \\layout or \\score closing brace, insert \\midi { } at the right position"
  - "Mock compiler fixture: writes fake .pdf and .midi files to simulate LilyPond output without requiring the binary"
  - "ChromaDB isolation in integration tests: unique collection names per test via request.node.name"

requirements-completed: [CORP-01, CORP-02]

# Metrics
duration: 7min
completed: 2026-02-25
---

# Phase 2 Plan 03: Ingestion Pipeline Summary

**Mutopia and PDMX ingestion pipeline with MIDI injection, compile-fix loop integration, music-aware chunking, metadata extraction, and ChromaDB indexing producing (LilyPond, MIDI, description) triples**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-25T00:23:16Z
- **Completed:** 2026-02-25T00:29:43Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Shared `ingest_score()` pipeline orchestrates the full flow: quality filter -> MIDI injection -> compilation (with fix loop) -> chunking -> metadata extraction -> description generation -> ChromaDB indexing
- Mutopia adapter discovers `.ly` files, extracts Mutopia-specific header fields (mutopiatitle, mutopiacomposer, etc.), and maps them to ScoreMetadata with instrument family classification
- PDMX adapter discovers MusicXML files, converts via `musicxml2ly`, stores originals alongside, and feeds into the shared pipeline
- `ensure_midi_block()` injects `\midi { }` into scores that lack it, using brace counting to find the correct insertion point
- MIDI feature extraction (velocity histogram, pitch range, rhythmic complexity) when mido is available
- 34 new tests (22 unit + 12 integration) all passing, 156 total suite tests with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: MIDI injection, Mutopia header parsing, and shared ingestion pipeline** - `b075e4c` (feat)
2. **Task 2: PDMX adapter and integration tests for both sources** - `de539ee` (feat)

## Files Created/Modified
- `src/engrave/corpus/ingest/__init__.py` - Package init re-exporting all public functions
- `src/engrave/corpus/ingest/pipeline.py` - Shared ingestion pipeline: ingest_score(), ingest_mutopia_corpus(), IngestionResult dataclass
- `src/engrave/corpus/ingest/mutopia.py` - Mutopia adapter: header parsing, metadata mapping, file discovery, instrument family classification
- `src/engrave/corpus/ingest/pdmx.py` - PDMX adapter: MusicXML discovery, musicxml2ly conversion, original storage, corpus ingestion
- `src/engrave/corpus/ingest/midi_injection.py` - ensure_midi_block() for injecting \midi {} into LilyPond scores
- `tests/unit/test_midi_injection.py` - 6 tests for MIDI block injection (existing, after layout, no layout, no score, complex layout, midi with content)
- `tests/unit/test_mutopia_header.py` - 16 tests for header extraction and metadata mapping (all fields, missing, multiline, instrument families, era inference)
- `tests/integration/test_mutopia_ingest.py` - 5 integration tests for Mutopia pipeline (chunks indexed, source_collection, descriptions, MIDI injection, corpus discovery)
- `tests/integration/test_pdmx_ingest.py` - 7 integration tests for PDMX pipeline (discovery, conversion, failure handling, original storage, corpus indexing)
- `tests/fixtures/corpus/mutopia_bach.ly` - 16-bar Bach Invention fixture with Mutopia header, no \midi (tests injection)
- `tests/fixtures/musicxml/simple_score.musicxml` - 4-bar MusicXML piano score for PDMX testing
- `tests/conftest.py` - Added mock_lilypond_compiler and sample_mutopia_score fixtures

## Decisions Made
- **MIDI from our own compilation:** Scores compiled from our LilyPond source produce MIDI, not pre-existing archive MIDI. This ensures consistency between the indexed LilyPond and its MIDI representation.
- **Degenerate case filtering:** Sources under 10 characters or with fewer than 2 notes are skipped before compilation. This prevents wasting compilation time on empty files, headers-only files, or single-note test stubs.
- **PDMX originals stored alongside:** The original MusicXML file is copied to a `_originals` directory next to the converted LilyPond, preserving provenance and enabling re-conversion if musicxml2ly improves.
- **Instrument family classification:** A 70+ instrument lookup table maps instrument names to families (keyboard, strings, woodwind, brass, percussion, vocal, other). Supports partial matching for compound names like "Bb Clarinet".
- **Era inference:** Musical era is inferred from Mutopia style field first (Baroque, Classical, Romantic, Modern), then from date ranges if style is not available.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all tasks completed without issues.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ingestion pipeline ready for Plan 04 to build the retrieval API on top
- Both Mutopia and PDMX sources can populate the corpus collection via CLI commands
- CorpusStore verified end-to-end with real chunk indexing and metadata-filtered retrieval
- Compile-fix loop integration tested (mocked) for error recovery path
- All 156 tests passing, no regressions from Plans 01 and 02

## Self-Check: PASSED

- All 11 created files verified present on disk
- Both task commits (b075e4c, de539ee) verified in git log
- 156/156 suite tests passing
- ruff check clean on all 5 source modules

---
*Phase: 02-rag-corpus-retrieval*
*Completed: 2026-02-25*
