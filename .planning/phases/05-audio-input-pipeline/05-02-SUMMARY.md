---
phase: 05-audio-input-pipeline
plan: 02
subsystem: audio
tags: [yt-dlp, youtube, audio-extraction, wav, ffmpeg]

# Dependency graph
requires:
  - phase: 01-project-setup
    provides: project structure, settings framework, CLI foundation
provides:
  - extract_youtube_audio() downloading YouTube URL to WAV via yt-dlp Python API
  - is_youtube_url() URL pattern validation for youtube.com/watch, youtu.be, youtube.com/shorts
  - YouTubeExtractionError custom exception for clear error reporting
affects: [05-audio-input-pipeline, 06-audio-understanding]

# Tech tracking
tech-stack:
  added: [yt-dlp]
  patterns: [yt-dlp Python API with context manager, FFmpegExtractAudio postprocessor, video ID deterministic filenames]

key-files:
  created:
    - src/engrave/audio/youtube.py
    - tests/unit/test_youtube.py
  modified: []

key-decisions:
  - "Video ID-based output filenames (not title) for deterministic pipeline runs"
  - "yt-dlp Python API with context manager (not subprocess CLI)"
  - "FFmpegExtractAudio postprocessor with preferredcodec=wav"
  - "Regex URL pattern matching for YouTube validation (youtube.com/watch, youtu.be, youtube.com/shorts)"

patterns-established:
  - "Mock yt_dlp module-level for full isolation in tests"
  - "Custom exception wrapping third-party errors (YouTubeExtractionError wraps DownloadError)"

requirements-completed: [FNDN-03]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 5 Plan 2: YouTube Audio Extraction Summary

**YouTube audio extraction via yt-dlp Python API with deterministic video-ID filenames and FFmpegExtractAudio WAV conversion**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T01:58:36Z
- **Completed:** 2026-02-25T02:02:53Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- YouTube audio extraction module using yt-dlp Python API (not subprocess)
- Deterministic output filenames based on video ID for reproducible pipeline runs
- URL validation covering youtube.com/watch, youtu.be, and youtube.com/shorts patterns
- Custom YouTubeExtractionError wrapping yt-dlp failures with clear messages
- 18 unit tests with fully mocked yt-dlp -- no actual downloads in tests

## Task Commits

Each task was committed atomically:

1. **Task 1: YouTube audio extraction module** - `ad745ac` (feat)

**Plan metadata:** [pending] (docs: complete plan)

_Note: Task 1 was committed as part of 05-01 batch by prior executor. Code verified correct and all tests pass._

## Files Created/Modified
- `src/engrave/audio/youtube.py` - extract_youtube_audio() and is_youtube_url() with YouTubeExtractionError
- `tests/unit/test_youtube.py` - 18 unit tests covering URL validation, extraction options, output path, error handling
- `pyproject.toml` - Added yt-dlp>=2024.0.0 dependency
- `uv.lock` - Updated lockfile with yt-dlp

## Decisions Made
- Video ID-based filenames (`%(id)s.%(ext)s`) instead of title-based for deterministic reproducibility
- yt-dlp Python API with context manager pattern instead of subprocess CLI invocation
- `bestaudio/best` format selection with FFmpegExtractAudio postprocessor converting to WAV
- `quiet=True` and `no_warnings=True` to suppress console output during extraction
- Regex-based URL validation rather than URL parsing for simplicity and performance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Prior executor (05-01) committed youtube.py and test_youtube.py in the same commit as the normalizer/separator/transcriber modules. The code was verified correct and all 18 tests pass. No re-work needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- YouTube extraction ready for integration into audio input pipeline
- Audio format normalization (05-01) and YouTube extraction (05-02) provide the ingestion layer
- Next: source separation (05-03) and transcription (05-04) for the processing layer

## Self-Check: PASSED

- FOUND: src/engrave/audio/youtube.py
- FOUND: tests/unit/test_youtube.py
- FOUND: 05-02-SUMMARY.md
- FOUND: commit ad745ac

---
*Phase: 05-audio-input-pipeline*
*Completed: 2026-02-24*
