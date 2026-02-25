---
phase: 05-audio-input-pipeline
plan: 03
subsystem: audio
tags: [audio-separator, source-separation, hierarchical-cascade, htdemucs, bs-roformer, stem-routing]

# Dependency graph
requires:
  - phase: 05-01
    provides: AudioConfig with SeparationStep model and audio normalization
provides:
  - run_separation() hierarchical cascade engine with per-stem model routing
  - StemOutput model for standardized stem artifacts
  - _map_stem_names() for HTDemucs and RoFormer output conventions
  - get_default_steps() big band cascade defaults
affects: [05-04, 05-05, 05-06, 06-audio-understanding]

# Tech tracking
tech-stack:
  added: [audio-separator]
  patterns: [hierarchical-separation-cascade, per-step-model-instantiation, case-insensitive-stem-mapping, positional-fallback]

key-files:
  created:
    - src/engrave/audio/separator.py
    - tests/unit/test_separator.py
  modified: []

key-decisions:
  - "One Separator instance per step, GC reclaims between steps -- prevents memory exhaustion on Apple Silicon"
  - "Case-insensitive substring matching for stem name mapping with positional fallback"
  - "SeparationStep and StemOutput are frozen dataclasses (immutable config)"

patterns-established:
  - "Hierarchical cascade: ordered SeparationStep list where each step's input_stem references a prior step's output"
  - "Per-step Separator instantiation: never keep multiple models in memory simultaneously"
  - "Stem name mapping: name-based matching first, positional fallback when model output names are opaque"

requirements-completed: [AUDP-01]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 5 Plan 3: Source Separation Engine Summary

**Hierarchical cascade engine with per-stem model routing via audio-separator, mapping HTDemucs and RoFormer outputs to standardized stem names**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T01:58:46Z
- **Completed:** 2026-02-25T02:03:07Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Hierarchical separation cascade orchestrating multi-step model execution with chained inputs
- Stem name mapping handling both HTDemucs-style (drums/bass/vocals/other) and RoFormer-style (Vocals/Instrumental) output conventions
- Memory-safe design: one Separator instance at a time, released between steps
- 18 unit tests with fully mocked audio-separator covering cascade logic, name mapping, error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Separation data models and cascade orchestration** - `3418777` (feat)

**Plan metadata:** [pending]

## Files Created/Modified
- `src/engrave/audio/separator.py` - SeparationStep/StemOutput models, run_separation() cascade, _map_stem_names(), get_default_steps()
- `tests/unit/test_separator.py` - 18 unit tests covering single-step, cascade, name mapping (HTDemucs/RoFormer/positional fallback), defaults, error handling

## Decisions Made
- One Separator instance per step with GC reclaim between steps to prevent memory exhaustion on Apple Silicon (4-6GB per model)
- Case-insensitive substring matching for stem name mapping, with positional fallback when output filenames don't contain recognizable stem names
- SeparationStep and StemOutput are frozen (immutable) dataclasses -- config is treated as immutable data
- Empty steps list returns empty results (no error) -- valid degenerate case

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff RUF043 lint error in test regex pattern**
- **Found during:** Task 1 (commit attempt)
- **Issue:** `pytest.raises(match="does_not_exist.wav")` uses `.` which is a regex metacharacter
- **Fix:** Changed to raw string `r"does_not_exist\.wav"` to make regex intent explicit
- **Files modified:** tests/unit/test_separator.py
- **Verification:** `uv run ruff check` passes, all tests pass
- **Committed in:** 3418777 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Lint compliance fix only. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Separation engine ready for integration with audio pipeline (05-05/05-06)
- Transcriber (05-04) can consume StemOutput paths as input
- Benchmark harness can use run_separation() for closed-loop testing

## Self-Check: PASSED

- FOUND: src/engrave/audio/separator.py
- FOUND: tests/unit/test_separator.py
- FOUND: commit 3418777

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-25*
