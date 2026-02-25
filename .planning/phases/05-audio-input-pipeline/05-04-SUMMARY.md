---
phase: 05-audio-input-pipeline
plan: 04
subsystem: audio
tags: [basic-pitch, midi, transcription, quality-metrics, pretty-midi, numpy, protocol]

# Dependency graph
requires:
  - phase: 03-generation-engine
    provides: "MIDI analysis infrastructure (pretty_midi, numpy already available)"
provides:
  - "Transcriber protocol for pluggable WAV-to-MIDI backends"
  - "BasicPitchTranscriber with in-process ONNX and subprocess venv paths"
  - "StemQuality dataclass with 5 heuristic transcription quality metrics"
  - "annotate_quality() computing quality metadata from MIDI files"
  - "INSTRUMENT_RANGES pitch bounds for 13 instruments"
affects: [05-audio-input-pipeline, 06-audio-understanding]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Protocol-based pluggable backend (Transcriber)", "Dual execution path (in-process vs subprocess)", "Quality-as-metadata not quality-as-gate"]

key-files:
  created:
    - src/engrave/audio/transcriber.py
    - src/engrave/audio/quality.py
    - tests/unit/test_transcriber.py
    - tests/unit/test_quality.py
  modified: []

key-decisions:
  - "TranscriptionConfig dataclass local to transcriber.py (not yet in settings.py) -- will integrate when audio pipeline config is complete"
  - "Quality metrics are informational metadata for LLM, not binary pass/fail gates"
  - "Onset cluster score uses 10ms threshold and counts fraction of notes with at least one neighbor within threshold"
  - "Drum tracks excluded from quality analysis (only pitched instruments)"

patterns-established:
  - "Protocol + dataclass backend pattern: runtime_checkable Protocol for contract, dataclass for implementation"
  - "Lazy import pattern: basic_pitch imported inside method to avoid import errors in Python 3.12 environment"
  - "Programmatic MIDI test fixtures: pretty_midi creates deterministic test inputs, no fixture files"

requirements-completed: [AUDP-02]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 5 Plan 4: Transcription Engine and Quality Annotation Summary

**Pluggable WAV-to-MIDI transcription via Basic Pitch protocol with 5-metric post-transcription quality heuristics for downstream LLM confidence assessment**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T01:58:40Z
- **Completed:** 2026-02-25T02:04:49Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Transcriber protocol with runtime-checkable contract for pluggable WAV-to-MIDI backends
- BasicPitchTranscriber supporting both in-process ONNX and subprocess Python 3.10 venv execution paths
- StemQuality dataclass computing 5 heuristic quality metrics (note density, pitch range violations, onset clustering, velocity variance, duration CV) from transcribed MIDI
- 44 unit tests passing (11 transcriber + 33 quality) with all basic_pitch dependencies fully mocked

## Task Commits

Each task was committed atomically:

1. **Task 1: Transcriber protocol and BasicPitchTranscriber** - `6538b4d` (feat, bundled with 05-01 commit due to parallel execution)
2. **Task 2: Post-transcription quality annotation** - `0111935` (feat)

## Files Created/Modified
- `src/engrave/audio/transcriber.py` - Transcriber protocol, BasicPitchTranscriber, TranscriptionConfig, create_transcriber factory
- `src/engrave/audio/quality.py` - StemQuality dataclass, annotate_quality(), INSTRUMENT_RANGES, get_expected_range()
- `tests/unit/test_transcriber.py` - 11 tests covering protocol conformance, both execution paths, validation, factory
- `tests/unit/test_quality.py` - 33 tests covering all 5 metrics, empty MIDI, serialization, instrument range lookup

## Decisions Made
- TranscriptionConfig dataclass kept local to transcriber.py rather than adding to settings.py -- will integrate when full audio pipeline config is established
- Quality metrics are purely informational (the "LLM IS the fallback" strategy) -- no automatic re-transcription or gating
- Onset cluster threshold set at 10ms matching common neural transcription temporal resolution
- Drum instruments excluded from quality analysis since quality metrics target pitched content

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cleaned up onset_cluster_score computation**
- **Found during:** Task 2 (quality annotation)
- **Issue:** Initial onset cluster algorithm had redundant first-pass computation
- **Fix:** Replaced with single-pass neighbor-checking algorithm that counts notes with at least one neighbor within 10ms
- **Files modified:** src/engrave/audio/quality.py
- **Verification:** All onset cluster tests pass with correct scores
- **Committed in:** 0111935 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor cleanup, no scope change.

## Issues Encountered

- Pre-commit hook stash/unstash conflict with prior uncommitted phase 5 files (from plans 01-03) caused Task 1 to commit under an incorrect commit message alongside youtube.py and test_youtube.py files. The transcriber.py and test_transcriber.py content is correct; only the commit attribution is mixed with prior plan files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Transcriber protocol ready for pipeline integration in plan 05-05/05-06
- Quality annotation ready to feed StemQuality metadata into downstream LLM prompts
- 484 total tests passing with no regressions

## Self-Check: PASSED

- All 4 created files exist on disk
- Commit 6538b4d found (Task 1 - bundled with 05-01)
- Commit 0111935 found (Task 2)
- 484 tests passing, 0 regressions

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-25*
