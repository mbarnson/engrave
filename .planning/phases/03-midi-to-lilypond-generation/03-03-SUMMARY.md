---
phase: 03-midi-to-lilypond-generation
plan: 03
subsystem: generation
tags: [pipeline, assembler, cli, gherkin, integration-tests, midi-to-lilypond]

# Dependency graph
requires:
  - phase: 03-midi-to-lilypond-generation
    plan: 01
    provides: "MIDI loading, analysis, tokenization, section detection"
  - phase: 03-midi-to-lilypond-generation
    plan: 02
    provides: "CoherenceState, templates, prompts, failure logging"
  - phase: 01-project-scaffolding-inference-router
    provides: "InferenceRouter, LilyPondCompiler, compile_with_fix_loop"
provides:
  - "End-to-end MIDI-to-LilyPond generation pipeline (generate_from_midi)"
  - "Section assembler merging per-section output into single .ly file"
  - "CLI `engrave generate` command with MIDI input and .ly output"
  - "Integration test suite with mocked LLM/compiler"
  - "Gherkin scenarios for happy path, failure, and no-metadata paths"
affects: [phase-4-rendering, phase-5-audio-analysis, tune-02-finetuning]

# Tech tracking
tech-stack:
  added: []
  patterns: [section-by-section generation orchestration, mock-generator-router pattern, programmatic MIDI test fixtures, async pipeline with mocked IO]

key-files:
  created:
    - src/engrave/generation/pipeline.py
    - src/engrave/generation/assembler.py
    - tests/integration/test_generation_pipeline.py
    - tests/integration/test_section_generation.py
    - tests/integration/test_midi_generation_steps.py
    - tests/integration/features/midi_generation.feature
  modified:
    - src/engrave/generation/__init__.py
    - src/engrave/cli.py
    - tests/conftest.py

key-decisions:
  - "Pipeline uses async throughout for LLM and compilation calls; tests use asyncio.run() wrapper"
  - "Section failure halts entire generation (no partial output with gaps per must_haves)"
  - "Assembler concatenates per-instrument music across sections into continuous variables"
  - "Mock generator router dynamically parses template variable names from prompt for realistic responses"
  - "RAG retriever is optional callable (query, limit) -> list[str]; graceful fallback to empty list"
  - "Analysis proxy object bridges MidiAnalysis (lists of tuples) to CoherenceState (scalar fields)"

patterns-established:
  - "Pipeline orchestration: load -> analyze -> detect sections -> per-section generate -> compile-fix -> assemble"
  - "Mock generator router: extracts variable names from prompt template and returns formatted instrument blocks"
  - "Integration test pattern: programmatic MIDI creation in tmp_path, mocked LLM + compiler, verify output structure"
  - "CLI lazy import pattern with graceful RAG fallback (import error or --no-rag flag)"

requirements-completed: [FNDN-01, LILY-01, LILY-02, LILY-03, LILY-04]

# Metrics
duration: 9min
completed: 2026-02-25
---

# Phase 3 Plan 03: Generation Pipeline and CLI Integration Summary

**Section-by-section MIDI-to-LilyPond generation pipeline with compile-fix loop, section assembly into single .ly file, CLI generate command, and 88 total tests**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T00:58:10Z
- **Completed:** 2026-02-25T01:07:21Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- End-to-end generation pipeline: MIDI load -> analyze -> section detect -> per-section LLM generation -> compile-fix loop -> assembly into single .ly file
- Section assembler merges per-section outputs into one compilable LilyPond file with single \version, \score, and continuous instrument variables
- CLI `engrave generate` command with --output, --labels, --no-rag, and --role options
- 15 integration tests (9 pipeline + 3 section + 3 Gherkin) plus 73 existing unit tests = 88 total Phase 3 tests
- Concert pitch enforcement: no \relative or \transpose in generated output

## Task Commits

Each task was committed atomically:

1. **Task 1: Generation pipeline and section assembler** - `48fd315` (feat)
2. **Task 2: Integration tests and conftest fixtures** - `b6ab4d9` (feat)
3. **Task 3: CLI generate command and Gherkin scenarios** - `bffa50d` (feat)

## Files Created/Modified
- `src/engrave/generation/pipeline.py` - Section-by-section generation orchestration with generate_from_midi() and generate_section()
- `src/engrave/generation/assembler.py` - Section assembly into single .ly file with continuous instrument variables
- `src/engrave/generation/__init__.py` - Updated exports: GenerationResult, GenerationHaltError, generate_from_midi, assemble_sections
- `src/engrave/cli.py` - Added `engrave generate` command with MIDI input and .ly output
- `tests/conftest.py` - Added 5 new fixtures: mock_rag_retriever, sample_midi_type0, sample_midi_type1, mock_generator_router, mock_compiler_success
- `tests/integration/test_generation_pipeline.py` - 9 integration tests for pipeline (type 0/1, user labels, no-RAG, failure, concert pitch)
- `tests/integration/test_section_generation.py` - 3 integration tests for multi-section coherence, single section, assembly structure
- `tests/integration/test_midi_generation_steps.py` - 3 Gherkin step definitions for happy path, failure halt, no-metadata
- `tests/integration/features/midi_generation.feature` - 3 Gherkin scenarios

## Decisions Made
- Pipeline uses async throughout for LLM and compiler calls; integration tests wrap with asyncio.run()
- Section compilation failure halts entire generation and returns structured failure record (no partial output with gaps)
- Assembler concatenates per-instrument music content across all sections into continuous variables in a single \score block
- Mock generator router dynamically parses variable names from the prompt template to produce realistic instrument blocks
- RAG retriever is an optional callable with signature (query, limit) -> list[str]; pipeline gracefully falls back to empty examples
- Analysis proxy object bridges MidiAnalysis (which stores lists of tuples) to CoherenceState.initial_from_analysis (which expects scalar attributes)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete Phase 3: MIDI file in, compilable LilyPond out
- `engrave generate` CLI command ready for use with real MIDI files (requires configured LLM provider)
- Pipeline integrates: MIDI subsystem (Plan 01) + generation foundation (Plan 02) + orchestration (Plan 03)
- 88 tests across unit and integration suites provide regression safety
- No blockers for Phase 4 (rendering) or Phase 5 (audio analysis)

## Self-Check: PASSED

All 9 files verified present. All 3 commit hashes verified in git log. 88 tests pass.

---
*Phase: 03-midi-to-lilypond-generation*
*Completed: 2026-02-25*
