---
phase: 07-convergent-sight-reading-ensemble-intelligence
plan: 02
subsystem: rendering
tags: [lilypond, beaming, section-groups, ensemble, swing, big-band]

# Dependency graph
requires:
  - phase: 04-rendering-engine
    provides: "InstrumentSpec, BigBandPreset, generate_part, generate_conductor_score"
provides:
  - "InstrumentSpec.section_group field for joint generation grouping"
  - "resolve_section_groups() function grouping instruments by section"
  - "BeamStyle enum and beaming_commands() for swing/straight LilyPond Timing"
  - "resolve_beam_style() for style inference from description and hints"
  - "Beaming injection in generate_part() and generate_conductor_score()"
affects: [07-03-pipeline-restructuring, ensm-02-joint-generation]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy-import-circular-dependency, style-aware-beaming, section-group-resolution]

key-files:
  created:
    - src/engrave/generation/section_groups.py
    - tests/unit/test_section_groups.py
    - tests/unit/test_beaming.py
  modified:
    - src/engrave/rendering/ensemble.py
    - src/engrave/rendering/generator.py
    - tests/unit/test_ensemble.py
    - tests/unit/test_part_generator.py
    - tests/unit/test_score_generator.py

key-decisions:
  - "Lazy import of beaming_commands in generator.py to break circular dependency (rendering.__init__ -> generator -> section_groups -> ensemble -> rendering.__init__)"
  - "Beaming style defaults to swing for big band if unspecified"
  - "resolve_beam_style uses keyword matching against frozensets for style classification"

patterns-established:
  - "Lazy import pattern for cross-package dependencies that would create circular imports"
  - "Section group as optional field (None = ungrouped, string = group name) on InstrumentSpec"

requirements-completed: [ENSM-02, ENGR-05]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 07 Plan 02: Section Groups and Beaming Summary

**InstrumentSpec section_group field with resolve_section_groups() producing 7 generation groups from big band, plus swing/straight beaming command injection into LilyPond part and score generators**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T04:50:22Z
- **Completed:** 2026-02-25T04:55:59Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Added section_group field to InstrumentSpec with correct BigBandPreset assignments (5 saxes, 4 trumpets, 4 trombones grouped; 4 rhythm ungrouped)
- Created resolve_section_groups() returning 7 groups sorted by score_order from big band preset
- Implemented BeamStyle enum, beaming_commands(), and resolve_beam_style() with swing/straight LilyPond 2.24 Timing commands
- Injected beaming commands into generate_part() and generate_conductor_score() with beam_style parameter defaulting to swing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add section_group to InstrumentSpec and resolve_section_groups with beaming** - `d727eb4` (feat)
2. **Task 2: Inject beaming commands into LilyPond template generation** - `08fb832` (feat)

## Files Created/Modified
- `src/engrave/generation/section_groups.py` - BeamStyle enum, resolve_section_groups(), beaming_commands(), resolve_beam_style()
- `src/engrave/rendering/ensemble.py` - Added section_group field to InstrumentSpec with BigBandPreset assignments
- `src/engrave/rendering/generator.py` - Added beam_style parameter and beaming injection to generate_part() and generate_conductor_score()
- `tests/unit/test_section_groups.py` - 16 tests for section group resolution
- `tests/unit/test_beaming.py` - 15 tests for beaming commands and beam style resolution
- `tests/unit/test_ensemble.py` - 7 new tests for section_group field verification
- `tests/unit/test_part_generator.py` - 5 new tests for part beaming injection
- `tests/unit/test_score_generator.py` - 5 new tests for conductor score beaming injection

## Decisions Made
- Lazy import of beaming_commands inside generate_part() and generate_conductor_score() to break circular dependency chain (rendering.__init__ -> generator -> section_groups -> ensemble -> rendering.__init__)
- Beaming commands placed after \score { in parts and after << in conductor score for correct LilyPond Timing scope
- resolve_beam_style defaults to SWING for big band when no style signal detected from description or user hints

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed circular import between rendering and generation packages**
- **Found during:** Task 2 (beaming injection into generator.py)
- **Issue:** Top-level import of beaming_commands from engrave.generation.section_groups caused circular import: rendering.__init__ -> generator -> section_groups -> ensemble -> rendering.__init__
- **Fix:** Changed to lazy import inside the two functions that use beaming_commands
- **Files modified:** src/engrave/rendering/generator.py
- **Verification:** Full test suite (163 tests) passes without import errors
- **Committed in:** 08fb832 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Import pattern change required for correctness. No scope creep.

## Issues Encountered
None beyond the circular import auto-fixed above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Section groups provide the structural foundation for joint generation dispatch in Plan 07-03
- Beaming commands are per-part for now; per-section temporal beaming will be wired in 07-03
- All existing tests continue to pass (163 total across affected test files)

## Self-Check: PASSED

- All 8 source/test files: FOUND
- Commit d727eb4 (Task 1): FOUND
- Commit 08fb832 (Task 2): FOUND
- Full test suite: 163 passed

---
*Phase: 07-convergent-sight-reading-ensemble-intelligence*
*Completed: 2026-02-25*
