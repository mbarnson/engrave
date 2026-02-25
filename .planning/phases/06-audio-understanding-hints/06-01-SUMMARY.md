---
phase: 06-audio-understanding-hints
plan: 01
subsystem: audio
tags: [pydantic, litellm, gemini, audio-lm, structured-output, templates]

# Dependency graph
requires:
  - phase: 05-audio-input-pipeline
    provides: "Audio normalizer, Transcriber protocol pattern, WAV fixtures"
  - phase: 03-midi-to-lilypond
    provides: "SectionBoundary from midi/sections.py"
provides:
  - "AudioDescription and SectionDescription Pydantic models"
  - "Describer protocol (async, runtime_checkable) for audio LM backends"
  - "GeminiDescriber backend with litellm.acompletion, retry, and fallback"
  - "Natural language template rendering for prompt injection"
  - "DescriberConfig nested under AudioConfig in settings.py"
  - "create_describer factory function"
affects: [06-02, 07-convergent-sight-reading, 09-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns: [async-describer-protocol, schema-enforced-json-output, nl-template-rendering]

key-files:
  created:
    - src/engrave/audio/description.py
    - src/engrave/audio/describer.py
    - src/engrave/audio/templates.py
    - tests/unit/test_audio_description.py
    - tests/unit/test_describer.py
    - tests/unit/test_audio_templates.py
  modified:
    - src/engrave/audio/__init__.py
    - src/engrave/config/settings.py

key-decisions:
  - "Describer protocol is async (unlike sync Transcriber) -- audio LM calls are I/O-bound"
  - "GeminiDescriber retries once on validation failure with simplified prompt, then returns minimal defaults"
  - "Audio downsampled to 16kHz via pydub when exceeding max_file_size_mb threshold"
  - "NL templates produce compact prose for CONTEXTUAL prompt block -- no raw JSON in generation prompt"

patterns-established:
  - "Async Protocol pattern: Describer mirrors Transcriber but with async describe() method"
  - "Schema-enforced JSON output: response_format with json_schema sent to litellm for Gemini"
  - "Graceful degradation: all error paths return minimal AudioDescription with defaults, never crash"

requirements-completed: [AUDP-03]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 6 Plan 01: Audio Description Foundation Summary

**AudioDescription Pydantic schema with GeminiDescriber async backend, NL template rendering, and DescriberConfig -- 25 unit tests passing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T03:37:09Z
- **Completed:** 2026-02-25T03:41:12Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- AudioDescription and SectionDescription two-tier Pydantic models with all user-decided fields (no confidence scores)
- GeminiDescriber implementing async Describer protocol with litellm, schema-enforced JSON, retry on validation failure, graceful fallback on timeout/persistent errors
- Natural language template rendering converting structured data to prompt-ready text for the CONTEXTUAL block
- DescriberConfig nested under AudioConfig with model, timeout, max_file_size_mb, max_retries settings
- 25 unit tests covering schema validation, protocol conformance, mocked API calls, retry/fallback, and template rendering

## Task Commits

Each task was committed atomically:

1. **Task 1: AudioDescription schema, Describer protocol + GeminiDescriber, NL templates, DescriberConfig** - `3c91a0d` (feat)
2. **Task 2: Unit tests for AudioDescription schema, Describer protocol, and NL templates** - `2b9f1a8` (test)

## Files Created/Modified
- `src/engrave/audio/description.py` - AudioDescription and SectionDescription Pydantic models
- `src/engrave/audio/describer.py` - Describer protocol, GeminiDescriber, create_describer factory
- `src/engrave/audio/templates.py` - render_track_summary, render_section_description, render_full_description
- `src/engrave/audio/__init__.py` - Updated with new exports (12 new symbols)
- `src/engrave/config/settings.py` - Added DescriberConfig class, nested under AudioConfig
- `tests/unit/test_audio_description.py` - 8 tests for schema validation and JSON roundtrip
- `tests/unit/test_describer.py` - 8 tests for protocol, API calls, retry, fallback, factory
- `tests/unit/test_audio_templates.py` - 9 tests for NL template rendering

## Decisions Made
- Describer protocol is async (`async def describe`) unlike the sync Transcriber -- I/O-bound audio LM calls benefit from concurrent processing
- GeminiDescriber sends simplified prompt on retry (drops section detail) -- reduces chance of same parsing failure repeating
- Audio files exceeding max_file_size_mb are downsampled to 16kHz via pydub before base64 encoding -- Gemini downsamples internally anyway
- NL templates produce compact prose sentences, not bullet points -- matches the natural language injection requirement from CONTEXT.md
- create_describer factory uses getattr for loose coupling with config object -- mirrors create_transcriber pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AudioDescription schema ready for consumption by three-tier prompt builder (06-02)
- GeminiDescriber ready for integration with audio pipeline (06-02)
- NL templates provide render_full_description() for CONTEXTUAL prompt block injection
- DescriberConfig configurable via `[audio.describer]` in engrave.toml

---
*Phase: 06-audio-understanding-hints*
*Completed: 2026-02-25*
