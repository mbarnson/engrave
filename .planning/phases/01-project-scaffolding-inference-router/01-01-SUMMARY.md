---
phase: 01-project-scaffolding-inference-router
plan: 01
subsystem: infra
tags: [python, uv, litellm, pydantic-settings, typer, ruff, pytest, pre-commit]

# Dependency graph
requires: []
provides:
  - "Installable Python package with src/engrave layout and uv"
  - "Settings loading from engrave.toml + .env with env var override"
  - "InferenceRouter for role-based LLM dispatch via LiteLLM"
  - "CLI entry point with check, version, compile commands"
  - "Dev toolchain: ruff, pytest, pre-commit, Makefile"
affects: [all-subsequent-phases, 01-02-lilypond-compiler]

# Tech tracking
tech-stack:
  added: [litellm, pydantic-settings, typer, rich, ruff, pytest, pytest-asyncio, pytest-bdd, pytest-cov, pre-commit, hatchling]
  patterns: [role-based-inference-routing, toml-plus-env-config, provider-prefix-model-strings, fail-dont-fallback]

key-files:
  created:
    - src/engrave/config/settings.py
    - src/engrave/config/roles.py
    - src/engrave/llm/router.py
    - src/engrave/llm/exceptions.py
    - src/engrave/cli.py
    - engrave.toml
    - pyproject.toml
    - Makefile
    - tests/conftest.py
    - tests/unit/test_config.py
    - tests/unit/test_router.py
  modified: []

key-decisions:
  - "Used hatchling as build backend with src layout"
  - "pydantic-settings v2 requires settings_customise_sources for TOML -- not just model_config toml_file"
  - "TestSettings subclass pattern for test isolation of TOML path"
  - "typer (not typer[all]) -- the [all] extra no longer exists in typer 0.24.x"
  - "Lazy imports in CLI commands for fast startup"

patterns-established:
  - "Role-based routing: code calls router.complete(role=...), never LiteLLM directly"
  - "Config priority: env vars > .env > engrave.toml > defaults"
  - "Provider prefix model strings: lm_studio/, anthropic/, openai/, hosted_vllm/"
  - "Fail-don't-fallback: num_retries=0, ProviderError on any failure"
  - "Test fixture pattern: _make_settings_class() for custom TOML paths"

requirements-completed: [FNDN-04]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 1 Plan 01: Project Scaffolding & Inference Router Summary

**Role-based LLM routing via LiteLLM with pydantic-settings TOML config, Typer CLI, and full dev toolchain (ruff, pytest, pre-commit, Makefile)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-24T23:14:37Z
- **Completed:** 2026-02-24T23:20:08Z
- **Tasks:** 2
- **Files modified:** 23

## Accomplishments
- Installable Python package with `uv pip install -e .` and `engrave` CLI command
- InferenceRouter dispatches LLM calls by pipeline role (compile_fixer, generator, describer) to configured provider+model via LiteLLM
- Settings loads from engrave.toml + .env with correct priority chain (env vars > .env > TOML > defaults)
- 17 unit tests pass at 91% coverage, ruff clean, pre-commit hooks active

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding and configuration system** - `6486c55` (feat)
2. **Task 2: Inference router and CLI entry point** - `c9c1d6b` (feat)

## Files Created/Modified
- `pyproject.toml` - Project metadata, deps, ruff/pytest/coverage config
- `src/engrave/__init__.py` - Package init with version
- `src/engrave/config/__init__.py` - Config module re-export
- `src/engrave/config/settings.py` - Pydantic-settings models loading engrave.toml + .env
- `src/engrave/config/roles.py` - Role-to-model resolution with context window validation
- `src/engrave/llm/__init__.py` - LLM module init
- `src/engrave/llm/router.py` - InferenceRouter wrapping LiteLLM with role-based dispatch
- `src/engrave/llm/exceptions.py` - ProviderError and RoleNotFoundError with diagnostics
- `src/engrave/lilypond/__init__.py` - LilyPond module init (placeholder for Plan 02)
- `src/engrave/cli.py` - Typer CLI with check, version, compile (stub) commands
- `engrave.toml` - Runtime config with provider endpoints and role mappings
- `engrave.toml.example` - Documented example config for new developers
- `.env.example` - Template for API keys
- `.gitignore` - Python, LilyPond, IDE, OS exclusions
- `.pre-commit-config.yaml` - Ruff and uv-lock pre-commit hooks
- `Makefile` - setup, test, lint, format targets
- `README.md` - Minimal project readme (required by hatchling)
- `tests/conftest.py` - Shared fixtures: tmp_engrave_toml, settings, mock_acompletion
- `tests/unit/test_config.py` - 8 tests for config loading, env override, role validation
- `tests/unit/test_router.py` - 9 tests for router resolution, completion, error handling
- `uv.lock` - Dependency lockfile

## Decisions Made
- **hatchling build backend**: Needed for src layout support with uv. Works out of the box with `[tool.hatch.build.targets.wheel] packages = ["src/engrave"]`
- **settings_customise_sources**: pydantic-settings v2.13 requires explicit TomlConfigSettingsSource via the `settings_customise_sources` classmethod -- the `model_config = SettingsConfigDict(toml_file=...)` alone is insufficient without this hook
- **TestSettings subclass pattern**: Tests use `_make_settings_class(toml_path)` to create Settings subclasses pointing at tmp TOML files, avoiding global state pollution
- **typer (not typer[all])**: The `[all]` extra was removed in typer 0.24.x; typer now includes Rich/shellingham by default
- **Lazy imports in CLI**: CLI commands import heavy modules (litellm, settings, router) inside function bodies to keep `engrave --help` fast

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added README.md required by hatchling**
- **Found during:** Task 1 (uv sync)
- **Issue:** hatchling build backend requires README.md to exist when `readme = "README.md"` is in pyproject.toml
- **Fix:** Created minimal README.md with project description
- **Files modified:** README.md
- **Verification:** uv sync completes successfully
- **Committed in:** 6486c55 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed typer[all] extra no longer exists**
- **Found during:** Task 1 (uv sync)
- **Issue:** typer 0.24.x removed the `[all]` extra; `uv sync` warned about it
- **Fix:** Changed dependency from `typer[all]` to `typer`
- **Files modified:** pyproject.toml
- **Verification:** uv sync completes without warnings
- **Committed in:** 6486c55 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed pydantic-settings TOML source configuration**
- **Found during:** Task 1 (test_config.py failures)
- **Issue:** `SettingsConfigDict(toml_file=...)` alone does not register a TOML source in pydantic-settings v2.13; requires `settings_customise_sources` classmethod
- **Fix:** Added `settings_customise_sources` to Settings class with explicit TomlConfigSettingsSource; created `_make_settings_class()` test helper
- **Files modified:** src/engrave/config/settings.py, tests/conftest.py, tests/unit/test_config.py
- **Verification:** All 8 config tests pass
- **Committed in:** 6486c55 (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Project foundation complete: installable package, config system, inference router, dev toolchain
- Ready for Plan 02: LilyPond compiler wrapper, error parser, compile-fix retry loop
- LilyPond binary not yet installed (`brew install lilypond` needed before Plan 02 integration tests)

## Self-Check: PASSED

All 12 key files verified present. Both commit hashes (6486c55, c9c1d6b) confirmed in git log.

---
*Phase: 01-project-scaffolding-inference-router*
*Completed: 2026-02-24*
