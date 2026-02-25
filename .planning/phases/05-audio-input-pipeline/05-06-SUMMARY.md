---
phase: 05-audio-input-pipeline
plan: 06
subsystem: audio
tags: [benchmark, mir-eval, midi2audio, fluidsynth, closed-loop-evaluation, json-results]

# Dependency graph
requires:
  - phase: 05-01
    provides: AudioConfig with BenchmarkConfig, SeparationConfig models
  - phase: 05-03
    provides: run_separation() cascade engine for pipeline round-trip
  - phase: 05-04
    provides: Transcriber protocol and quality annotation for pipeline round-trip
provides:
  - "BenchmarkRun, StemMetrics, AggregateScore data models with JSON serialization"
  - "render_midi_to_audio() via FluidSynth for ground truth audio generation"
  - "diff_midi() via mir_eval for note-level precision/recall/F1 evaluation"
  - "BenchmarkHarness with run_single, run_batch, compare_runs orchestration"
  - "CLI benchmark run/compare commands"
affects: [06-audio-understanding, post-phase-5-spike]

# Tech tracking
tech-stack:
  added: [midi2audio, mir_eval]
  patterns: [PipelineProtocol-decoupling, closed-loop-benchmark, JSON-result-storage]

key-files:
  created:
    - src/engrave/benchmark/__init__.py
    - src/engrave/benchmark/models.py
    - src/engrave/benchmark/renderer.py
    - src/engrave/benchmark/evaluator.py
    - src/engrave/benchmark/harness.py
    - tests/unit/test_benchmark_evaluator.py
    - tests/unit/test_benchmark_renderer.py
    - tests/unit/test_benchmark_harness.py
  modified:
    - src/engrave/cli.py
    - pyproject.toml

key-decisions:
  - "PipelineProtocol decouples harness from concrete AudioPipeline -- works before 05-05 is executed"
  - "mir_eval used directly in evaluator tests (pure Python, safe for unit tests) alongside mocked tests"
  - "Per-stem comparison against full reference MIDI -- precision is meaningful, recall expected low per-stem"
  - "BenchmarkConfig as local dataclass, separate from settings.py BenchmarkConfig pydantic model"

patterns-established:
  - "Closed-loop benchmark: render -> process -> diff -> aggregate -> JSON storage"
  - "PipelineProtocol pattern: runtime_checkable Protocol for pipeline dependency injection"
  - "Programmatic MIDI test fixtures via pretty_midi for deterministic benchmark tests"

requirements-completed: [AUDP-01, AUDP-02]

# Metrics
duration: 8min
completed: 2026-02-25
---

# Phase 5 Plan 6: Benchmark Harness Summary

**Closed-loop evaluation harness rendering MIDI to audio via FluidSynth, round-tripping through separation+transcription, and diffing against ground truth with mir_eval precision/recall/F1**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-25T02:08:59Z
- **Completed:** 2026-02-25T02:17:04Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- BenchmarkRun, StemMetrics, AggregateScore data models with full JSON round-trip serialization (to_json/from_json/save/load)
- FluidSynth MIDI-to-audio renderer via midi2audio with configurable SoundFont and directory auto-creation
- mir_eval-based MIDI diff evaluator computing precision, recall, F1, and average overlap from note-level comparison
- BenchmarkHarness orchestrating closed-loop render->process->evaluate with run_single, run_batch, and compare_runs
- CLI `engrave benchmark run` and `engrave benchmark compare` commands with rich table output
- 29 new unit tests, 529 total tests passing with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Benchmark data models, renderer, and evaluator** - `8e9d178` (feat)
2. **Task 2: Benchmark harness orchestration and CLI command** - `3bf3d8f` (feat)

**Plan metadata:** [pending]

## Files Created/Modified
- `src/engrave/benchmark/__init__.py` - Package init with public API exports
- `src/engrave/benchmark/models.py` - BenchmarkRun, StemMetrics, AggregateScore dataclasses with JSON serialization
- `src/engrave/benchmark/renderer.py` - render_midi_to_audio() via midi2audio FluidSynth wrapper
- `src/engrave/benchmark/evaluator.py` - MidiDiffResult and diff_midi() using mir_eval transcription metrics
- `src/engrave/benchmark/harness.py` - BenchmarkHarness class with PipelineProtocol, run_single, run_batch, compare_runs
- `src/engrave/cli.py` - Added benchmark_app Typer group with run and compare commands
- `pyproject.toml` - Added midi2audio and mir_eval dependencies
- `tests/unit/test_benchmark_evaluator.py` - 10 tests: real mir_eval integration + mocked argument verification
- `tests/unit/test_benchmark_renderer.py` - 5 tests: mocked FluidSynth with path/soundfont/error coverage
- `tests/unit/test_benchmark_harness.py` - 14 tests: orchestration, batch, compare, serialization, aggregate computation

## Decisions Made
- PipelineProtocol (runtime_checkable Protocol) decouples harness from concrete AudioPipeline. This allows the benchmark package to be built and tested independently of 05-05 pipeline.py, which hasn't been executed yet. The harness only needs `process(input_path, job_dir)` returning an object with `stem_results`.
- Used real mir_eval in evaluator tests alongside mocked tests. Since mir_eval is pure Python with no system dependencies, it runs reliably in unit tests and validates the actual metric computation.
- Per-stem comparison against the full reference MIDI: each stem's precision is meaningful (are its notes correct?), while recall will naturally be low (each stem only captures part of the full score). This matches the plan's design guidance.
- BenchmarkConfig as a local dataclass in harness.py, separate from the pydantic BenchmarkConfig in settings.py, to keep the benchmark package self-contained. The CLI bridges the two.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed midi2audio and mir_eval dependencies**
- **Found during:** Task 1 (evaluator and renderer implementation)
- **Issue:** midi2audio and mir_eval not in project dependencies
- **Fix:** Added midi2audio>=0.1.1 and mir-eval>=0.8.2 to pyproject.toml, ran uv sync
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** Import succeeds, all tests pass
- **Committed in:** 8e9d178 (Task 1 commit)

**2. [Rule 3 - Blocking] Created placeholder harness.py for __init__.py imports**
- **Found during:** Task 1 (test collection)
- **Issue:** benchmark/__init__.py imports BenchmarkHarness from harness.py, but harness.py wasn't created until Task 2
- **Fix:** Created minimal placeholder harness.py with empty BenchmarkHarness class, replaced with full implementation in Task 2
- **Files modified:** src/engrave/benchmark/harness.py
- **Verification:** Tests collect and run successfully
- **Committed in:** 8e9d178 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed B008 lint error in CLI compare command**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** `typer.Argument(...)` as default parameter value triggers B008 (function call in argument defaults)
- **Fix:** Changed to `Annotated[list[str], typer.Argument(...)]` syntax
- **Files modified:** src/engrave/cli.py
- **Verification:** ruff check passes
- **Committed in:** 3bf3d8f (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All fixes necessary for functionality and lint compliance. No scope creep.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required. FluidSynth must be installed on the system for actual MIDI-to-audio rendering (benchmark tests mock FluidSynth entirely).

## Next Phase Readiness
- Benchmark harness ready for integration once AudioPipeline (05-05) is complete
- PipelineProtocol ensures compatibility with any pipeline implementation satisfying the contract
- JSON result storage enables systematic model comparison across pipeline configurations
- CLI `engrave benchmark run/compare` provides user-facing entry point for experimentation
- 529 total tests passing, all audio pipeline components ready for Phase 6

## Self-Check: PASSED

- All 8 created files verified present on disk
- Commit 8e9d178 found (Task 1)
- Commit 3bf3d8f found (Task 2)
- 529 tests passing, 0 regressions

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-25*
