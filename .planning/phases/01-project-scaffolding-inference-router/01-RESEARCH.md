# Phase 1: Project Scaffolding & Inference Router - Research

**Researched:** 2026-02-24
**Domain:** Python project scaffolding, multi-provider LLM routing, LilyPond subprocess compilation, compile-check-fix retry loop
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Local-first: default to LMStudio/Ollama local endpoint on M4 Max 128GB. Cloud APIs are benchmarking tools, not the default path
- Fail, don't fallback: if the configured provider fails, surface the error. User explicitly switches providers. No silent fallback
- RunPod (or similar serverless GPU) is a first-class named provider alongside local, Anthropic, and OpenAI
- Config split: API keys in .env (gitignored), provider/model/endpoint settings in engrave.toml (committed)
- Role-based model mapping: config defines roles (e.g., `compile_fixer`, `generator`, `describer`) that map to provider+model. Swap models by changing one config line, not code
- Lightweight model validation per role: each role specifies minimum context window and optional capability tags. Config validation warns if assigned model likely doesn't fit
- Error context: feed the LilyPond error message plus ~20 lines around the error location back to the LLM. Not the full source
- Strict musical preservation: the fix must keep all notes, articulations, dynamics intact. Only fix syntax/structural errors. If it can't fix without changing music, fail
- Fail with diagnostics after 5 attempts: report the original error, what fixes were tried, and the final state
- Early exit on repeated errors: track error hashes across attempts. If the same error appears twice, stop early instead of burning remaining retries. Include in diagnostics
- Flat src layout: `src/engrave/` with modules like `llm/`, `lilypond/`, `config/`
- CLI via click or typer: installable command (e.g., `engrave compile test.ly`) via `uv pip install -e .`
- TOML config: `pyproject.toml` for project metadata, `engrave.toml` for runtime config (providers, models, endpoints)
- Testing: pytest with fixtures for mocking LLM responses and LilyPond compilation. Tests run without API keys or LilyPond installed
- Gherkin integration tests: pytest-bdd with `.feature` files for any scenario expressible as given/when/then. Integration tests, not unit tests
- Code coverage: 80% minimum enforced in pre-commit hook, excluding entrypoints
- Linting: Ruff for both formatting and linting (replaces black + flake8)
- Pre-commit hook: runs ruff check --fix, ruff format, pytest on changed files, coverage check
- Setup: `make setup` installs deps, sets up pre-commit hooks, verifies LilyPond. Single command onboarding for developers and agents
- OS-aware installation: `make setup` detects OS -- `brew install lilypond` on macOS, `apt-get install lilypond` on Linux
- glibc vs musl detection: `make setup` detects glibc vs musl (Alpine/busybox) for correct binary/wheel handling on Linux
- Minimum version: LilyPond >= 2.24 (current stable). Setup warns/fails on older versions
- Subprocess wrapper: thin Python wrapper around `subprocess.run(['lilypond', ...])`. Captures stdout/stderr, parses error output, returns structured results
- Open-weight preferred: avoid hard dependencies on closed-weight models
- Local-first on M4 Max 128GB for development. RunPod/serverless GPU for models that don't fit locally. Cloud APIs (Anthropic, OpenAI) only as quality ceiling benchmarks
- Generic role references in planning docs: reference roles not model names. Specific picks during research
- The routing infrastructure must make model swapping trivial

### Claude's Discretion
- Exact Ruff rule configuration
- click vs typer choice for CLI
- Internal module organization within the flat src layout
- Subprocess wrapper API design
- LilyPond error parsing implementation

### Deferred Ideas (OUT OF SCOPE)
- Specific model benchmarking for compile-fix loop -- belongs in later phase research
- CI/CD pipeline -- not scoped for Phase 1
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FNDN-04 | System supports multiple LLM providers (Anthropic API, OpenAI API, LMStudio local) via LiteLLM, configurable per pipeline stage | LiteLLM provider configuration, role-based model mapping, engrave.toml config design, async completion API |
| FNDN-05 | System provides a compile-check-fix retry loop that detects LilyPond compilation errors, feeds them back to the LLM, and retries up to 5 times | LilyPond CLI error output format, subprocess wrapper design, error parsing regex patterns, retry loop architecture with error hash deduplication |
</phase_requirements>

## Summary

Phase 1 delivers the two foundational subsystems that every subsequent phase depends on: a unified multi-provider LLM inference router and a LilyPond compile-check-fix loop. The inference router wraps LiteLLM to provide role-based model mapping (e.g., `compile_fixer` maps to a specific provider+model), configured via `engrave.toml` with secrets in `.env`. The compile-fix loop runs LilyPond as a subprocess, parses structured error output (filename:line:column format on stderr), extracts ~20 lines of context around the error, feeds this to the LLM for correction, and retries up to 5 times with early exit on repeated error hashes.

The project scaffolding uses `uv init --package engrave` to create a `src/engrave/` layout, with `pyproject.toml` for metadata and build configuration, `engrave.toml` for runtime config via pydantic-settings `TomlConfigSettingsSource`, and Ruff for linting/formatting. The CLI uses Typer (recommendation -- see rationale below). Testing uses pytest for unit tests and pytest-bdd for Gherkin integration tests. A `Makefile` provides `make setup` as the single onboarding command.

**Primary recommendation:** Use LiteLLM `acompletion()` for all LLM calls, Typer for CLI, pydantic-settings with TOML for config, and `subprocess.run()` with `capture_output=True` for LilyPond invocation. Design the error parser as a standalone function that returns structured `CompileResult` objects.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LiteLLM | latest (1.x, Feb 2026) | Unified multi-provider LLM interface | Wraps 100+ providers in OpenAI-compatible format. 8ms P95 overhead. Supports Anthropic, OpenAI, LM Studio, vLLM/RunPod via `openai/`, `anthropic/`, `lm_studio/`, `hosted_vllm/` prefixes. Async via `acompletion()`. |
| pydantic-settings | 2.x | Configuration management | Native TOML support via `TomlConfigSettingsSource`. Priority chain: env vars > .env > TOML > defaults. Nested config models for provider/role mapping. |
| pydantic | 2.12.x | Data validation | Required by pydantic-settings. Defines structured types for config, compile results, error reports. |
| Typer | 0.15.x | CLI framework | Built on Click, type-hint-driven, autocompletion, minimal boilerplate. Modern Python CLI standard. |
| Ruff | 0.14.x | Linting + formatting | Replaces black + isort + flake8. Single tool, extremely fast (10-100x). |
| pytest | 8.x | Unit testing | Standard Python test framework. Fixtures for mocking LLM responses and LilyPond. |
| pytest-bdd | 8.1.x | Gherkin integration tests | Pytest plugin for .feature files. No separate runner. Fixtures via dependency injection. |
| pytest-cov | latest | Coverage reporting | Enforces 80% minimum. Integrates with pre-commit. |
| pre-commit | latest | Git hooks | Runs ruff, pytest, coverage on commit. |
| LilyPond | 2.24.4 | Music engraving CLI | Stable release. Available via `brew install lilypond` (confirmed: Homebrew has 2.24.4). |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | latest | .env file loading | Loading API keys from .env into environment. pydantic-settings uses this internally. |
| openai | 2.23.0 | OpenAI SDK | Transitive dependency of LiteLLM. Also used directly if needed for LM Studio. |
| anthropic | 0.83.0 | Anthropic SDK | Transitive dependency of LiteLLM for Anthropic provider. |
| tomli | latest | TOML parsing (Python < 3.11) | Fallback for TOML parsing. Python 3.12 has built-in `tomllib`. |
| rich | latest | Terminal output | Pretty error reports, progress display for compile-fix loop. Typer uses Rich internally. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | Click | Click is lower-level, more decorators, no type-hint inference. Typer wraps Click, so all Click features remain accessible. Typer is recommended for new projects. |
| pydantic-settings TOML | Manual tomllib + dataclass | Loses validation, priority chain, nested models, .env integration. Not worth hand-rolling. |
| pytest-bdd | behave | behave requires its own runner, doesn't integrate with pytest fixtures. pytest-bdd is pytest-native. |
| Ruff | black + flake8 + isort | Three tools vs one. Ruff is strictly faster and covers all three. |

**Installation:**
```bash
# Initialize project
uv init --package engrave

# Core dependencies
uv add litellm pydantic-settings typer[all] rich

# Dev dependencies
uv add --dev ruff pytest pytest-bdd pytest-cov pre-commit

# System dependencies (macOS)
brew install lilypond
```

## Architecture Patterns

### Recommended Project Structure

```
engrave/
├── src/
│   └── engrave/
│       ├── __init__.py
│       ├── cli.py                  # Typer app entry point
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py         # Pydantic settings models (loads engrave.toml + .env)
│       │   └── roles.py            # Role -> provider+model mapping logic
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── router.py           # InferenceRouter wrapping LiteLLM
│       │   └── exceptions.py       # Mapped exceptions (provider-agnostic)
│       └── lilypond/
│           ├── __init__.py
│           ├── compiler.py         # Subprocess wrapper: run lilypond, capture output
│           ├── parser.py           # Error output parser: stderr -> structured errors
│           └── fixer.py            # Compile-check-fix retry loop
├── tests/
│   ├── conftest.py                 # Shared fixtures (mock LLM, mock lilypond)
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_router.py
│   │   ├── test_compiler.py
│   │   ├── test_parser.py
│   │   └── test_fixer.py
│   ├── integration/
│   │   ├── features/
│   │   │   ├── inference_routing.feature
│   │   │   └── compile_fix_loop.feature
│   │   ├── test_inference_routing.py
│   │   └── test_compile_fix_loop.py
│   └── fixtures/
│       ├── broken.ly               # Deliberately broken LilyPond for testing
│       ├── valid.ly                # Known-good LilyPond for testing
│       └── error_outputs/          # Captured lilypond stderr for parser tests
├── engrave.toml                    # Runtime config (committed)
├── engrave.toml.example            # Example config for new developers
├── .env.example                    # Example env vars (committed)
├── .env                            # Actual secrets (gitignored)
├── pyproject.toml                  # Project metadata, build config, ruff config
├── Makefile                        # make setup, make test, make lint, make compile
├── .pre-commit-config.yaml         # Pre-commit hook config
└── .gitignore
```

### Pattern 1: Role-Based Inference Router

**What:** A thin wrapper around LiteLLM that maps pipeline roles to provider+model combinations. Code calls `router.complete(role="compile_fixer", ...)` and the router resolves the role to the configured model string (e.g., `"anthropic/claude-sonnet-4-20250514"` or `"lm_studio/qwen3-coder-next"`).

**When to use:** Every LLM call in the system. Never call LiteLLM directly.

**Example:**
```python
# src/engrave/llm/router.py
from litellm import acompletion
from engrave.config.settings import Settings, RoleConfig

class InferenceRouter:
    """Route LLM calls by pipeline role, not provider."""

    def __init__(self, settings: Settings):
        self._roles: dict[str, RoleConfig] = settings.roles
        self._configure_providers(settings)

    async def complete(
        self,
        role: str,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> str:
        """Send completion request for a given pipeline role."""
        role_config = self._roles[role]
        model = role_config.model  # e.g., "anthropic/claude-sonnet-4-20250514"

        response = await acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or role_config.max_tokens,
            api_base=role_config.api_base,  # None for cloud, URL for local/RunPod
            api_key=role_config.api_key,    # From .env via settings
            num_retries=0,  # Fail, don't fallback -- user decision
        )
        return response.choices[0].message.content

    def _configure_providers(self, settings: Settings) -> None:
        """Set LiteLLM environment variables for providers."""
        import os
        if settings.providers.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.providers.anthropic_api_key
        if settings.providers.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.providers.openai_api_key
        if settings.providers.lm_studio_api_base:
            os.environ["LM_STUDIO_API_BASE"] = settings.providers.lm_studio_api_base
```

**Source:** [LiteLLM LM Studio docs](https://docs.litellm.ai/docs/providers/lm_studio), [LiteLLM OpenAI-compatible docs](https://docs.litellm.ai/docs/providers/openai_compatible)

### Pattern 2: Structured LilyPond Error Parsing

**What:** Parse LilyPond's stderr output into structured error objects. LilyPond errors follow the format `filename:lineno:columnno: errortype: message` followed by the offending source line with a position indicator.

**When to use:** Every LilyPond compilation. The parser feeds the compile-fix loop.

**Example:**
```python
# src/engrave/lilypond/parser.py
import re
from dataclasses import dataclass

@dataclass
class LilyPondError:
    """A single parsed error from LilyPond compilation."""
    file: str
    line: int
    column: int
    severity: str        # "error", "warning", "fatal error"
    message: str
    offending_line: str   # The source line that caused the error

# Pattern: filename:line:column: severity: message
ERROR_PATTERN = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<severity>error|warning|fatal error):\s+"
    r"(?P<message>.+)$"
)

def parse_lilypond_errors(stderr: str) -> list[LilyPondError]:
    """Parse LilyPond stderr into structured error objects."""
    errors = []
    lines = stderr.splitlines()
    for i, line in enumerate(lines):
        match = ERROR_PATTERN.match(line)
        if match:
            # Next line is typically the offending source line
            offending = lines[i + 1] if i + 1 < len(lines) else ""
            errors.append(LilyPondError(
                file=match.group("file"),
                line=int(match.group("line")),
                column=int(match.group("col")),
                severity=match.group("severity"),
                message=match.group("message"),
                offending_line=offending.strip(),
            ))
    return errors
```

**Source:** [LilyPond Error Messages](https://lilypond.org/doc/v2.24/Documentation/usage/error-messages), [LilyPond Common Errors](https://lilypond.org/doc/v2.24/Documentation/learning/some-common-errors)

### Pattern 3: Compile-Check-Fix Retry Loop

**What:** Compile LilyPond source, parse errors, extract context around the error, send to LLM for fix, and retry. Track error hashes for early exit on repeated errors.

**When to use:** Every LilyPond compilation that may contain LLM-generated code.

**Example:**
```python
# src/engrave/lilypond/fixer.py
import hashlib
from dataclasses import dataclass, field

@dataclass
class FixAttempt:
    """Record of a single fix attempt."""
    attempt_number: int
    error_hash: str
    error_message: str
    fix_applied: str

@dataclass
class CompileResult:
    """Result of compilation with fix loop."""
    success: bool
    output_path: str | None
    source: str                        # Final source (fixed or original)
    attempts: list[FixAttempt] = field(default_factory=list)
    final_errors: list[LilyPondError] = field(default_factory=list)

async def compile_with_fix_loop(
    source: str,
    router: InferenceRouter,
    compiler: LilyPondCompiler,
    max_attempts: int = 5,
    context_lines: int = 20,
) -> CompileResult:
    """Compile LilyPond with LLM-assisted error recovery."""
    seen_hashes: set[str] = set()
    attempts: list[FixAttempt] = []
    current_source = source

    for attempt_num in range(max_attempts):
        result = compiler.compile(current_source)
        if result.success:
            return CompileResult(
                success=True,
                output_path=result.output_path,
                source=current_source,
                attempts=attempts,
            )

        # Parse errors
        errors = parse_lilypond_errors(result.stderr)
        if not errors:
            break  # Unparseable error -- cannot fix

        # Early exit on repeated error
        error_hash = hashlib.sha256(
            result.stderr.encode()
        ).hexdigest()[:16]

        if error_hash in seen_hashes:
            break  # Same error repeated -- stop early
        seen_hashes.add(error_hash)

        # Extract context around first error
        error_context = extract_error_context(
            current_source, errors[0], context_lines
        )

        # Ask LLM to fix
        fix_prompt = build_fix_prompt(
            source_context=error_context,
            errors=errors,
            original_source=current_source,
        )

        fixed_source = await router.complete(
            role="compile_fixer",
            messages=[{"role": "user", "content": fix_prompt}],
            temperature=0.1,  # Low temperature for precise fixes
        )

        attempts.append(FixAttempt(
            attempt_number=attempt_num + 1,
            error_hash=error_hash,
            error_message=errors[0].message,
            fix_applied=f"LLM fix attempt {attempt_num + 1}",
        ))

        current_source = extract_lilypond_from_response(fixed_source)

    return CompileResult(
        success=False,
        output_path=None,
        source=current_source,
        attempts=attempts,
        final_errors=errors,
    )
```

### Pattern 4: TOML + .env Configuration

**What:** Split configuration into `engrave.toml` (committed, contains provider endpoints and role mappings) and `.env` (gitignored, contains API keys). Use pydantic-settings to load both with proper priority.

**When to use:** All configuration. Never hard-code provider details or API keys.

**Example:**
```toml
# engrave.toml
[providers.lm_studio]
api_base = "http://localhost:1234/v1"

[providers.runpod]
api_base = "https://api.runpod.ai/v2/your-endpoint-id/openai/v1"

[roles.compile_fixer]
model = "lm_studio/qwen3-coder-next"
max_tokens = 4096
min_context_window = 32000
tags = ["code"]

[roles.generator]
model = "lm_studio/qwen3-coder-next"
max_tokens = 8192
min_context_window = 65000
tags = ["code", "lilypond"]

[roles.describer]
model = "anthropic/claude-sonnet-4-20250514"
max_tokens = 2048
min_context_window = 16000
tags = ["audio", "description"]

[lilypond]
min_version = "2.24"
compile_timeout = 60
max_fix_attempts = 5
context_lines = 20
```

```python
# src/engrave/config/settings.py
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class ProviderConfig(BaseModel):
    api_base: str | None = None
    api_key: str | None = None

class RoleConfig(BaseModel):
    model: str
    max_tokens: int = 4096
    min_context_window: int = 8000
    tags: list[str] = []
    api_base: str | None = None
    api_key: str | None = None

class ProvidersConfig(BaseModel):
    lm_studio: ProviderConfig = ProviderConfig()
    runpod: ProviderConfig = ProviderConfig()
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

class LilyPondConfig(BaseModel):
    min_version: str = "2.24"
    compile_timeout: int = 60
    max_fix_attempts: int = 5
    context_lines: int = 20

class Settings(BaseSettings):
    providers: ProvidersConfig = ProvidersConfig()
    roles: dict[str, RoleConfig] = {}
    lilypond: LilyPondConfig = LilyPondConfig()

    model_config = SettingsConfigDict(
        toml_file="engrave.toml",
        env_file=".env",
        env_prefix="ENGRAVE_",
        env_nested_delimiter="__",
    )
```

**Source:** [pydantic-settings TOML docs](https://deepwiki.com/pydantic/pydantic-settings/3.2-configuration-files), [pydantic-settings official docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Anti-Patterns to Avoid

- **Direct LiteLLM calls scattered across modules:** All LLM calls must go through the `InferenceRouter`. This ensures role-based routing, consistent error handling, and trivial model swapping.
- **Parsing LilyPond stderr with string matching:** Use regex with named groups against the documented `filename:line:column: severity: message` format. Ad-hoc string splitting breaks on multi-line errors.
- **Silent provider fallback:** The user decision is explicit: fail, don't fallback. If LM Studio is down, raise an error. Don't silently fall back to Anthropic API.
- **Storing API keys in engrave.toml:** Keys go in `.env` only. `engrave.toml` is committed; `.env` is gitignored.
- **Running pytest on every pre-commit (full suite):** Only run tests on changed files during pre-commit. Full suite in CI or `make test`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-provider LLM routing | Custom HTTP clients per provider | LiteLLM | 100+ providers, streaming, async, error normalization. Months of work to replicate. |
| TOML + .env config with validation | Manual `tomllib` parsing + `os.environ` | pydantic-settings `TomlConfigSettingsSource` | Priority chain, nested models, type validation, env var override. 50+ edge cases handled. |
| CLI argument parsing | argparse | Typer | Type-hint inference, autocompletion, help generation, subcommands. |
| Python project packaging | Manual setup.py / pip | uv | 10-100x faster, lockfile, built-in venv, resolver, `uv run` for scripts. |
| Linting + formatting | black + flake8 + isort | Ruff | Single tool, faster, consistent config in pyproject.toml. |
| Git hooks | Manual .git/hooks scripts | pre-commit | Framework handles install, update, language environments. |
| BDD test runner | Custom Gherkin parser | pytest-bdd | Pytest-native, fixtures, step definitions, no separate runner. |

**Key insight:** Phase 1 is infrastructure. Every piece has mature, battle-tested solutions. The only novel code is the LilyPond error parser and the compile-fix loop orchestration -- everything else should be configuration of existing tools.

## Common Pitfalls

### Pitfall 1: LiteLLM Model String Format Varies by Provider
**What goes wrong:** Using wrong model string format causes silent failures or wrong provider routing. `"claude-sonnet-4-20250514"` routes differently from `"anthropic/claude-sonnet-4-20250514"`.
**Why it happens:** LiteLLM uses model string prefixes to select providers. Without the prefix, it guesses, often incorrectly.
**How to avoid:** Always use fully-qualified model strings with provider prefix: `anthropic/claude-*`, `openai/gpt-*`, `lm_studio/<model>`, `hosted_vllm/<model>`. Validate model strings in config loading.
**Warning signs:** Unexpected provider in logs, API key errors when using local models, responses from wrong model.

### Pitfall 2: LilyPond Writes Errors to Stderr AND Stdout
**What goes wrong:** Capturing only stderr misses some error information. LilyPond sends progress messages, warnings, and some error details to both streams.
**How to avoid:** Capture both stdout and stderr with `subprocess.run(capture_output=True, text=True)`. Parse both streams. Use `--loglevel=ERROR` to reduce noise: `lilypond --loglevel=ERROR --pdf -o output input.ly`.
**Warning signs:** Missing error context in fix prompts, "successful" compilations that actually failed.

### Pitfall 3: LilyPond Error Line Numbers Don't Match the Actual Problem
**What goes wrong:** The error message points to line N, but the actual problem is 1-2 lines above. This is documented LilyPond behavior.
**How to avoid:** When extracting context around an error, include lines ABOVE the reported line number (the ~20 line context window handles this). Don't assume the exact reported line is wrong.
**Warning signs:** LLM "fixes" the wrong line, error persists after fix attempt.

### Pitfall 4: pydantic-settings TOML Priority Surprise
**What goes wrong:** Environment variables silently override TOML values, or TOML doesn't load because `toml_file` path is relative to working directory, not project root.
**How to avoid:** Use absolute paths or `Path(__file__).parent` resolution for TOML file location. Document the priority chain: env vars > .env > TOML > defaults. Test config loading explicitly.
**Warning signs:** Config values different from what's in engrave.toml, working config breaks when running from different directory.

### Pitfall 5: Pre-commit Hook Runs Full Test Suite (Slow)
**What goes wrong:** Running all tests on every commit makes commits take 30+ seconds, developers skip hooks.
**How to avoid:** Pre-commit runs only: ruff check, ruff format, and a fast smoke test (e.g., `pytest tests/unit/ -x --timeout=10`). Full test suite runs via `make test` or CI.
**Warning signs:** Commits taking >10 seconds, developers running `git commit --no-verify`.

### Pitfall 6: LilyPond Not Found in subprocess PATH
**What goes wrong:** `subprocess.run(['lilypond', ...])` fails with FileNotFoundError because Homebrew's LilyPond is not in the subprocess PATH (e.g., when running inside a uv-managed venv).
**How to avoid:** In the compiler wrapper, resolve the LilyPond binary path at initialization time using `shutil.which('lilypond')`. Store the resolved path. Fall back to common locations (`/opt/homebrew/bin/lilypond`, `/usr/bin/lilypond`). Fail fast with a clear error if not found.
**Warning signs:** Tests pass locally but fail in clean environments, "command not found" errors.

### Pitfall 7: Async LiteLLM in Sync Test Context
**What goes wrong:** Tests using `acompletion()` fail because pytest doesn't handle async by default.
**How to avoid:** Use `pytest-asyncio` and mark async tests with `@pytest.mark.asyncio`. Or provide a sync wrapper for testing. Better: mock at the router level so tests never call LiteLLM directly.
**Warning signs:** "coroutine was never awaited" errors in tests, hanging test suite.

## Code Examples

### LilyPond Subprocess Compilation

```python
# src/engrave/lilypond/compiler.py
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RawCompileResult:
    """Raw result from lilypond subprocess."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    output_path: Path | None

class LilyPondCompiler:
    """Thin wrapper around the lilypond CLI."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.binary = self._find_binary()

    def _find_binary(self) -> str:
        """Resolve lilypond binary path."""
        path = shutil.which("lilypond")
        if path:
            return path
        # Common Homebrew locations
        for candidate in [
            "/opt/homebrew/bin/lilypond",
            "/usr/local/bin/lilypond",
            "/usr/bin/lilypond",
        ]:
            if Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "LilyPond not found. Install with: brew install lilypond"
        )

    def compile(self, source: str, output_dir: Path | None = None) -> RawCompileResult:
        """Compile LilyPond source to PDF."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".ly", mode="w", delete=False
        ) as f:
            f.write(source)
            input_path = Path(f.name)

        try:
            cmd = [
                self.binary,
                "--loglevel=ERROR",  # Reduce noise, keep errors
                "--pdf",
                "-o", str(output_dir or input_path.parent / input_path.stem),
                str(input_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output_pdf = (output_dir or input_path.parent) / f"{input_path.stem}.pdf"

            return RawCompileResult(
                success=result.returncode == 0 and output_pdf.exists(),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                output_path=output_pdf if output_pdf.exists() else None,
            )
        finally:
            input_path.unlink(missing_ok=True)
```

**Source:** [LilyPond CLI docs](https://lilypond.org/doc/v2.24/Documentation/usage/command_002dline-usage), [Python subprocess docs](https://docs.python.org/3/library/subprocess.html)

### Typer CLI Entry Point

```python
# src/engrave/cli.py
import typer
from pathlib import Path

app = typer.Typer(
    name="engrave",
    help="AI-powered music engraving pipeline",
)

@app.command()
def compile(
    input_file: Path = typer.Argument(..., help="LilyPond source file"),
    fix: bool = typer.Option(True, help="Enable LLM-assisted error fixing"),
    max_attempts: int = typer.Option(5, help="Max fix attempts"),
    role: str = typer.Option("compile_fixer", help="LLM role for fixing"),
) -> None:
    """Compile a LilyPond file to PDF with optional LLM error fixing."""
    import asyncio
    from engrave.config.settings import Settings
    from engrave.llm.router import InferenceRouter
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.lilypond.fixer import compile_with_fix_loop

    settings = Settings()
    source = input_file.read_text()

    if fix:
        router = InferenceRouter(settings)
        compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)
        result = asyncio.run(compile_with_fix_loop(
            source=source,
            router=router,
            compiler=compiler,
            max_attempts=max_attempts,
        ))
    else:
        compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)
        raw = compiler.compile(source)
        # ... handle raw result

@app.command()
def check(
    provider: str = typer.Argument(..., help="Provider to test: anthropic, openai, lm_studio"),
) -> None:
    """Test connectivity to an LLM provider."""
    # ... send test completion, report success/failure
```

**Source:** [Typer docs](https://typer.tiangolo.com/), [Typer features](https://typer.tiangolo.com/features/)

### pytest-bdd Integration Test Example

```gherkin
# tests/integration/features/compile_fix_loop.feature
Feature: Compile-fix retry loop
  The system compiles LilyPond and fixes errors via LLM

  Scenario: Successful compilation of valid LilyPond
    Given a valid LilyPond source
    When I compile the source
    Then the compilation succeeds
    And no fix attempts were made

  Scenario: LLM fixes a broken LilyPond file within 5 attempts
    Given a LilyPond source with a missing closing brace
    When I compile with the fix loop enabled
    Then the compilation succeeds after at most 5 attempts
    And the musical content is preserved

  Scenario: Early exit on repeated error
    Given a LilyPond source with an unfixable error
    And the LLM always returns the same broken code
    When I compile with the fix loop enabled
    Then the loop exits early before 5 attempts
    And the diagnostics show a repeated error hash
```

```python
# tests/integration/test_compile_fix_loop.py
from pytest_bdd import scenario, given, when, then, parsers
import pytest

@scenario("features/compile_fix_loop.feature", "LLM fixes a broken LilyPond file within 5 attempts")
def test_fix_broken():
    pass

@given("a LilyPond source with a missing closing brace", target_fixture="source")
def broken_source():
    return '\\version "2.24.4"\n\\relative c\' { c4 d e f\n'  # Missing }

@when("I compile with the fix loop enabled", target_fixture="result")
def compile_with_fix(source, mock_router, mock_compiler):
    import asyncio
    from engrave.lilypond.fixer import compile_with_fix_loop
    return asyncio.run(compile_with_fix_loop(
        source=source,
        router=mock_router,
        compiler=mock_compiler,
        max_attempts=5,
    ))

@then("the compilation succeeds after at most 5 attempts")
def check_success(result):
    assert result.success
    assert len(result.attempts) <= 5
```

**Source:** [pytest-bdd docs](https://pytest-bdd.readthedocs.io/en/latest/)

### Makefile Setup Target

```makefile
# Makefile
.PHONY: setup test lint compile check

PYTHON := python3
UV := uv

# Single-command onboarding
setup:
	@echo "=== Engrave Setup ==="
	# Install Python dependencies
	$(UV) sync
	# Install pre-commit hooks
	$(UV) run pre-commit install
	# Verify LilyPond
	@if command -v lilypond >/dev/null 2>&1; then \
		LILY_VERSION=$$(lilypond --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+'); \
		echo "LilyPond found: $$LILY_VERSION"; \
	else \
		echo "WARNING: LilyPond not found."; \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "Install with: brew install lilypond"; \
		elif [ -f /etc/alpine-release ] || busybox --help >/dev/null 2>&1; then \
			echo "Detected musl/Alpine. Install with: apk add lilypond"; \
		else \
			echo "Install with: sudo apt-get install lilypond"; \
		fi; \
	fi
	@echo "=== Setup Complete ==="

test:
	$(UV) run pytest tests/ -v --cov=engrave --cov-report=term-missing

lint:
	$(UV) run ruff check src/ tests/
	$(UV) run ruff format --check src/ tests/

format:
	$(UV) run ruff check --fix src/ tests/
	$(UV) run ruff format src/ tests/

compile:
	@echo "Usage: uv run engrave compile <file.ly>"
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.3
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.9.30
    hooks:
      - id: uv-lock
```

### Ruff Configuration in pyproject.toml

```toml
# In pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "RUF",  # ruff-specific rules
]
ignore = [
    "E501",  # line-length handled by formatter
]

[tool.ruff.lint.isort]
known-first-party = ["engrave"]
```

**Source:** [Ruff configuration docs](https://docs.astral.sh/ruff/configuration/), [Ruff tutorial](https://docs.astral.sh/ruff/tutorial/)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip + venv + setup.py | uv + pyproject.toml + uv_build | 2024-2025 | 10-100x faster, lockfile, built-in venv, `uv run` |
| black + flake8 + isort | Ruff | 2023-2024 | Single tool, faster, unified config |
| argparse / Click decorators | Typer type hints | 2020+, matured 2024 | Less boilerplate, autocompletion, Click compatibility |
| Manual .env parsing | pydantic-settings v2 with TOML | 2024-2025 | Type-safe, priority chain, nested models, TOML native |
| Direct provider SDKs | LiteLLM unified interface | 2023+, now 100+ providers | One API, all providers, async, streaming, error normalization |
| LilyPond 2.22 | LilyPond 2.24.4 (stable) | 2023 | Current stable. 2.25.x is dev branch for Abjad compat. |

**Deprecated/outdated:**
- `setup.py` / `setup.cfg`: Replaced by `pyproject.toml` + build backends (uv_build, hatchling, etc.)
- `black` / `flake8` / `isort` as separate tools: Ruff covers all three
- `behave` for BDD: pytest-bdd integrates with pytest natively; behave requires its own runner

## Open Questions

1. **LilyPond error output to stderr vs stdout**
   - What we know: Errors follow `filename:line:col: severity: message` format. LilyPond has `--loglevel` flag.
   - What's unclear: Exact split between stderr and stdout varies by LilyPond version. Some progress messages go to stdout, errors to stderr, but this is not formally documented.
   - Recommendation: Capture both streams with `capture_output=True`. Parse both. Use `--loglevel=ERROR` to minimize noise.

2. **RunPod endpoint as LiteLLM provider**
   - What we know: RunPod vLLM workers expose OpenAI-compatible endpoints. LiteLLM supports `hosted_vllm/` prefix or generic `openai/` with custom `api_base`.
   - What's unclear: Exact RunPod endpoint URL format for serverless, authentication header format (RunPod uses `Bearer` token in `Authorization` header, same as OpenAI).
   - Recommendation: Configure RunPod as `openai/<model-name>` with `api_base` pointing to RunPod endpoint and `api_key` set to RunPod API key. Test during implementation.

3. **pytest-bdd `bdd_features_base_dir` with src layout**
   - What we know: Default is relative to current module path. Can be overridden in pytest.ini.
   - What's unclear: Whether `features/` inside `tests/integration/` works seamlessly with `uv run pytest`.
   - Recommendation: Set `bdd_features_base_dir = tests/integration/features` in `pyproject.toml` under `[tool.pytest.ini_options]`.

4. **Coverage enforcement in pre-commit**
   - What we know: User wants 80% minimum in pre-commit hook, excluding entrypoints.
   - What's unclear: Whether running full coverage check in pre-commit is too slow for a good developer experience.
   - Recommendation: Run coverage in `make test`, not pre-commit. Pre-commit should be fast (<10s). Enforce coverage in CI or as a separate `make check-coverage` target.

## Sources

### Primary (HIGH confidence)
- [LiteLLM Official Docs](https://docs.litellm.ai/docs/) - Provider configuration, completion API, error handling
- [LiteLLM LM Studio Provider](https://docs.litellm.ai/docs/providers/lm_studio) - LM Studio model naming and configuration
- [LiteLLM OpenAI-Compatible Endpoints](https://docs.litellm.ai/docs/providers/openai_compatible) - Custom endpoint configuration for vLLM/RunPod
- [LiteLLM Exception Mapping](https://docs.litellm.ai/docs/exception_mapping) - Error types and retry strategies
- [LilyPond CLI Usage (v2.24)](https://lilypond.org/doc/v2.24/Documentation/usage/command_002dline-usage) - Command-line options, loglevel, output formats
- [LilyPond Error Messages (v2.24)](https://lilypond.org/doc/v2.24/Documentation/usage/error-messages) - Error output format specification
- [LilyPond Common Errors (v2.24)](https://lilypond.org/doc/v2.24/Documentation/learning/some-common-errors) - Frequent error patterns
- [uv Project Creation](https://docs.astral.sh/uv/concepts/projects/init/) - `--package` flag, src layout
- [uv Pre-commit Integration](https://docs.astral.sh/uv/guides/integration/pre-commit/) - uv-lock hook, uv-pre-commit
- [Ruff Configuration](https://docs.astral.sh/ruff/configuration/) - pyproject.toml config, rule selection
- [Ruff Tutorial](https://docs.astral.sh/ruff/tutorial/) - Setup and usage guide
- [pydantic-settings TOML](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - TomlConfigSettingsSource, priority chain
- [pydantic-settings Configuration Files](https://deepwiki.com/pydantic/pydantic-settings/3.2-configuration-files) - TOML integration details
- [pytest-bdd Docs (v8.1)](https://pytest-bdd.readthedocs.io/en/latest/) - Setup, step definitions, fixtures, feature file config
- [Typer Features](https://typer.tiangolo.com/features/) - Type-hint CLI, autocompletion
- [Python subprocess Docs](https://docs.python.org/3/library/subprocess.html) - capture_output, text mode

### Secondary (MEDIUM confidence)
- [LiteLLM Completion Input Params](https://docs.litellm.ai/docs/completion/input) - Full parameter list
- [RunPod OpenAI Compatibility](https://docs.runpod.io/serverless/vllm/openai-compatibility) - vLLM endpoint format
- [LilyPond Error/Warning Output (Contributor Guide)](https://lilypond.org/doc/v2.24/Documentation/contributor/warnings-errors-progress-and-debug-output) - Internal error handling details
- [Homebrew LilyPond formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/l/lilypond.rb) - Confirmed v2.24.4 available

### Tertiary (LOW confidence)
- [python-ly GitHub](https://github.com/frescobaldi/python-ly) - Potential for pre-compilation syntax validation (v0.9.5, stable but not actively developed). May be useful for brace-matching before invoking LilyPond, but needs validation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs, versions confirmed on PyPI/Homebrew
- Architecture: HIGH - Patterns follow LiteLLM docs, LilyPond CLI documented behavior, pydantic-settings official examples
- Pitfalls: HIGH - LilyPond error format verified in official docs, LiteLLM model strings verified, pre-commit patterns verified

**Environment verified:**
- Python 3.13.5 installed (will use 3.12 for project via uv -- 3.13 not yet fully supported by PyTorch ecosystem)
- uv 0.9.30 installed
- Ruff 0.14.3 installed
- LilyPond 2.24.4 available via Homebrew (not yet installed)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, monthly refresh adequate)
