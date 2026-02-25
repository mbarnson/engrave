---
phase: 03-midi-to-lilypond-generation
plan: 01
subsystem: midi
tags: [mido, pretty_midi, midi-parsing, tokenization, section-detection, lilypond-pitch]

# Dependency graph
requires:
  - phase: 01-project-scaffolding-inference-router
    provides: "Project structure, pyproject.toml, ruff config, pytest setup"
provides:
  - "MIDI type 0 and type 1 loading with channel splitting and track normalization"
  - "Musical analysis (key estimation, tempo, time sig, instrument detection) via pretty_midi"
  - "Human-readable MIDI-to-text tokenization with LilyPond absolute pitch naming"
  - "Section boundary detection with priority chain (markers > time sig > key sig > tempo > fixed)"
  - "Full 128-entry General MIDI instrument name lookup table"
affects: [03-02-PLAN, 03-03-PLAN, generation-pipeline, prompt-construction]

# Tech tracking
tech-stack:
  added: [mido 1.3.3, pretty_midi 0.2.11, pytest-timeout 2.4.0]
  patterns: [TDD RED-GREEN, dataclass-based domain models, Krumhansl-Kessler key profiles, priority-chain boundary detection]

key-files:
  created:
    - src/engrave/midi/__init__.py
    - src/engrave/midi/loader.py
    - src/engrave/midi/analyzer.py
    - src/engrave/midi/tokenizer.py
    - src/engrave/midi/sections.py
    - tests/unit/test_midi_loader.py
    - tests/unit/test_midi_analyzer.py
    - tests/unit/test_midi_tokenizer.py
    - tests/unit/test_midi_sections.py
    - tests/fixtures/generate_midi_fixtures.py
    - tests/fixtures/simple_type0.mid
    - tests/fixtures/simple_type1.mid
    - tests/fixtures/no_metadata.mid
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "NoteEvent velocity stored from note_on event (not note_off) for accurate dynamics"
  - "Krumhansl-Kessler major/minor profiles for key estimation via chroma correlation"
  - "Sharps-only pitch naming (no enharmonic context yet) -- matches LilyPond default"
  - "LilyPond absolute octave convention: c (no mark) = MIDI octave 4 (48-59)"
  - "Velocity-to-dynamic threshold mapping with hysteresis (>8 velocity change required)"
  - "Section boundaries deduplicated by bar number, highest priority wins"
  - "Programmatic MIDI fixture generation for deterministic, small test files"

patterns-established:
  - "TDD RED-GREEN-REFACTOR cycle with separate commits per phase"
  - "Programmatic test fixture generation (tests/fixtures/generate_midi_fixtures.py)"
  - "Dataclass domain models (NoteEvent, MidiTrackInfo, MidiAnalysis, SectionBoundary)"
  - "Priority-chain pattern for multi-source boundary detection"

requirements-completed: [FNDN-01, LILY-01]

# Metrics
duration: 8min
completed: 2026-02-25
---

# Phase 3 Plan 1: MIDI Subsystem Summary

**MIDI type 0/1 loading with channel splitting, Krumhansl-Kessler key estimation, LilyPond absolute-pitch tokenization, and priority-chain section boundary detection**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-25T00:46:03Z
- **Completed:** 2026-02-25T00:54:28Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- MIDI type 0 files split by channel into separate tracks with GM instrument lookup; type 1 files parsed per-track with track_name and program_change extraction
- Musical analysis via pretty_midi extracts key (Krumhansl-Kessler), tempo, time signatures, instruments, and bar count
- Text tokenization produces bar-by-bar output with LilyPond absolute pitch names, quantized durations (including dotted), dynamic changes, and explicit rests
- Section boundary detection scans for rehearsal marks, time sig changes, key sig changes, tempo changes (>10%), with fixed-length fallback and short-section merging
- 32 unit tests across 4 test files, all passing with ruff clean

## Task Commits

Each task was committed atomically (TDD RED then GREEN):

1. **Task 1: MIDI loader and analyzer** - `8a79eb7` (test: RED), `722f8b4` (feat: GREEN)
2. **Task 2: MIDI tokenizer and section detection** - `c881609` (test: RED), `2c4b841` (feat: GREEN)

## Files Created/Modified
- `src/engrave/midi/__init__.py` - Package init re-exporting full public API
- `src/engrave/midi/loader.py` - MIDI loading, type 0 channel splitting, type 1 track parsing, GM instrument table
- `src/engrave/midi/analyzer.py` - Musical analysis via pretty_midi with Krumhansl-Kessler key estimation
- `src/engrave/midi/tokenizer.py` - MIDI-to-text tokenization for LLM prompts with LilyPond pitch/duration conventions
- `src/engrave/midi/sections.py` - Section boundary detection with priority chain and merging
- `tests/unit/test_midi_loader.py` - 11 unit tests for loader (type 0/1, drums, timing, edge cases)
- `tests/unit/test_midi_analyzer.py` - 7 unit tests for analyzer (tempo, time sig, key, instruments, bars)
- `tests/unit/test_midi_tokenizer.py` - 8 unit tests for tokenizer (pitch, duration, dotted, velocity, rests, bars)
- `tests/unit/test_midi_sections.py` - 6 unit tests for sections (fallback, markers, time sig, merging, priority)
- `tests/fixtures/generate_midi_fixtures.py` - Programmatic MIDI fixture generator
- `tests/fixtures/simple_type0.mid` - Type 0 fixture (piano + bass + drums)
- `tests/fixtures/simple_type1.mid` - Type 1 fixture (trumpet + trombone with marker)
- `tests/fixtures/no_metadata.mid` - No-metadata fixture (3/4 time, no track names)
- `pyproject.toml` - Added mido, pretty_midi, pytest-timeout dependencies

## Decisions Made
- NoteEvent stores velocity from the note_on event, not note_off, since note_off velocity is often zero and meaningless for dynamics
- Krumhansl-Kessler profiles chosen over pretty_midi's built-in key estimation for explicit control and LilyPond-formatted output
- Sharps-only pitch naming (c, cis, d, dis) without enharmonic spelling -- matches LilyPond default behavior; enharmonic context can be added later using key signature
- LilyPond absolute octave reference: c (no mark) = MIDI octave 4 (notes 48-59), c' = 60-71, c'' = 72-83, c, = 36-47
- Velocity-to-dynamic mapping uses hysteresis (8-unit threshold) to avoid spurious dynamic changes on slight velocity variations
- Section boundary deduplication keeps highest-priority boundary when multiple types occur at the same bar

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed pytest-timeout**
- **Found during:** Task 1 (RED phase test execution)
- **Issue:** Plan verification commands use `--timeout=30` but pytest-timeout not installed
- **Fix:** Added pytest-timeout to dev dependencies via `uv add --group dev pytest-timeout`
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** `uv run pytest --timeout=30` works
- **Committed in:** 8a79eb7 (Task 1 RED commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor -- missing dev dependency, no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- MIDI subsystem ready for consumption by generation pipeline (03-02, 03-03)
- `load_midi()` returns normalized tracks + metadata for any type 0 or type 1 file
- `analyze_midi()` provides key, tempo, time sig, instruments for prompt construction
- `tokenize_section_for_prompt()` produces bar-by-bar text for LLM prompt inclusion
- `detect_sections()` provides section boundaries for the section-by-section generation pipeline
- No blockers for next plan

## Self-Check: PASSED

All 13 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 03-midi-to-lilypond-generation*
*Completed: 2026-02-25*
