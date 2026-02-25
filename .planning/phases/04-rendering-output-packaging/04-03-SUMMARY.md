---
phase: 04-rendering-output-packaging
plan: 03
subsystem: rendering
tags: [lilypond, render-pipeline, zip-packaging, cli, compilation, python-slugify]

# Dependency graph
requires:
  - phase: 04-rendering-output-packaging
    provides: "BigBandPreset data model, InstrumentSpec, LilyPond generators (generate_music_definitions, generate_conductor_score, generate_part, restate_dynamics)"
  - phase: 01-project-skeleton
    provides: "LilyPondCompiler for .ly -> PDF compilation"
provides:
  - "RenderPipeline: orchestrates .ly generation, LilyPond compilation, and ZIP packaging"
  - "RenderResult: dataclass tracking compiled/failed files and error messages"
  - "CLI render command: engrave render <dir> [--output] [--title] for end-to-end rendering"
  - "ZIP output: flat archive with score.pdf, 17 part PDFs, all .ly sources, and MIDI"
affects: [05-audio-understanding, 07-convergent-sight-reading]

# Tech tracking
tech-stack:
  added: [python-slugify]
  patterns: ["RenderPipeline orchestration with graceful compilation failure handling", "ZIP packaging with flat structure and date-stamped naming", "CLI render command with lazy imports and exit code semantics"]

key-files:
  created:
    - src/engrave/rendering/packager.py
    - tests/unit/test_packager.py
    - tests/integration/test_packaging.py
  modified:
    - src/engrave/rendering/__init__.py
    - src/engrave/cli.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "python-slugify for Unicode-safe song title slugification (song titles may contain diacritics, unlike ASCII instrument names)"
  - "RenderPipeline sets compiler.timeout before each compile call (300s for score, 60s for parts)"
  - "Partial compilation: failed parts logged and excluded from ZIP PDFs, but .ly source files always included"
  - "CLI render command reads music-definitions.ly with regex variable extraction as placeholder until Phase 3 assembler produces dict[str, str] directly"

patterns-established:
  - "RenderPipeline.render() returns RenderResult dataclass with success/failed/errors for downstream reporting"
  - "ZIP naming: {slugified-title}-{YYYY-MM-DD}.zip with python-slugify for Unicode handling"
  - "CLI exit code semantics: 0 = all compiled, 1 = score failed, 2 = some parts failed"

requirements-completed: [FNDN-06, ENGR-09]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 4 Plan 03: Render Pipeline & ZIP Packaging Summary

**RenderPipeline orchestrating .ly generation, LilyPond compilation, and ZIP packaging with CLI render command, graceful partial-failure handling, and python-slugify for Unicode-safe filenames**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T01:31:28Z
- **Completed:** 2026-02-25T01:37:10Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- RenderPipeline class connecting generators (04-02) to compiler (Phase 1) producing complete ZIP packages with score.pdf, 17 part PDFs, all .ly source files, and MIDI output
- Graceful compilation failure handling: failed parts logged and excluded from PDF output, but .ly sources always included; pipeline never crashes on individual part failures
- CLI `engrave render` command with progress reporting, exit code semantics (0/1/2), and regex-based music-definitions.ly parsing as placeholder interface
- 13 new tests (11 unit + 2 integration) all passing; full suite at 386 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: RenderPipeline and ZIP packager with tests** - `1ea9e69` (feat)
2. **Task 2: CLI render command and integration test** - `38a2f66` (feat)

## Files Created/Modified
- `src/engrave/rendering/packager.py` - RenderPipeline class and RenderResult dataclass; _slugify_title using python-slugify; _package_zip with flat ZIP structure
- `tests/unit/test_packager.py` - 11 unit tests covering ZIP contents, filename patterns, title resolution, compilation failure handling, and timeout semantics
- `tests/integration/test_packaging.py` - 2 integration tests for full pipeline success and partial failure scenarios
- `src/engrave/rendering/__init__.py` - Re-exports RenderPipeline and RenderResult in package public API
- `src/engrave/cli.py` - CLI `render` command with --output and --title options, lazy imports, and exit code semantics
- `pyproject.toml` - Added python-slugify dependency
- `uv.lock` - Updated lockfile with python-slugify and text-unidecode

## Decisions Made
- Used python-slugify (not simple regex) for song title slugification because song titles may contain Unicode, diacritics, and special characters that instrument names never have
- RenderPipeline mutates compiler.timeout before score vs part compilation calls (300s vs 60s) rather than creating separate compiler instances
- Partial compilation produces a ZIP that still includes all .ly source files even for failed parts, since the source is useful for debugging
- CLI render command uses regex-based variable extraction from music-definitions.ly as a placeholder -- Phase 3's assembler will eventually produce the dict[str, str] of music variables directly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 complete: full rendering pipeline from ensemble presets through compilation to ZIP packaging
- RenderPipeline available via `from engrave.rendering import RenderPipeline, BIG_BAND`
- CLI `engrave render` ready for end-to-end testing with real LilyPond
- Pipeline is the final assembly stage consuming Phase 3 generation output and Phase 1 compiler

## Self-Check: PASSED

- All 7 files verified on disk
- Both task commits found: `1ea9e69`, `38a2f66`
- 386 tests pass in 7.89s

---
*Phase: 04-rendering-output-packaging*
*Completed: 2026-02-25*
