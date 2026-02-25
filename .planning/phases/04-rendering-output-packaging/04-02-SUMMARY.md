---
phase: 04-rendering-output-packaging
plan: 02
subsystem: rendering
tags: [lilypond, generator, transposition, conductor-score, parts, dynamic-restatement, tdd]

# Dependency graph
requires:
  - phase: 04-rendering-output-packaging
    provides: "BigBandPreset data model, InstrumentSpec, StaffGroupType, LilyPond stylesheet constants"
  - phase: 03-midi-to-lilypond-generation
    provides: "Concert-pitch LilyPond music variables consumed by generators"
provides:
  - "generate_music_definitions: shared music-definitions.ly with all concert-pitch variables"
  - "generate_conductor_score: tabloid landscape score with StaffGroup hierarchy, brackets/braces, ChordNames, MIDI"
  - "generate_part: transposed individual parts with compressMMRests, chord symbols for rhythm section"
  - "restate_dynamics: post-processor inserting dynamics at entrances after 2+ bars rest"
affects: [04-03-PLAN, 07-rendering-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Token-walking text processor for dynamic restatement (regex match at position)", "Section-grouped StaffGroup builder via itertools.groupby", "Slug helper for instrument-to-filename mapping"]

key-files:
  created:
    - src/engrave/rendering/generator.py
    - tests/unit/test_score_generator.py
    - tests/unit/test_part_generator.py
    - tests/unit/test_dynamic_restatement.py
    - tests/fixtures/sample_concert_pitch.ly
  modified:
    - src/engrave/rendering/__init__.py

key-decisions:
  - "restate_dynamics uses token-walking regex approach (not full LilyPond parser) for targeted dynamic/rest pattern recognition"
  - "Piano PianoStaff splits into upper (treble) and lower (bass) staves with separate variable references (piano, pianoLeft)"
  - "Non-transposing instruments (trombone, rhythm) omit \\transpose wrapper entirely rather than \\transpose c' c'"
  - "Conductor score uses concert pitch throughout with no \\transpose commands"

patterns-established:
  - "Generator functions return complete .ly source strings; no file I/O in generator module"
  - "Part slugification: lowercase + space-to-hyphen for ASCII instrument names"
  - "StaffGroup hierarchy built by grouping instruments by section via itertools.groupby"

requirements-completed: [ENGR-01, ENGR-02, ENGR-03, ENGR-04, ENSM-04]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 4 Plan 02: Score & Part Generators Summary

**LilyPond file generators producing conductor score with StaffGroup hierarchy, transposed instrument parts with compressMMRests and chord symbols, and dynamic restatement post-processing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T01:22:28Z
- **Completed:** 2026-02-25T01:27:58Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Conductor score generator with correct StaffGroup nesting (Saxophones/Trumpets/Trombones brackets, Rhythm brace), tabloid landscape, concert pitch, ChordNames, DrumStaff, PianoStaff, MIDI block, RemoveEmptyStaves
- Part generator with per-instrument transposition (Eb alto/bari, Bb tenor/trumpet, C trombones/rhythm), compressMMRests wrapping globalMusic in parallel, chord symbols on rhythm section only, studio mode variant
- Dynamic restatement post-processor tracking changing dynamic levels and inserting restatements at note entrances following 2+ bars of multi-measure rest
- 55 TDD tests covering score structure, transposition, chord symbols, special instruments, dynamic restatement edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Score and part generators with tests (TDD RED+GREEN)** - `fba580b` (feat)
2. **Task 2: Dynamic restatement post-processor with tests (TDD RED+GREEN)** - `3d43852` (feat)

## Files Created/Modified
- `src/engrave/rendering/generator.py` - Four public functions: generate_music_definitions, generate_conductor_score, generate_part, restate_dynamics
- `src/engrave/rendering/__init__.py` - Updated to re-export generator functions in package public API
- `tests/unit/test_score_generator.py` - 18 tests for conductor score and music definitions generation
- `tests/unit/test_part_generator.py` - 25 tests for part generation including transposition, chords, special instruments
- `tests/unit/test_dynamic_restatement.py` - 12 tests for dynamic restatement post-processing
- `tests/fixtures/sample_concert_pitch.ly` - Minimal concert-pitch fixture with globalMusic, chordSymbols, altoSaxOne, trumpetOne, guitar

## Decisions Made
- restate_dynamics uses a position-based regex token walker rather than a full LilyPond parser -- sufficient for recognizing dynamic markings and multi-measure rest patterns without the complexity of full grammar parsing
- Piano parts use PianoStaff with separate upper/lower staff references (pianoLeft variable for bass clef staff)
- Non-transposing instruments (trombones, rhythm section) omit the `\transpose` wrapper entirely rather than wrapping in `\transpose c' c'` which would be a no-op
- Conductor score contains no `\transpose` commands -- concert pitch throughout per SCORING_GUIDE.md

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All four generator public functions ready for Plan 04-03 (compilation and packaging)
- generate_music_definitions + generate_conductor_score + generate_part form the complete .ly file generation pipeline
- restate_dynamics available as a pre-processing step before file generation
- Package __init__.py exports all functions for convenient imports

## Self-Check: PASSED

- All 6 files verified on disk
- Both task commits found: `fba580b`, `3d43852`
- 55 tests pass in 0.03s

---
*Phase: 04-rendering-output-packaging*
*Completed: 2026-02-25*
