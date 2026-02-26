---
phase: quick-1
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/engrave/config/settings.py
  - src/engrave/config/roles.py
  - engrave.toml
  - engrave.toml.example
  - tests/conftest.py
  - tests/unit/test_config.py
autonomous: true
requirements: [QUICK-1]

must_haves:
  truths:
    - "RoleConfig no longer accepts or stores min_context_window"
    - "No context window estimation or warning logic exists in roles.py"
    - "TOML configs contain no min_context_window lines"
    - "All existing tests pass after removal"
  artifacts:
    - path: "src/engrave/config/settings.py"
      provides: "RoleConfig without min_context_window field"
    - path: "src/engrave/config/roles.py"
      provides: "Role resolution without context window estimation"
    - path: "engrave.toml"
      provides: "Runtime config without min_context_window"
    - path: "engrave.toml.example"
      provides: "Example config without min_context_window"
    - path: "tests/conftest.py"
      provides: "MINIMAL_TOML without min_context_window"
    - path: "tests/unit/test_config.py"
      provides: "Config tests without context window warning test"
  key_links: []
---

<objective>
Remove the min_context_window field and all context window estimation logic from the codebase.

Purpose: Context window estimation was removed as a design decision -- the server rejects requests that exceed context, making client-side guessing unnecessary and misleading (especially for local models where the guess was a bogus 32K default).
Output: Clean codebase with no traces of context window estimation.
</objective>

<execution_context>
@/Users/patbarnson/.claude/get-shit-done/workflows/execute-plan.md
@/Users/patbarnson/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/engrave/config/settings.py
@src/engrave/config/roles.py
@engrave.toml
@engrave.toml.example
@tests/conftest.py
@tests/unit/test_config.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove context window logic from source and config files</name>
  <files>
    src/engrave/config/settings.py
    src/engrave/config/roles.py
    engrave.toml
    engrave.toml.example
  </files>
  <action>
    In src/engrave/config/settings.py:
    - Remove line 51: `min_context_window: int = 8000` from the RoleConfig class

    In src/engrave/config/roles.py:
    - Remove `import warnings` (line 6) -- no longer used after removing the warning
    - Remove the entire `KNOWN_CONTEXT_WINDOWS` dict (lines 14-21)
    - Remove the entire `_estimate_context_window()` function (lines 24-29)
    - In `validate_and_resolve_roles()`, remove the context window validation block (lines 80-86: the `estimated = ...` call, the `if estimated ...` block, and the `warnings.warn(...)` call)
    - Update the docstring of `validate_and_resolve_roles()` (line 68) to remove step 2 about context window warning. The docstring should list only: 1. Resolve api_base/api_key from the matching provider config, 2. Log the resolved configuration

    In engrave.toml:
    - Remove `min_context_window = 32000` from [roles.compile_fixer] (line 16)
    - Remove `min_context_window = 32000` from [roles.generator] (line 22)
    - Remove `min_context_window = 16000` from [roles.describer] (line 28)

    In engrave.toml.example:
    - Remove `min_context_window = 32000` from [roles.compile_fixer] (line 26)
    - Remove `min_context_window = 65000` from [roles.generator] (line 31)
    - Remove `min_context_window = 16000` from [roles.describer] (line 36)
  </action>
  <verify>uv python -c "from engrave.config.settings import RoleConfig; r = RoleConfig(model='test/m'); assert not hasattr(r, 'min_context_window') or 'min_context_window' not in RoleConfig.model_fields"</verify>
  <done>No references to min_context_window, KNOWN_CONTEXT_WINDOWS, or _estimate_context_window exist in src/ or config files</done>
</task>

<task type="auto">
  <name>Task 2: Update test fixtures and remove context window test</name>
  <files>
    tests/conftest.py
    tests/unit/test_config.py
  </files>
  <action>
    In tests/conftest.py:
    - Remove `min_context_window = 32000` from the MINIMAL_TOML string (line 30, inside the [roles.compile_fixer] block)

    In tests/unit/test_config.py:
    - Remove `import warnings` (line 5) -- no longer used
    - Remove the entire `test_warns_on_insufficient_context_window` method (lines 84-94) from TestRoleValidation class
  </action>
  <verify>cd /Users/patbarnson/devel/engrave && uv run pytest tests/unit/test_config.py -x -v</verify>
  <done>All config tests pass, no context window test exists, no warnings import in test_config.py</done>
</task>

</tasks>

<verification>
cd /Users/patbarnson/devel/engrave && uv run pytest tests/unit/test_config.py -x -v && uv run python -c "from engrave.config.roles import validate_and_resolve_roles; print('Import OK, no context window logic')"
</verification>

<success_criteria>
- RoleConfig.model_fields does not contain min_context_window
- roles.py has no KNOWN_CONTEXT_WINDOWS, _estimate_context_window, or warnings import
- engrave.toml and engrave.toml.example have no min_context_window lines
- MINIMAL_TOML in conftest.py has no min_context_window
- test_warns_on_insufficient_context_window test is gone
- All existing tests in test_config.py pass
</success_criteria>

<output>
After completion, create `.planning/quick/1-remove-min-context-window-field-and-all-/1-01-SUMMARY.md`
</output>
