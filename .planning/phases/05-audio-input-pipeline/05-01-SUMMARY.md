---
phase: 05-audio-input-pipeline
plan: 01
subsystem: audio
tags: [pydub, audio-normalization, wav, config, pydantic]

# Dependency graph
requires:
  - phase: 01-project-setup
    provides: Settings/pydantic-settings TOML loading infrastructure
provides:
  - AudioConfig with nested SeparationConfig, TranscriptionConfig, BenchmarkConfig
  - normalize_audio() converting MP3/WAV/AIFF/FLAC to WAV mono 44.1kHz 16-bit
  - detect_audio_format() for extension-based format identification
  - sample_wav conftest fixture for audio test suites
affects: [05-audio-input-pipeline, 06-audio-understanding]

# Tech tracking
tech-stack:
  added: [pydub]
  patterns: [nested-pydantic-config, stdlib-wav-test-fixtures]

key-files:
  created:
    - src/engrave/audio/__init__.py
    - src/engrave/audio/normalizer.py
    - tests/unit/test_normalizer.py
  modified:
    - src/engrave/config/settings.py
    - tests/conftest.py
    - pyproject.toml

key-decisions:
  - "pydub for format detection/conversion via AudioSegment.from_file() -- lightweight wrapper around ffmpeg"
  - "stdlib wave module for test fixture creation -- no pydub dependency in test setup"
  - "SeparationConfig.default_steps() class method returns big band cascade (htdemucs_ft + bs_roformer)"

patterns-established:
  - "Audio test fixtures use stdlib wave module, not pydub, for programmatic WAV creation"
  - "Nested config models (SeparationStep, TranscriptionConfig, BenchmarkConfig) under AudioConfig"
  - "sample_wav conftest fixture: 1s 440Hz mono sine wave for audio pipeline tests"

requirements-completed: [FNDN-02, FNDN-03]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 5 Plan 01: Audio Config Extension and Format Normalizer Summary

**AudioConfig with nested separation/transcription/benchmark models and pydub-based format normalizer converting MP3/WAV/AIFF/FLAC to WAV mono 44.1kHz**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T01:58:35Z
- **Completed:** 2026-02-25T02:03:10Z
- **Tasks:** 1
- **Files modified:** 7

## Accomplishments
- Extended Settings with AudioConfig containing target_sample_rate, target_channels, max_duration_seconds, supported_formats, plus nested SeparationConfig, TranscriptionConfig, and BenchmarkConfig
- Created normalize_audio() that converts supported audio formats to WAV mono 44.1kHz with duration and format validation
- Created detect_audio_format() for extension-based format identification with clear error messages
- Added 18 unit tests covering format detection, WAV passthrough, stereo-to-mono downmix, resampling, directory creation, error paths, and mocked non-WAV format handling
- Added sample_wav conftest fixture and [audio] section to MINIMAL_TOML for test infrastructure

## Task Commits

Each task was committed atomically:

1. **Task 1: Audio config extension and normalizer module** - `6538b4d` (feat)

**Plan metadata:** [pending]

## Files Created/Modified
- `src/engrave/config/settings.py` - Added AudioConfig, SeparationStep, SeparationConfig, TranscriptionConfig, BenchmarkConfig models; added audio field to Settings
- `src/engrave/audio/__init__.py` - Audio package init with docstring and empty __all__
- `src/engrave/audio/normalizer.py` - normalize_audio() and detect_audio_format() functions
- `tests/unit/test_normalizer.py` - 18 unit tests for normalizer module
- `tests/conftest.py` - Added sample_wav fixture, [audio] section in MINIMAL_TOML, wave/struct/math imports
- `pyproject.toml` - Added pydub>=0.25.1 dependency

## Decisions Made
- Used pydub for format detection/conversion via AudioSegment.from_file() -- lightweight wrapper around ffmpeg, handles all four target formats
- stdlib wave module for test fixture creation -- keeps test setup independent of the library under test
- SeparationConfig.default_steps() returns big band cascade: htdemucs_ft for 4-stem split, then bs_roformer on the "other" residual for piano isolation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed pydub dependency**
- **Found during:** Task 1 (normalizer implementation)
- **Issue:** pydub not in project dependencies, import would fail
- **Fix:** Added pydub>=0.25.1 to pyproject.toml dependencies, ran uv sync
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** Import succeeds, all 433 tests pass
- **Committed in:** 6538b4d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Dependency installation necessary for normalizer to function. No scope creep.

## Issues Encountered
- Pre-commit hook stash/restore behavior initially caused commit to capture pre-staged files from other plan work instead of this plan's changes. Resolved by amending the commit with correct file staging.

## User Setup Required

None - no external service configuration required. pydub requires ffmpeg to be installed on the system for non-WAV format handling (ffmpeg is typically pre-installed on macOS via Homebrew or Xcode).

## Next Phase Readiness
- AudioConfig and normalizer are ready for consumption by Plans 02-06 (YouTube ingestion, source separation, transcription, benchmark harness, public API)
- sample_wav fixture available in conftest for all audio pipeline tests
- SeparationConfig and TranscriptionConfig schemas ready for Plan 02 (separation) and Plan 04 (transcription) implementation

## Self-Check: PASSED

All created files verified present. Commit 6538b4d confirmed in git history.

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-25*
