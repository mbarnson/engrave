---
phase: 03-midi-to-lilypond-generation
plan: 02
subsystem: generation
tags: [pydantic, lilypond, coherence, prompt-engineering, token-budget, failure-logging]

# Dependency graph
requires:
  - phase: 01-project-foundation
    provides: pydantic-settings config and LilyPond compiler/fixer
  - phase: 02-rag-corpus-retrieval
    provides: RAG retrieval for LilyPond examples
provides:
  - CoherenceState model for musical context passing between sections
  - LilyPond structural template generation (absolute pitch, concert pitch)
  - Prompt budget manager with graceful truncation
  - Structured failure logging for TUNE-02 fine-tuning
affects: [03-03-pipeline, phase-4-rendering, tune-02-finetuning]

# Tech tracking
tech-stack:
  added: []
  patterns: [variable-per-instrument templates, section coherence state, prompt budget management, structured failure logging]

key-files:
  created:
    - src/engrave/generation/__init__.py
    - src/engrave/generation/coherence.py
    - src/engrave/generation/templates.py
    - src/engrave/generation/prompts.py
    - src/engrave/generation/failure_log.py
    - tests/unit/test_coherence.py
    - tests/unit/test_templates.py
    - tests/unit/test_concert_pitch.py
    - tests/unit/test_prompt_budget.py
    - tests/unit/test_failure_log.py
  modified: []

key-decisions:
  - "CoherenceState carries 12 fields including dynamics, articulation, voicing, open ties, and running summary capped at 1200 chars"
  - "Summary truncation uses simple oldest-content removal (LLM compression deferred per research open question #3)"
  - "Prompt budget defaults to 32K total: 2K system + 500 template + 500 coherence + 3K RAG + 4K MIDI + 8K output + 4K safety"
  - "Truncation priority: RAG examples first, then coherence, then MIDI as last resort"
  - "Failure records stored as individual JSON files with timestamp-based filenames for easy ingestion"

patterns-established:
  - "Variable-per-instrument LilyPond templates: LLM fills music content, never generates score structure"
  - "Absolute pitch mode exclusively: no \\relative in generated templates"
  - "Concert pitch storage: no \\transpose in generated code"
  - "Graceful budget truncation: reduce least-critical content first (RAG > coherence > MIDI)"
  - "Structured failure logging: every compilation failure recorded for future fine-tuning"

requirements-completed: [LILY-02, LILY-03, LILY-04]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 3 Plan 02: Generation Foundation Summary

**CoherenceState model with 12 musical context fields, LilyPond variable-per-instrument templates in absolute/concert pitch, prompt budget manager with graceful RAG-first truncation, and structured JSON failure logging**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T00:46:10Z
- **Completed:** 2026-02-25T00:51:58Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- CoherenceState pydantic model serializes to compact prompt text, updates from generated LilyPond, detects open ties and dynamics, truncates running summaries
- LilyPond structural templates use absolute pitch mode and concert pitch exclusively -- LLM fills only music content within pre-validated skeletons
- Prompt budget manager allocates tokens across 7 categories and truncates gracefully (RAG examples first, coherence second, MIDI last)
- Failure logging writes machine-readable JSON with full context (prompt, MIDI tokens, error output, coherence state) for TUNE-02 fine-tuning

## Task Commits

Each task was committed atomically:

1. **Task 1: CoherenceState model and LilyPond structural templates** - `545d249` (feat, TDD: 26 tests)
2. **Task 2: Prompt budget manager and failure logging** - `28d4e05` (feat, TDD: 15 tests)

_TDD: Tests written first (RED), then implementation (GREEN), with ruff linting after each phase._

## Files Created/Modified
- `src/engrave/generation/__init__.py` - Package init with public API re-exports
- `src/engrave/generation/coherence.py` - CoherenceState pydantic model with serialization and update logic
- `src/engrave/generation/templates.py` - LilyPond structural template generation and LLM response parsing
- `src/engrave/generation/prompts.py` - Prompt construction with budget management
- `src/engrave/generation/failure_log.py` - Structured failure logging for TUNE-02
- `tests/unit/test_coherence.py` - 9 tests for CoherenceState
- `tests/unit/test_templates.py` - 14 tests for template generation
- `tests/unit/test_concert_pitch.py` - 3 tests for absolute/concert pitch constraints
- `tests/unit/test_prompt_budget.py` - 9 tests for prompt budget and build_section_prompt
- `tests/unit/test_failure_log.py` - 6 tests for failure logging

## Decisions Made
- CoherenceState summary truncation uses simple oldest-content removal (trim from beginning, prepend "..."). LLM-based compression deferred per research open question #3.
- Token estimation uses chars/4 approximation -- rough but sufficient for budget management. Exact tokenizer integration deferred until model selection.
- Failure records stored as individual JSON files (not a single log file) for easy parallel ingestion and TUNE-02 training data preparation.
- Variable naming convention: camelCase with digit-to-word conversion (e.g., "Alto Sax 1" -> "altoSaxOne") for valid LilyPond identifiers.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Generation foundation modules ready for pipeline orchestration (Plan 03)
- CoherenceState, templates, prompts, and failure logging are pure logic with no I/O dependencies on MIDI parsing
- Plan 01 (MIDI parsing) and Plan 02 (generation foundation) can proceed in parallel -- no blocking dependencies

## Self-Check: PASSED

- All 10 created files verified present on disk
- Commit 545d249 (Task 1) verified in git log
- Commit 28d4e05 (Task 2) verified in git log
- 41 tests pass across 5 test files

---
*Phase: 03-midi-to-lilypond-generation*
*Completed: 2026-02-25*
