---
phase: quick
plan: 1
subsystem: docs
tags: [audio-separator, bs-roformer, demucs, source-separation, planning]

# Dependency graph
requires:
  - phase: none
    provides: n/a
provides:
  - Updated STACK.md with audio-separator as primary source separation package
  - Updated ARCHITECTURE.md Stage 1 component with per-stem model routing
  - Updated REQUIREMENTS.md AUDP-01 to best-available model strategy
  - Updated PROJECT.md active requirements for audio-separator
affects: [phase-5-audio-processing, phase-6-audio-understanding]

# Tech tracking
tech-stack:
  added: [audio-separator]
  patterns: [per-stem-model-routing]

key-files:
  created: []
  modified:
    - .planning/research/STACK.md
    - .planning/research/ARCHITECTURE.md
    - .planning/REQUIREMENTS.md
    - .planning/PROJECT.md

key-decisions:
  - "audio-separator replaces demucs-infer as primary source separation package"
  - "Per-stem model strategy: BS-RoFormer for vocals (~12.9 dB SDR), Mel-Band RoFormer for drums/other (~12.5 dB), HTDemucs ft for bass (~9.0 dB)"
  - "demucs-infer preserved in Alternatives Considered for minimal-dependency HTDemucs-only use case"

patterns-established:
  - "Per-stem model routing: different separation models selected per stem target for optimal quality"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-02-24
---

# Quick Task 1: Update Planning Docs for audio-separator Summary

**Replaced demucs-infer with audio-separator across all planning docs, documenting per-stem SOTA model strategy (BS-RoFormer ~12.9 dB SDR vocals, Mel-Band RoFormer, HTDemucs ft, SCNet)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T00:21:27Z
- **Completed:** 2026-02-25T00:26:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- STACK.md fully updated: new audio-separator recommendation with per-stem model strategy table, installation commands, version compatibility, memory budgets, scaling references, and sources
- ARCHITECTURE.md Stage 1 component description, ASCII diagram, data flow, scaling, build order, and sources all reference audio-separator with per-stem model routing
- REQUIREMENTS.md AUDP-01 broadened from "via Demucs v4" to "via best-available model per stem using audio-separator"
- PROJECT.md active requirements bullet updated to audio-separator package
- demucs-infer preserved in Alternatives Considered with clear "when to use" guidance (HTDemucs-only, minimal dependency)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update STACK.md source separation section and installation** - `dae9130` (docs)
2. **Task 2: Update ARCHITECTURE.md, REQUIREMENTS.md, PROJECT.md, and MEMORY.md** - `260b51d` (docs)

## Files Created/Modified
- `.planning/research/STACK.md` - Source Separation section, installation, alternatives, compatibility, memory budget, scaling, sources
- `.planning/research/ARCHITECTURE.md` - Stage 1 component, ASCII diagram, data flow, project structure, scaling, build order, sources
- `.planning/REQUIREMENTS.md` - AUDP-01 requirement text broadened to best-available model strategy
- `.planning/PROJECT.md` - Active requirements bullet updated

## Decisions Made
- audio-separator chosen over demucs-infer as primary package because it wraps all SOTA models (BS-RoFormer, Mel-Band RoFormer, Demucs HTDemucs, MDX-NET, SCNet) under one API
- Per-stem model selection strategy: use highest-quality model per stem in offline pipeline
- demucs-infer retained as documented alternative for HTDemucs-only use cases

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Updated additional Demucs references throughout STACK.md**
- **Found during:** Task 1
- **Issue:** Plan listed 10 specific change locations but STACK.md had additional Demucs references in PyTorch table, Basic Pitch rationale, pipeline strategy, ffmpeg note, librosa note, TensorFlow/JAX note, and Apple Silicon notes
- **Fix:** Updated all remaining Demucs references to audio-separator or neutral language as appropriate
- **Files modified:** .planning/research/STACK.md
- **Verification:** grep confirms no inappropriate Demucs-as-primary references remain
- **Committed in:** dae9130 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Additional references needed updating for consistency. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All planning documents now correctly reference audio-separator for Phase 5 (audio processing) implementation
- Per-stem model strategy is documented with SDR benchmarks to guide model selection during Phase 5
- MEMORY.md updated to reflect audio-separator superseding demucs-infer

## Self-Check: PASSED

- All 4 modified files exist on disk
- Both task commits (dae9130, 260b51d) found in git history

---
*Quick Task: 1*
*Completed: 2026-02-24*
