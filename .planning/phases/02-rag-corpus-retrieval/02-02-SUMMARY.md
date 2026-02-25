---
phase: 02-rag-corpus-retrieval
plan: 02
subsystem: corpus
tags: [lilypond, chunking, regex, metadata, parsing, python-ly]

# Dependency graph
requires:
  - phase: 01-project-scaffolding-inference-router
    provides: project structure, pytest/ruff tooling, pyproject.toml
provides:
  - Music-aware LilyPond phrase chunking (chunk_score, find_phrase_boundaries, expand_repeats)
  - Metadata extraction from LilyPond source (extract_metadata)
  - Structured text description templating (generate_description)
  - LilyPond test fixtures (simple, multi-part, repeat scores)
affects: [02-03-ingestion-pipeline, 02-04-retrieval-interface, 03-lilypond-generation]

# Tech tracking
tech-stack:
  added: [python-ly]
  patterns: [regex boundary detection, repeat unrolling, bar-count fallback chunking, deterministic metadata extraction]

key-files:
  created:
    - src/engrave/corpus/chunker.py
    - src/engrave/corpus/metadata.py
    - src/engrave/corpus/description.py
    - tests/unit/test_chunker.py
    - tests/unit/test_boundaries.py
    - tests/unit/test_metadata.py
    - tests/unit/test_description.py
    - tests/fixtures/corpus/simple_score.ly
    - tests/fixtures/corpus/multi_part_score.ly
    - tests/fixtures/corpus/repeat_score.ly
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "1-bar overlap between adjacent chunks for pickup note and cadential material continuity"
  - "Repeats expanded (unrolled) before chunking -- linear chunks match performer reading order"
  - "Fixed 8-bar fallback chunking when no structural boundaries detected"
  - "Deterministic regex metadata extraction -- no LLM involvement per user decision"
  - "python-ly installed as dependency (works on Python 3.13 despite PyPI listing 3.8-3.11)"

patterns-established:
  - "Boundary detection: compiled regex patterns for LilyPond structural cues"
  - "Repeat expansion: brace-counting block extraction with iterative unrolling"
  - "Metadata extraction: individual field extractors composed into extract_metadata()"
  - "Description templating: sentence-per-field with None omission"

requirements-completed: [CORP-04]

# Metrics
duration: 7min
completed: 2026-02-24
---

# Phase 2 Plan 02: Chunking & Metadata Summary

**Music-aware LilyPond phrase chunking with boundary detection, repeat expansion, regex metadata extraction, and structured description templating**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-25T00:11:43Z
- **Completed:** 2026-02-25T00:19:25Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Boundary detection for all LilyPond structural cues (rehearsal marks, barlines, key/time changes, repeats, sections, fine, segno, coda)
- Repeat volta/segno expansion with alternative block handling and safety valve for nested repeats
- Music-aware chunking with 1-bar overlap, 4-8 bar target, and multi-part score support (single-instrument + full-score vertical chunks)
- Deterministic metadata extraction for key, time, tempo, instrument, clef, note density, dynamic range, articulation count, chord symbols
- Structured natural language description templates for ChromaDB embedding (not LLM-generated)
- 57 passing tests across 4 test modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Boundary detection, repeat expansion, and chunking** - `62f45e4` (feat)
2. **Task 2: Metadata extraction and description templating** - `18d4f32` (feat)

## Files Created/Modified
- `src/engrave/corpus/chunker.py` - Music-aware phrase chunking: boundary detection, repeat expansion, bar-count fallback, multi-part support
- `src/engrave/corpus/metadata.py` - Metadata extraction: key, time, tempo, instrument, clef, note density, dynamics, articulations, chords
- `src/engrave/corpus/description.py` - Structured text description templating for ChromaDB embedding
- `tests/unit/test_chunker.py` - 13 tests for chunking behaviors (simple, fallback, overlap, repeats, multi-part)
- `tests/unit/test_boundaries.py` - 16 tests for boundary detection (all structural cue types)
- `tests/unit/test_metadata.py` - 23 tests for metadata extraction (all fields + missing/graceful handling)
- `tests/unit/test_description.py` - 5 tests for description templating (full, omission, natural language)
- `tests/fixtures/corpus/simple_score.ly` - 16-bar single instrument with rehearsal mark at bar 9 and key change at bar 13
- `tests/fixtures/corpus/multi_part_score.ly` - 12-bar violin + cello with double barline at bar 5
- `tests/fixtures/corpus/repeat_score.ly` - 8-bar score with repeat volta 2 and alternatives
- `pyproject.toml` - Added python-ly dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- **1-bar overlap:** Chosen for pickup note and cadential material continuity between adjacent chunks. Enough for musical context without excessive duplication.
- **Repeat expansion before chunking:** Unrolled repeats produce linear chunks matching how performers read through the form. Alternative approach (chunk as-written) would preserve repeat structure but produce less useful retrieval examples.
- **8-bar fallback:** When no structural boundaries exist, synthetic boundaries generated every 8 bar checks. Within the 4-8 bar target range and produces reasonable phrase-length chunks.
- **python-ly compatibility:** Installed python-ly 0.9.9 on Python 3.13 -- works without issues despite PyPI listing 3.8-3.11 only. Confirmed pure Python with no compatibility problems.
- **Note name formatting:** LilyPond accidental notation (fis -> F#, bes -> Bb) mapped to standard display names for readable metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed fallback chunking for boundary-free scores**
- **Found during:** Task 1 (chunking tests)
- **Issue:** When no structural boundaries exist, _split_at_boundaries produced a single chunk for the entire score instead of splitting at bar-count intervals
- **Fix:** Added _generate_bar_boundaries() function that creates synthetic split points every N bar checks when the boundaries list is empty
- **Files modified:** src/engrave/corpus/chunker.py
- **Verification:** test_falls_back_to_4_8_bar_chunks passes
- **Committed in:** 62f45e4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential fix -- without it, plain scores would produce a single oversized chunk instead of phrase-level segments.

## Issues Encountered
- Pre-existing test failure in `tests/unit/test_store.py::TestCorpusStore::test_query_returns_retrieval_results` from Plan 01 implementation. Logged to `deferred-items.md` -- out of scope for this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Chunking pipeline ready for Plan 03's ingestion pipeline to consume via `chunk_score()`
- Metadata extraction ready for Plan 03 to call `extract_metadata()` per chunk
- Description templating ready for Plan 03 to call `generate_description()` per chunk
- All three modules produce raw dicts/strings -- Plan 03 will wrap them in Chunk model objects

## Self-Check: PASSED

- All 10 created files verified present on disk
- Both task commits (62f45e4, 18d4f32) verified in git log
- 57/57 plan tests passing
- ruff check clean on all 3 source modules

---
*Phase: 02-rag-corpus-retrieval*
*Completed: 2026-02-24*
