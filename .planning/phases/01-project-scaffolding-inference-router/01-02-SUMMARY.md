---
phase: 01-project-scaffolding-inference-router
plan: 02
subsystem: lilypond
tags: [lilypond, subprocess, error-parsing, compile-fix-loop, tdd, pytest-bdd, gherkin, typer, rich]

# Dependency graph
requires:
  - phase: 01-project-scaffolding-inference-router
    provides: "InferenceRouter, Settings, CLI entry point, dev toolchain"
provides:
  - "LilyPondCompiler: subprocess wrapper with binary resolution"
  - "parse_lilypond_errors: structured error parsing from stderr"
  - "compile_with_fix_loop: 5-attempt retry with error hash deduplication"
  - "CLI compile command with --fix/--no-fix, --max-attempts, --role"
  - "Gherkin integration tests for compile-fix behavior"
affects: [03-lilypond-generation, all-compile-dependent-phases]

# Tech tracking
tech-stack:
  added: []
  patterns: [compile-fix-loop, error-hash-deduplication, context-window-extraction, strict-musical-preservation-prompt]

key-files:
  created:
    - src/engrave/lilypond/compiler.py
    - src/engrave/lilypond/parser.py
    - src/engrave/lilypond/fixer.py
    - tests/unit/test_compiler.py
    - tests/unit/test_parser.py
    - tests/unit/test_fixer.py
    - tests/integration/test_compile_fix_loop.py
    - tests/integration/features/compile_fix_loop.feature
    - tests/fixtures/valid.ly
    - tests/fixtures/broken.ly
    - tests/fixtures/error_outputs/missing_brace.txt
    - tests/fixtures/error_outputs/unknown_command.txt
  modified:
    - src/engrave/cli.py
    - tests/conftest.py

key-decisions:
  - "Error context window: ~20 lines centered on error line, full source also included in prompt for complete return"
  - "fix prompt includes full source alongside context snippet so LLM can return corrected complete file"
  - "extract_lilypond_from_response handles markdown code blocks, generic code blocks, and plain text"
  - "Repeated error hash detection after first occurrence triggers early loop exit"

patterns-established:
  - "Compile-fix loop: compile -> parse errors -> hash stderr -> extract context -> LLM fix -> retry"
  - "Error hash deduplication: SHA256 of stderr, early exit if hash already seen"
  - "Context extraction: ~20 lines centered on error line with line numbers and >> marker"
  - "Strict musical preservation prompt: explicit instruction to never change notes/articulations/dynamics"
  - "Mock compiler/router fixtures in conftest.py for testing without real LilyPond or LLM"

requirements-completed: [FNDN-05]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 1 Plan 02: LilyPond Compile-Fix Loop Summary

**LilyPond subprocess compiler, structured error parser, and 5-attempt compile-fix retry loop with error hash deduplication, wired through CLI**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-24T23:29:44Z
- **Completed:** 2026-02-24T23:35:46Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- LilyPondCompiler resolves binary via shutil.which + fallback paths, compiles via subprocess with --loglevel=ERROR --pdf, handles timeout gracefully
- parse_lilypond_errors() parses filename:line:col:severity:message format into structured LilyPondError dataclasses, handling error/warning/fatal error
- compile_with_fix_loop retries up to 5 times with error hash deduplication for early exit, feeds ~20 lines of context to LLM with strict musical preservation prompt
- CLI `engrave compile` command with --fix/--no-fix, --max-attempts, --role options and Rich diagnostics output
- 42 tests pass (25 new: 8 parser, 6 compiler, 7 fixer unit, 4 Gherkin integration) at 95% coverage

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: LilyPond compiler wrapper and error parser**
   - RED: `21b687e` (test) - failing tests for compiler and parser
   - GREEN: `4f03d1b` (feat) - implement compiler wrapper and error parser
2. **Task 2: Compile-fix retry loop, Gherkin integration tests, CLI wiring**
   - RED: `72577c5` (test) - failing tests for compile-fix loop
   - GREEN: `8cf0404` (feat) - implement compile-fix loop with CLI wiring

## Files Created/Modified
- `src/engrave/lilypond/compiler.py` - LilyPondCompiler: subprocess wrapper with binary resolution, timeout handling
- `src/engrave/lilypond/parser.py` - LilyPondError dataclass, parse_lilypond_errors with regex pattern
- `src/engrave/lilypond/fixer.py` - compile_with_fix_loop, extract_error_context, build_fix_prompt, extract_lilypond_from_response
- `src/engrave/cli.py` - Updated compile command stub with full pipeline wiring
- `tests/unit/test_compiler.py` - 6 tests: success, failure, binary resolution (3), timeout
- `tests/unit/test_parser.py` - 8 tests: single/multiple/warning/fatal/no errors, fixtures
- `tests/unit/test_fixer.py` - 7 tests: success, fix, early exit, max attempts, unparseable, context, prompt
- `tests/integration/test_compile_fix_loop.py` - 4 Gherkin scenarios with step definitions
- `tests/integration/features/compile_fix_loop.feature` - BDD feature file for compile-fix behavior
- `tests/conftest.py` - Added mock_compiler and mock_router fixtures
- `tests/fixtures/valid.ly` - Known-good LilyPond source
- `tests/fixtures/broken.ly` - Deliberately broken LilyPond (missing brace)
- `tests/fixtures/error_outputs/missing_brace.txt` - Captured LilyPond error output
- `tests/fixtures/error_outputs/unknown_command.txt` - Captured LilyPond error output

## Decisions Made
- **Error context includes full source in prompt**: The ~20-line context window centers around the error for focused attention, but the full source is also provided so the LLM can return a complete corrected file. This follows the plan's build_fix_prompt(source_context, errors, original_source) signature.
- **Code block extraction from LLM responses**: extract_lilypond_from_response handles ```lilypond, ```ly, generic ```, and plain text responses to be robust against varying LLM output formats.
- **Repeated hash triggers immediate exit**: When the same stderr hash is seen a second time, the loop records the attempt and breaks immediately rather than wasting another LLM call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_error_context_extracted assertion**
- **Found during:** Task 2 (fixer GREEN phase)
- **Issue:** Test asserted total prompt length < 80 lines, but prompt correctly includes full source alongside context window. The plan specifies both source_context and original_source as prompt parameters.
- **Fix:** Changed assertion to verify the CONTEXT AROUND ERROR section specifically contains ~20 lines, not the total prompt length.
- **Files modified:** tests/unit/test_fixer.py
- **Verification:** Test passes, correctly validates context window is ~20 lines
- **Committed in:** 8cf0404 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test assertion)
**Impact on plan:** Test correction only. No functional changes to implementation.

## Issues Encountered
None beyond the auto-fixed test assertion above.

## User Setup Required
None - all tests mock subprocess and LLM. No LilyPond binary or API keys needed for test execution.

## Next Phase Readiness
- Phase 1 complete: project scaffolding, inference router, and compile-fix pipeline all in place
- Ready for Phase 2: MIDI-to-LilyPond generation pipeline
- LilyPond binary not yet installed on development machine (`brew install lilypond` needed for real compilation)
- All tests pass without external dependencies (fully mocked)

## Self-Check: PASSED

All 15 key files verified present. All 4 commit hashes (21b687e, 4f03d1b, 72577c5, 8cf0404) confirmed in git log.

---
*Phase: 01-project-scaffolding-inference-router*
*Completed: 2026-02-24*
