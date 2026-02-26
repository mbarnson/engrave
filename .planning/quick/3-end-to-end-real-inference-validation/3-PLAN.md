---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/engrave/cli.py
  - src/engrave/generation/pipeline.py
  - src/engrave/smoke/runner.py
  - src/engrave/web/app.py
  - src/engrave/llm/router.py
  - src/engrave/lilypond/fixer.py
  - src/engrave/generation/assembler.py
  - src/engrave/generation/prompts.py
  - src/engrave/config/settings.py
  - src/engrave/config/roles.py
  - engrave.toml
  - tests/conftest.py
  - tests/unit/test_config.py
  - tests/unit/test_router.py
autonomous: false
requirements: [E2E-VALIDATION]

must_haves:
  truths:
    - "engrave check generator returns real LLM content (not mocked, not null)"
    - "engrave generate on inmood.mid produces a directory with LilyPond source"
    - "engrave generate on chattanooga.mid also produces LilyPond source"
    - "engrave render produces a ZIP containing score.pdf with real notation"
    - "engrave smoke-test passes all 9 checks on all 3 MIDI files"
    - "The web UI accepts a MIDI upload and produces a downloadable ZIP"
    - "No mocks used anywhere in the process"
  artifacts:
    - path: "jobs/e2e-test/smoke-results.json"
      provides: "Final smoke test JSON report"
    - path: "test-fixtures/.smoke/inmood/"
      provides: "Smoke artifacts for inmood.mid"
    - path: "test-fixtures/.smoke/chattanooga/"
      provides: "Smoke artifacts for chattanooga.mid"
    - path: "test-fixtures/.smoke/bigband/"
      provides: "Smoke artifacts for bigband.mid"
  key_links:
    - from: "src/engrave/cli.py (generate command)"
      to: "src/engrave/generation/pipeline.py (generate_from_midi)"
      via: "asyncio.run(generate_from_midi(...))"
      pattern: "asyncio\\.run.*generate_from_midi"
    - from: "src/engrave/generation/pipeline.py"
      to: "src/engrave/llm/router.py"
      via: "router.complete() with real vllm-mlx inference"
      pattern: "router\\.complete"
    - from: "src/engrave/smoke/runner.py"
      to: "src/engrave/generation/pipeline.py"
      via: "_run_midi_pipeline calls generate_from_midi"
      pattern: "generate_from_midi"
---

<objective>
Run the Engrave pipeline end-to-end with REAL LLM inference (Qwen3-Coder-30B via vllm-mlx), fix every crash encountered, and produce verified output artifacts that prove the pipeline works on real MIDI input.

Purpose: Every test in the project uses mocked LLM responses. This task validates the REAL pipeline produces REAL sheet music PDFs. Every bug fixed here is one fewer bug a human tester hits.

Output: Verified smoke-results.json with all checks passing, ZIP files with real PDFs, web UI confirmed working.
</objective>

<execution_context>
@/Users/patbarnson/.claude/get-shit-done/workflows/execute-plan.md
@/Users/patbarnson/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/end-to-end-real-inference-validation.md
@.planning/phases/07.1-minimal-ui-for-uat-needs/.continue-here.md

Key source files (read as needed when fixing crashes):
@src/engrave/cli.py
@src/engrave/generation/pipeline.py
@src/engrave/smoke/runner.py
@src/engrave/web/app.py
@src/engrave/llm/router.py
@src/engrave/lilypond/fixer.py
@src/engrave/generation/assembler.py
@src/engrave/generation/prompts.py
@src/engrave/config/settings.py
@engrave.toml

Previous progress context:
- vllm-mlx is running with Qwen3-Coder-30B-A3B-Instruct-4bit-dwq-v2 on port 8000
- `engrave check generator` NOW PASSES (null content blocker resolved)
- Sampling params configured in engrave.toml (temp=0.7, top_p=0.8, top_k=20, min_p=0.0)
- Previous smoke run produced artifacts in test-fixtures/.smoke/ for all 3 MIDI files
- Previous smoke-results.json in jobs/e2e-test/ shows 27/27 passing (but inmood shows 1.82s elapsed which is suspiciously fast -- could be cached artifacts, needs fresh run)
- Web app job directories exist in jobs/ from previous manual testing
- Test MIDI files: test-fixtures/inmood.mid, test-fixtures/chattanooga.mid, test-fixtures/bigband.mid
</context>

<tasks>

<task type="auto">
  <name>Task 1: Verify prerequisites and run CLI generate+render on inmood.mid</name>
  <files>
    src/engrave/cli.py
    src/engrave/generation/pipeline.py
    src/engrave/llm/router.py
    src/engrave/lilypond/fixer.py
    src/engrave/generation/assembler.py
    src/engrave/generation/prompts.py
    engrave.toml
  </files>
  <action>
IMPORTANT: This is a pipeline VALIDATION task. You are running real commands with a real LLM producing real output. Long inference times (5-60 minutes per MIDI file on 30B model) are expected and normal. Use 600000ms timeouts for inference commands.

Step 1 - Verify prerequisites:
```bash
lilypond --version
curl -s http://localhost:8000/v1/models | python3 -m json.tool
uv run engrave check generator
```
All three must succeed. If `engrave check generator` fails, diagnose: check engrave.toml [roles.generator] model matches what vllm-mlx reports. The model should be `hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit-dwq-v2`. If vllm-mlx is not running but LM Studio is on port 1234, update engrave.toml roles to use `lm_studio/` prefix and port 1234.

Step 2 - Verify test MIDI files exist:
```bash
ls -la test-fixtures/inmood.mid test-fixtures/chattanooga.mid test-fixtures/bigband.mid
```
All three should exist and be non-zero.

Step 3 - Run CLI generate on inmood.mid (the smallest file, fastest to debug):
```bash
mkdir -p jobs/e2e-test/inmood-cli-fresh/
uv run engrave generate test-fixtures/inmood.mid --output jobs/e2e-test/inmood-cli-fresh/inmood.ly --verbose --no-rag
```
Use 600000ms timeout. This runs REAL inference through vllm-mlx. Expect 5-20 minutes.

If it crashes, read the error, fix the source code, and re-run. Common failure modes:
- LLM returns content the parser cannot extract -> fix extract_lilypond_from_response in fixer.py
- Template variable mismatch -> fix parse_instrument_blocks in templates.py
- Section detection produces 0 sections -> check detect_sections on this MIDI
- CLI passes wrong args to generate_from_midi -> fix cli.py generate command
- LLM returns empty or null -> check router.py complete() handles None content

IMPORTANT: The `generate` CLI command writes a single .ly file (not a directory). Check cli.py line 328: output_path defaults to input with .ly extension, or uses --output if provided. The --output flag takes a FILE path, not directory. So use:
```bash
uv run engrave generate test-fixtures/inmood.mid --output jobs/e2e-test/inmood-cli-fresh/inmood.ly --verbose --no-rag
```
Create the output directory first: `mkdir -p jobs/e2e-test/inmood-cli-fresh/`

Step 4 - Render the output to ZIP:
```bash
uv run engrave render jobs/e2e-test/inmood-cli-fresh/ --title "In The Mood"
```
The render command reads .ly files from the input directory. If music-definitions.ly does not exist, it falls back to the first .ly file found. It extracts variables via regex and either routes through RenderPipeline (if variables match BIG_BAND preset) or does standalone compilation.

If render fails, read the error and fix. Common failure modes:
- No music variables extracted from the .ly file -> the regex `^(\w+)\s*=\s*\{` may not match the assembled output format
- LilyPond compilation errors -> the generated code has syntax issues the fix loop did not catch
- Variable names do not match BIG_BAND preset -> render falls back to standalone compilation, which is fine

Step 5 - Verify the output:
```bash
ls -la jobs/e2e-test/inmood-cli-fresh/*.zip 2>/dev/null || ls -la *.zip 2>/dev/null
```
The ZIP should contain at least score.ly. If compilation succeeded, it also contains a PDF.

After each fix, also run the unit tests to ensure no regressions:
```bash
uv run pytest tests/unit/ -x -q
```
  </action>
  <verify>
```bash
# Check the .ly file was generated
test -f jobs/e2e-test/inmood-cli-fresh/inmood.ly && echo "PASS: .ly file exists"
# Check it has content (not empty)
test -s jobs/e2e-test/inmood-cli-fresh/inmood.ly && echo "PASS: .ly file has content"
# Check unit tests still pass
uv run pytest tests/unit/ -x -q
```
  </verify>
  <done>
- `engrave check generator` passes with real vllm-mlx inference
- `engrave generate test-fixtures/inmood.mid` produces a non-empty .ly file
- `engrave render` produces a ZIP (or standalone compile succeeds)
- Unit tests pass (no regressions from any fixes)
  </done>
</task>

<task type="auto">
  <name>Task 2: Run full smoke test suite and verify web UI</name>
  <files>
    src/engrave/smoke/runner.py
    src/engrave/web/app.py
    src/engrave/generation/pipeline.py
  </files>
  <action>
IMPORTANT: Long inference times expected. Use 600000ms timeouts.

Step 1 - Clear previous smoke artifacts and run fresh smoke test:

The smoke runner creates job directories under test-fixtures/.smoke/{stem}/ for each input. Previous run results exist but the inmood result (1.82s) looks suspiciously fast -- it may have reused cached artifacts. Run fresh:

```bash
rm -rf test-fixtures/.smoke/
uv run engrave smoke-test test-fixtures/ --json jobs/e2e-test/smoke-results-fresh.json
```

This will run all 3 MIDI files (inmood, chattanooga, bigband) through the full pipeline with real inference. Expect 30-120+ minutes total on a 30B model.

NOTE: If a fresh run is impractical due to time constraints (each file takes 10-40 min of inference), and the previous smoke-results.json already shows 27/27 passing with non-trivial elapsed times for bigband (2517s) and chattanooga (8959s), you MAY use the existing results. The key validation is that the smoke artifacts (ZIPs with PDFs) exist and are real. Verify:

```bash
# Check existing artifacts are real (non-trivial file sizes)
ls -la test-fixtures/.smoke/bigband/*.zip test-fixtures/.smoke/chattanooga/*.zip test-fixtures/.smoke/inmood/*.zip
# Verify PDFs inside ZIPs
uv run python -c "
import zipfile
from pathlib import Path
for d in ['bigband', 'chattanooga', 'inmood']:
    zips = list(Path(f'test-fixtures/.smoke/{d}').glob('*.zip'))
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            sizes = {n: zf.getinfo(n).file_size for n in names}
            print(f'{z.name}: {sizes}')
"
```

If any ZIP is empty or contains 0-byte PDFs, the smoke artifacts are invalid and a fresh run IS required.

Step 2 - Copy final smoke results to the canonical location:
```bash
cp jobs/e2e-test/smoke-results-fresh.json jobs/e2e-test/smoke-results.json 2>/dev/null || true
```
(Or if using existing results, verify jobs/e2e-test/smoke-results.json exists and has 0 failures.)

Step 3 - Verify the web UI works:

Start the web server on port 8001 (since vllm-mlx uses 8000):
```bash
uv run engrave serve --port 8001 &
WEB_PID=$!
sleep 3
```

Test the endpoints programmatically:
```bash
# Test home page loads
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/
# Should return 200

# Test file upload with inmood.mid
curl -s -X POST http://127.0.0.1:8001/engrave -F "file=@test-fixtures/inmood.mid" -F "hints=" -o /tmp/engrave_upload_response.html -w "%{http_code}"
# Should return 200 with htmx polling div

# Extract job_id from response
cat /tmp/engrave_upload_response.html
```

The web UI starts a background asyncio task that runs the full pipeline. For a REAL inference test, this would take 10+ minutes. Instead, verify the upload endpoint accepts the file and returns a processing status:

```bash
# Check status endpoint works (should show "processing" since pipeline is running)
# Extract job_id from the HTML response (pattern: /status/XXXXXXXX)
JOB_ID=$(grep -oP 'status/\K[a-f0-9]+' /tmp/engrave_upload_response.html | head -1)
if [ -n "$JOB_ID" ]; then
    curl -s http://127.0.0.1:8001/status/$JOB_ID
    echo ""
    echo "PASS: Web UI accepted upload, job $JOB_ID is processing"
fi
```

Kill the web server after testing:
```bash
kill $WEB_PID 2>/dev/null
```

NOTE: If the web pipeline completes (it may if using cached results or if the model is fast enough), also test the download endpoint:
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/download/$JOB_ID
```

Step 4 - If any fixes were needed, run unit tests:
```bash
uv run pytest tests/unit/ -x -q
```

Step 5 - Fix any code issues encountered and re-run the failing step. This is the crash-fix-rerun cycle. Read the actual error, look at the actual source code, fix the real code, run again. Do NOT add mocks. Do NOT skip steps. Do NOT mark things as passing when they produced no output.
  </action>
  <verify>
```bash
# Smoke results exist and show 0 failures
uv run python -c "
import json
with open('jobs/e2e-test/smoke-results.json') as f:
    data = json.load(f)
summary = data.get('summary', {})
print(f'Inputs: {summary.get(\"total_inputs\", 0)}')
print(f'Passed: {summary.get(\"passed\", 0)}')
print(f'Failed: {summary.get(\"failed\", 0)}')
print(f'Errors: {summary.get(\"errors\", 0)}')
assert summary.get('failed', 1) == 0, 'Smoke test has failures'
assert summary.get('errors', 1) == 0, 'Smoke test has errors'
assert summary.get('total_inputs', 0) >= 3, 'Expected at least 3 inputs'
print('ALL SMOKE CHECKS PASS')
"
# Unit tests pass
uv run pytest tests/unit/ -x -q
```
  </verify>
  <done>
- `engrave smoke-test test-fixtures/` passes ALL checks on ALL MIDI files (0 failures, 0 errors)
- smoke-results.json saved to jobs/e2e-test/smoke-results.json
- Web UI accepts MIDI upload at /engrave and returns processing status
- Web UI /status endpoint returns job progress
- No mocks used anywhere
- All unit tests pass
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human verification of generated PDFs and web UI</name>
  <files></files>
  <action>
Human verifies that the generated PDFs contain actual music notation and the web UI is functional.
  </action>
  <verify>Human opens PDFs and confirms real notation is present, tests web UI in browser.</verify>
  <done>PDFs contain real music notation, web UI uploads and processes MIDI files successfully.</done>
  <what-built>
End-to-end pipeline validation with real LLM inference. The executor ran the full Engrave pipeline on real MIDI files (inmood.mid, chattanooga.mid, bigband.mid) using Qwen3-Coder-30B via vllm-mlx, producing real LilyPond source, compiling to real PDFs, and packaging into real ZIP files. Any code bugs discovered during real runs were fixed.
  </what-built>
  <how-to-verify>
1. Open one of the generated PDFs to verify it contains actual music notation (not blank pages):
   - `open test-fixtures/.smoke/bigband/bigband-2026-02-25.zip` (or the date-stamped version that exists)
   - Extract and open score.pdf -- it should show a big band score with multiple instrument staves

2. Review the smoke test results:
   - `cat jobs/e2e-test/smoke-results.json | python3 -m json.tool`
   - All 3 inputs should show all 9 checks passing

3. Quick test the web UI:
   - Run: `cd /Users/patbarnson/devel/engrave && uv run engrave serve --port 8001`
   - Open http://127.0.0.1:8001 in browser
   - Upload test-fixtures/inmood.mid (the smallest file)
   - Wait for processing to complete (may take 10+ minutes with real inference)
   - Download the ZIP and verify it contains score.pdf

4. Check that no mocks were used:
   - The smoke runner calls `generate_from_midi` which calls `router.complete()` which calls vllm-mlx
   - Verify vllm-mlx is running: `curl -s http://localhost:8000/v1/models | python3 -m json.tool`
  </how-to-verify>
  <resume-signal>Type "approved" if PDFs contain real notation and the web UI works, or describe issues found.</resume-signal>
</task>

</tasks>

<verification>
All Definition of Done items from end-to-end-real-inference-validation.md:
1. `uv run engrave check generator` passes with a REAL LLM
2. `uv run engrave generate test-fixtures/inmood.mid` produces LilyPond
3. `uv run engrave render` produces a ZIP with real PDFs
4. `uv run engrave generate test-fixtures/chattanooga.mid` also works
5. `uv run engrave smoke-test test-fixtures/` passes ALL 9 checks on ALL files
6. Smoke test JSON saved to jobs/e2e-test/smoke-results.json
7. `uv run engrave serve` starts and processes MIDI uploads
8. No mocks anywhere -- real LLM, real compilation, real PDFs
</verification>

<success_criteria>
- smoke-results.json exists with 0 failures and 0 errors across all MIDI inputs
- At least 3 MIDI files tested (inmood, chattanooga, bigband)
- ZIP files in test-fixtures/.smoke/ contain non-empty PDFs (>50KB each)
- Web UI /engrave endpoint accepts uploads and returns job status
- All unit tests pass (no regressions from bug fixes)
- No mocks used in any step
</success_criteria>

<output>
After completion, create `.planning/quick/3-end-to-end-real-inference-validation/3-SUMMARY.md`
</output>
