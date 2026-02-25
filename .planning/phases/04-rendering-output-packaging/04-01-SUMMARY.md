---
phase: 04-rendering-output-packaging
plan: 01
subsystem: rendering
tags: [lilypond, big-band, ensemble, transposition, dataclass, stylesheet]

# Dependency graph
requires:
  - phase: 03-midi-to-lilypond-generation
    provides: "Concert-pitch LilyPond source (music variables) consumed by rendering"
provides:
  - "BigBandPreset data model encoding 17 instruments with transposition, clef, section, score order"
  - "InstrumentSpec frozen dataclass for individual instrument configuration"
  - "StaffGroupType enum for conductor score bracket/brace grouping"
  - "LilyPond stylesheet constants for conductor score and individual parts"
  - "Studio mode layout variant for recording session bar numbering"
affects: [04-02-PLAN, 04-03-PLAN, 07-rendering-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Frozen dataclass ensemble preset as structured data model", "Raw LilyPond string constants in stylesheet module"]

key-files:
  created:
    - src/engrave/rendering/__init__.py
    - src/engrave/rendering/ensemble.py
    - src/engrave/rendering/stylesheet.py
    - tests/unit/test_ensemble.py
  modified: []

key-decisions:
  - "Piano is a single InstrumentSpec with is_grand_staff=True (not two entries); generator handles PianoStaff context"
  - "Baritone sax transpose_to is 'a' (A below middle C), octave lower than alto's 'a'"
  - "Staff size 14 for conductor score via layout-set-staff-size (not set-global-staff-size) inside layout block"
  - "Header constants use Python format strings ({title}, {composer}) not Jinja templates"

patterns-established:
  - "Ensemble preset as frozen dataclass tuple: instruments stored in score order, immutable"
  - "Stylesheet constants as raw LilyPond text: generator interpolates around them"
  - "Rendering package under src/engrave/rendering/ with public API re-exports from __init__.py"

requirements-completed: [ENSM-01]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 4 Plan 01: Ensemble Preset & Stylesheet Summary

**BigBandPreset frozen dataclass with 17 instruments matching SCORING_GUIDE.md transposition table, plus LilyPond paper/layout stylesheet constants for conductor score and parts**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T01:16:03Z
- **Completed:** 2026-02-25T01:19:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- BigBandPreset data model with all 17 big band instruments in correct score order (Alto Sax 1 through Drums)
- Transposition intervals verified against SCORING_GUIDE.md: Eb alto/bari, Bb tenor/trumpet, C trombones/rhythm
- LilyPond stylesheet constants for conductor score (tabloid landscape, staff size 14, RemoveEmptyStaves) and parts (letter portrait, bar numbers at system start)
- Studio mode layout variant with bar numbers on every measure for recording sessions
- 65 unit tests covering instrument count, score order, transposition, sections, clefs, chord symbols, variable names, frozen behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: BigBandPreset data model with tests (TDD RED+GREEN)** - `074aecb` (feat)
2. **Task 2: LilyPond stylesheet constants** - `ab2bebf` (feat)

## Files Created/Modified
- `src/engrave/rendering/__init__.py` - Package init re-exporting all public API from ensemble and stylesheet
- `src/engrave/rendering/ensemble.py` - StaffGroupType enum, InstrumentSpec dataclass, BigBandPreset dataclass, BIG_BAND constant
- `src/engrave/rendering/stylesheet.py` - CONDUCTOR_SCORE_PAPER/LAYOUT/HEADER, PART_PAPER/LAYOUT/HEADER, STUDIO_LAYOUT, VERSION_HEADER
- `tests/unit/test_ensemble.py` - 65 parametrized unit tests for ensemble preset data model

## Decisions Made
- Piano represented as single InstrumentSpec with `is_grand_staff=True` flag; PianoStaff two-staff rendering deferred to generator (Plan 04-02)
- Baritone sax `transpose_to="a"` (not `"a'"`) to achieve correct octave below alto transposition
- Conductor score staff size 14 set inside `\layout` block via `#(layout-set-staff-size 14)` for per-score control
- Header templates use Python `str.format()` placeholders, not Jinja2, keeping the dependency footprint minimal

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- BigBandPreset and stylesheet constants ready for Plan 04-02 (LilyPond file generators)
- Generator can iterate `BIG_BAND.instruments` for score ordering, part file generation, and transposition
- Stylesheet constants provide all paper/layout blocks needed by score and part .ly files

## Self-Check: PASSED

- All 4 created files verified on disk
- Both task commits found: `074aecb`, `ab2bebf`
- 65 tests pass in 0.03s

---
*Phase: 04-rendering-output-packaging*
*Completed: 2026-02-25*
