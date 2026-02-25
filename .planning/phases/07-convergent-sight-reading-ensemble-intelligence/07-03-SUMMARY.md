---
phase: 07-convergent-sight-reading-ensemble-intelligence
plan: 03
subsystem: generation
tags: [pipeline, section-groups, joint-generation, articulation, beaming, coherence, ensemble]

# Dependency graph
requires:
  - phase: 07-01-articulation-post-processor
    provides: "apply_articulation_defaults() ENSM-03 and apply_section_consistency() ENSM-05"
  - phase: 07-02-section-groups-beaming
    provides: "resolve_section_groups(), BeamStyle, beaming_commands(), resolve_beam_style()"
provides:
  - "Per-section-group dispatch in generate_from_midi() (7 calls vs 17 for big band)"
  - "ENSM-03 + ENSM-05 post-processing chain integrated into pipeline"
  - "Per-group coherence state (dict[str, CoherenceState]) for independent section tracking"
  - "Beaming commands injected per temporal section via build_score_template beaming parameter"
  - "8 integration tests validating complete pipeline: dispatch, post-processing, beaming, failure, coherence"
affects: [pipeline-assembly, uat-testing, tune-02-feedback-loop]

# Tech tracking
tech-stack:
  added: []
  patterns: ["per-section-group dispatch replacing per-instrument dispatch", "lazy post-processing import in pipeline to avoid circular dependencies", "group identifier keying for coherence state"]

key-files:
  created:
    - tests/integration/test_section_group_generation.py
  modified:
    - src/engrave/generation/pipeline.py
    - src/engrave/generation/templates.py

key-decisions:
  - "Backward compatible: preset=None falls back to per-instrument generation (no breaking changes)"
  - "Post-processing imports lazy inside generate_from_midi to avoid circular dependency (same pattern as 07-02)"
  - "Group identifier uses first instrument's sanitized variable_name for coherence dict keying"
  - "Section failure on any group halts entire temporal section (matching existing 03-03 decision)"

patterns-established:
  - "Section-group dispatch pattern: resolve groups from preset, iterate per group, scope MIDI/RAG/coherence, dispatch LLM"
  - "Post-processing pipeline pattern: LLM output -> ENSM-03 defaults -> ENSM-05 consistency -> assembly"
  - "Beaming injection pattern: resolve_beam_style per section -> beaming_commands -> build_score_template beaming parameter"

requirements-completed: [ENSM-02, ENSM-03, ENSM-05, ENGR-05]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 07 Plan 03: Pipeline Restructuring Summary

**Per-section-group LLM dispatch (17 calls -> 7 for big band) with ENSM-03/ENSM-05 articulation post-processing chain and swing/straight beaming injection per temporal section**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T04:58:57Z
- **Completed:** 2026-02-25T05:05:43Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Restructured generate_from_midi() pipeline from per-instrument to per-section-group dispatch with optional BigBandPreset parameter
- Integrated ENSM-03 articulation defaults and ENSM-05 section consistency into the post-processing chain after LLM output
- Per-group coherence state maintained independently as dict[str, CoherenceState] keyed by group identifier
- Beaming commands injected per temporal section via resolve_beam_style into build_score_template
- 8 integration tests covering joint dispatch, mixed dispatch, articulation defaults, section consistency, beaming, failure handling, and coherence isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Restructure pipeline for per-section-group dispatch with post-processing** - `0f6a18c` (feat)
2. **Task 2: Integration tests for joint generation and post-processing pipeline** - `e361d74` (test)

## Files Created/Modified
- `src/engrave/generation/pipeline.py` - Per-section-group dispatch with preset parameter, per-group coherence, ENSM-03/05 post-processing, beaming injection
- `src/engrave/generation/templates.py` - Added optional beaming parameter to build_score_template()
- `tests/integration/test_section_group_generation.py` - 8 integration tests (682 lines) validating complete pipeline

## Decisions Made
- Backward compatible preset parameter: when preset=None, falls back to per-instrument generation -- no breaking changes to existing callers or tests
- Lazy import of articulation post-processing functions inside generate_from_midi to avoid circular dependency chain (matching 07-02 lazy import pattern)
- Group identifier uses first instrument's sanitized variable name as dict key for coherence state
- Section failure on any group halts the entire temporal section with failure record identifying the specific group (matching existing 03-03 decision)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Pipeline restructuring complete: generate_from_midi() can dispatch per-section-group with BigBandPreset
- All 805 tests pass (797 unit + 8 new integration) with no regressions
- Post-processing chain (ENSM-03 -> ENSM-05) fully integrated
- Ready for UAT testing in Plan 07.1-03

## Self-Check: PASSED
