---
phase: 06-audio-understanding-hints
plan: 02
subsystem: generation
tags: [hints, prompt-engineering, audit-log, three-tier-prompt, cli]

# Dependency graph
requires:
  - phase: 06-audio-understanding-hints
    provides: "AudioDescription Pydantic models, NL template rendering, GeminiDescriber"
  - phase: 03-midi-to-lilypond
    provides: "build_section_prompt, generate_section, generate_from_midi pipeline"
provides:
  - "Hint loader with inline text vs file path auto-detection"
  - "Three-tier prompt authority structure (DEFINITIVE/CONTEXTUAL/RAW INPUT)"
  - "Audit log for per-field source resolution tracking (structured JSON)"
  - "Pipeline integration: audio_description and user_hints flow to every section"
  - "CLI --hints flag on generate command"
affects: [07-convergent-sight-reading, 09-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns: [three-tier-prompt-authority, per-field-audit-log, hint-loader-auto-detection]

key-files:
  created:
    - src/engrave/hints/__init__.py
    - src/engrave/hints/loader.py
    - src/engrave/generation/audit.py
    - tests/unit/test_hint_loader.py
    - tests/unit/test_audit.py
    - tests/integration/test_audio_generation.py
  modified:
    - src/engrave/generation/prompts.py
    - src/engrave/generation/pipeline.py
    - src/engrave/generation/__init__.py
    - src/engrave/cli.py
    - tests/unit/test_prompt_budget.py

key-decisions:
  - "Three-tier prompt uses same template for all paths (audio+MIDI, MIDI-only) with placeholder text for empty tiers"
  - "Audio description and user hints are NEVER truncated -- only MIDI, RAG, and coherence participate in budget fitting"
  - "Audit log is skeletal in Phase 6 -- hint_value always None (hints unstructured), audio_value requires NL parsing"
  - "MIDI/audio disagreements logged at WARNING level -- disagreement itself is the signal (per user decision)"
  - "PromptBudget safety_margin reduced from 4000 to 3200 to accommodate new description_tokens=800 field"

patterns-established:
  - "Three-tier authority pattern: DEFINITIVE > CONTEXTUAL > RAW INPUT in generation prompts"
  - "Hint loader auto-detection: Path.is_file() check before treating as inline text"
  - "Audit log pattern: FieldResolution per field, AuditEntry per section, AuditLog per job"

requirements-completed: [AUDP-04]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 6 Plan 02: Pipeline Integration Summary

**Three-tier prompt authority (DEFINITIVE/CONTEXTUAL/RAW INPUT) with hint loader, audit log, CLI --hints, and audio description pipeline integration -- 30 tests passing**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T03:44:06Z
- **Completed:** 2026-02-25T03:50:50Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Three-tier prompt restructuring with DEFINITIVE (user hints), CONTEXTUAL (audio analysis), and RAW INPUT (MIDI) authority labels, fully backward compatible
- Hint loader package with auto-detection of inline text vs file path, exported as load_hints()
- Audit log infrastructure with FieldResolution/AuditEntry/AuditLog dataclasses, writing structured JSON per job
- Pipeline integration wiring audio_description and user_hints through generate_section() and generate_from_midi()
- CLI --hints flag on generate command accepting inline text or .hints file paths
- 30 tests (6 hint loader, 5 audit log, 7 three-tier prompt, 3 integration, 9 existing prompt budget) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Hint loader, audit log, three-tier prompt restructuring** - `200990c` (feat)
2. **Task 2: Pipeline integration, CLI --hints, tests** - `7440239` (feat)

## Files Created/Modified
- `src/engrave/hints/__init__.py` - Package init exporting load_hints
- `src/engrave/hints/loader.py` - Hint loading with inline text vs file path auto-detection
- `src/engrave/generation/audit.py` - FieldResolution, AuditEntry, AuditLog dataclasses with JSON write
- `src/engrave/generation/prompts.py` - Three-tier prompt restructuring with audio_description and user_hints params
- `src/engrave/generation/pipeline.py` - Pipeline integration with audio description rendering, audit log, and hint passthrough
- `src/engrave/generation/__init__.py` - Updated exports with AuditLog, AuditEntry, FieldResolution
- `src/engrave/cli.py` - Added --hints option to generate command
- `tests/unit/test_hint_loader.py` - 6 tests for hint loading
- `tests/unit/test_audit.py` - 5 tests for audit log
- `tests/unit/test_prompt_budget.py` - 7 new three-tier prompt tests added
- `tests/integration/test_audio_generation.py` - 3 integration tests for audio+hints pipeline

## Decisions Made
- Three-tier prompt uses same template always, even for pure MIDI -- DEFINITIVE and CONTEXTUAL sections show "No user hints provided." and "No audio analysis available." as placeholder text
- Audio description and user hints are NEVER truncated (small, high-authority content) -- only MIDI, RAG, and coherence participate in budget fitting
- PromptBudget.safety_margin reduced from 4000 to 3200 to accommodate new description_tokens=800 field (per research pitfall #3)
- Audit log skeletal in Phase 6: hint_value always None (unstructured text), audio_value populated from AudioDescription section data
- MIDI/audio disagreements logged at WARNING level per user decision ("disagreement is the signal")
- Track summary rendered only for first section; matched section description rendered per section by bar range overlap

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Three-tier prompt structure ready for convergent sight-reading (Phase 7) where all three tiers will be populated
- Audit log infrastructure ready for per-field override tracking when hints become structured (future phase)
- CLI --hints flag operational for end-to-end testing with real audio + MIDI input
- 745 total tests passing (no regressions)

---
*Phase: 06-audio-understanding-hints*
*Completed: 2026-02-25*
