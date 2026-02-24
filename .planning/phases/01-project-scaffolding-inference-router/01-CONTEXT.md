# Phase 1: Project Scaffolding & Inference Router - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Python project structure with CLI entry point, multi-provider LLM routing via LiteLLM, LilyPond installation and subprocess compilation, and a compile-check-fix retry loop that feeds LilyPond errors back to the LLM. This phase delivers the foundation that all subsequent phases build on.

</domain>

<decisions>
## Implementation Decisions

### LLM Provider Config
- Local-first: default to LMStudio/Ollama local endpoint on M4 Max 128GB. Cloud APIs are benchmarking tools, not the default path
- Fail, don't fallback: if the configured provider fails, surface the error. User explicitly switches providers. No silent fallback
- RunPod (or similar serverless GPU) is a first-class named provider alongside local, Anthropic, and OpenAI
- Config split: API keys in .env (gitignored), provider/model/endpoint settings in engrave.toml (committed)
- Role-based model mapping: config defines roles (e.g., `compile_fixer`, `generator`, `describer`) that map to provider+model. Swap models by changing one config line, not code
- Lightweight model validation per role: each role specifies minimum context window and optional capability tags. Config validation warns if assigned model likely doesn't fit

### Compile-Fix Loop
- Error context: feed the LilyPond error message plus ~20 lines around the error location back to the LLM. Not the full source
- Strict musical preservation: the fix must keep all notes, articulations, dynamics intact. Only fix syntax/structural errors. If it can't fix without changing music, fail
- Fail with diagnostics after 5 attempts: report the original error, what fixes were tried, and the final state
- Early exit on repeated errors: track error hashes across attempts. If the same error appears twice, stop early instead of burning remaining retries. Include in diagnostics

### Project Structure
- Flat src layout: `src/engrave/` with modules like `llm/`, `lilypond/`, `config/`
- CLI via click or typer: installable command (e.g., `engrave compile test.ly`) via `uv pip install -e .`
- TOML config: `pyproject.toml` for project metadata, `engrave.toml` for runtime config (providers, models, endpoints)
- Testing: pytest with fixtures for mocking LLM responses and LilyPond compilation. Tests run without API keys or LilyPond installed
- Gherkin integration tests: pytest-bdd with `.feature` files for any scenario expressible as given/when/then. Integration tests, not unit tests
- Code coverage: 80% minimum enforced via `make test --cov-fail-under=80`, not pre-commit (too slow for commit hook)
- Linting: Ruff for both formatting and linting (replaces black + flake8)
- Pre-commit hook: runs ruff check --fix, ruff format (no pytest — coverage enforced in make test)
- Setup: `make setup` installs deps, sets up pre-commit hooks, verifies LilyPond. Single command onboarding for developers and agents

### LilyPond Setup
- OS-aware installation: `make setup` detects OS — `brew install lilypond` on macOS, `apt-get install lilypond` on Linux
- glibc vs musl detection: `make setup` detects glibc vs musl (Alpine/busybox) for correct binary/wheel handling on Linux
- Minimum version: LilyPond >= 2.24 (current stable). Setup warns/fails on older versions
- Subprocess wrapper: thin Python wrapper around `subprocess.run(['lilypond', ...])`. Captures stdout/stderr, parses error output, returns structured results

### Model Philosophy
- Open-weight preferred: avoid hard dependencies on closed-weight models. Every pipeline role should have an open-weight option that runs locally
- Local-first on M4 Max 128GB for development. RunPod/serverless GPU for models that don't fit locally. Cloud APIs (Anthropic, OpenAI) only as quality ceiling benchmarks
- Generic role references in planning docs: REQUIREMENTS.md and ROADMAP.md should reference roles (e.g., "audio LM, open-weight preferred") not specific model names. Specific model picks happen during phase research, not in requirements
- The routing infrastructure must make model swapping trivial — the ML landscape moves fast

### Claude's Discretion
- Exact Ruff rule configuration
- click vs typer choice for CLI
- Internal module organization within the flat src layout
- Subprocess wrapper API design
- LilyPond error parsing implementation

</decisions>

<specifics>
## Specific Ideas

- "I'd prefer to be able to run these models locally on my M4 Max MacBook Pro with 128GB of VRAM, or else use inference on RunPod or the like with an open-weight model where possible"
- "A hard dependency on closed-weight models is concerning"
- RunPod as deployment target for demo to Sam — needs to work natively on Linux
- `make setup` should be the single command that gets any developer or agent from zero to running

</specifics>

<deferred>
## Deferred Ideas

- **Phase 0 prerequisite (DONE):** Updated ALL planning docs (ROADMAP.md, REQUIREMENTS.md, PROJECT.md, research/) with current model references. Qwen2-Audio → Qwen3-Omni-30B-A3B-Captioner, Gemini 2.5 Flash → Gemini 3 Flash. Added vllm-mlx for MoE inference on Apple Silicon. Added basic-pitch Python 3.10 venv hard constraint. Research docs note specific candidates; normative docs reference current models.
- Specific model benchmarking for compile-fix loop — belongs in Phase 1 research, not context
- CI/CD pipeline — not scoped for Phase 1

</deferred>

---

*Phase: 01-project-scaffolding-inference-router*
*Context gathered: 2026-02-24*
