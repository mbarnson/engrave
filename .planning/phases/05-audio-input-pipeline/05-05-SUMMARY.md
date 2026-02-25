---
phase: 05-audio-input-pipeline
plan: 05
subsystem: audio
tags: [pipeline, orchestration, cli, integration-tests, job-directory]

# Dependency graph
requires:
  - phase: 05-01
    provides: AudioConfig, normalize_audio, sample_wav fixture
  - phase: 05-02
    provides: extract_youtube_audio, is_youtube_url
  - phase: 05-03
    provides: run_separation, StemOutput, get_default_steps
  - phase: 05-04
    provides: Transcriber protocol, BasicPitchTranscriber, annotate_quality, StemQuality
provides:
  - "AudioPipeline orchestrating normalize -> separate -> transcribe -> annotate"
  - "JobResult and StemResult dataclasses for pipeline output"
  - "CLI process-audio command accepting audio files or YouTube URLs"
  - "Public API re-exports from engrave.audio package"
  - "Mock fixtures: mock_normalizer, mock_separator, mock_transcriber"
affects: [05-06, 06-audio-understanding]

# Tech tracking
tech-stack:
  added: []
  patterns: [pipeline-orchestration-with-job-directory, cli-lazy-imports-with-mock-patching, conftest-mock-fixtures-for-audio-stages]

key-files:
  created:
    - src/engrave/audio/pipeline.py
    - tests/integration/test_audio_pipeline.py
    - tests/integration/test_youtube_extract.py
  modified:
    - src/engrave/audio/__init__.py
    - src/engrave/cli.py
    - tests/conftest.py
    - .gitignore

key-decisions:
  - "Pipeline stages run sequentially (not async) -- simplifies error handling and job directory state"
  - "Transcriber injected into AudioPipeline constructor for testability"
  - "Config SeparationStep models converted to separator.SeparationStep at pipeline boundary"
  - "jobs/ gitignored to prevent large WAV intermediates from being committed"

patterns-established:
  - "Job directory structure: input.wav, separation/, transcription/, quality/, metadata.json"
  - "Mock fixture pattern: conftest fixtures patch pipeline imports for isolated integration testing"
  - "CLI lazy import pattern with mocked module-level patches for Typer CLI tests"

requirements-completed: [FNDN-02, FNDN-03, AUDP-01, AUDP-02]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 5 Plan 05: Audio Pipeline Orchestration Summary

**End-to-end audio pipeline wiring normalizer, separator, transcriber, and quality annotator into a single AudioPipeline with CLI process-audio command and 16 integration tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T02:09:03Z
- **Completed:** 2026-02-25T02:14:14Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- AudioPipeline class orchestrating 4-stage sequential pipeline (normalize, separate, transcribe, annotate) with timestamped job directory management
- CLI `engrave process-audio` command accepting audio file paths or YouTube URLs with `--output-dir`, `--no-separate`, and `--steps` options
- Public API re-exports from engrave.audio: AudioPipeline, JobResult, StemResult, StemQuality, annotate_quality, extract_youtube_audio, normalize_audio
- 16 integration tests covering full pipeline flow, job directory structure, metadata writing, error propagation, YouTube extraction, and CLI command
- Mock fixture infrastructure (mock_normalizer, mock_separator, mock_transcriber) in conftest for reusable audio test isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: AudioPipeline orchestration and job directory structure** - `a631668` (feat)
2. **Task 2: CLI process-audio command and integration tests** - `78d4173` (feat)

**Plan metadata:** [pending]

## Files Created/Modified
- `src/engrave/audio/pipeline.py` - AudioPipeline, JobResult, StemResult dataclasses; 4-stage orchestration; YouTube wrapper
- `src/engrave/audio/__init__.py` - Public API re-exports for all audio package symbols
- `src/engrave/cli.py` - process-audio CLI command with YouTube URL detection and rich output
- `tests/integration/test_audio_pipeline.py` - 10 integration tests for pipeline orchestration and error handling
- `tests/integration/test_youtube_extract.py` - 6 integration tests for YouTube flow and CLI command
- `tests/conftest.py` - mock_normalizer, mock_separator, mock_transcriber fixtures; _write_minimal_wav helper
- `.gitignore` - Added jobs/ directory entry

## Decisions Made
- Pipeline stages execute sequentially (not async) to simplify error handling and job directory state management
- Transcriber is injected into AudioPipeline constructor to support test mocking without patching
- Config SeparationStep (Pydantic) models are converted to separator.SeparationStep (frozen dataclass) at the pipeline boundary to keep module independence
- jobs/ gitignored because WAV intermediate files are large and transient

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-commit ruff hooks caught unused variable assignments and formatting issues in test files. Fixed inline before commit (standard pre-commit flow, not a deviation).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full audio pipeline operational end-to-end with mocked dependencies
- Plan 05-06 (benchmark harness) can use AudioPipeline and mock fixtures for closed-loop evaluation
- Phase 6 (audio understanding) can invoke pipeline via CLI or Python API
- 515 total tests passing with zero regressions

## Self-Check: PASSED

All created files verified present. Commits a631668 and 78d4173 confirmed in git history.

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-25*
