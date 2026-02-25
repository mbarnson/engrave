# Quick Task: End-to-End Real Inference Validation

## What This Is

Engrave is a pipeline that turns MIDI files into publication-quality sheet music. It has been built over 7+ phases with full test coverage — but every test uses mocked LLM responses. **No one has ever run the actual pipeline on a real MIDI file with a real LLM producing real LilyPond code that gets compiled into real PDFs and packaged into a real ZIP file.**

This task fixes that. You will run the pipeline end-to-end with real inference, fix every crash and failure you encounter, and produce actual output artifacts that a human can open and evaluate.

## Why This Matters

The project has 791 passing tests. All mocked. The owner tried to hand this to a human tester and predicted exactly what would happen: the first real run would crash, requiring a copy-paste-fix cycle. Your job is to BE that cycle — run it, crash, fix, run again — until the pipeline produces real output. Every bug you fix here is one fewer bug the human tester hits.

## Prerequisites You Must Verify (Not Assume)

Before running anything, confirm each of these. Do not skip any.

1. **LilyPond is installed and works:**
   ```bash
   lilypond --version
   ```
   If this fails, install it: `brew install lilypond`

2. **LMStudio is running with a model loaded:**
   ```bash
   curl http://localhost:1234/v1/models
   ```
   If this fails, tell the user to start LMStudio and load a model. You cannot proceed without a running LLM. Do NOT mock this. Do NOT skip this. Do NOT pretend this works.

3. **The Engrave LLM connectivity check passes:**
   ```bash
   uv run engrave check generator
   ```
   If this fails, diagnose and fix the connection. Check `engrave.toml` for the model name — it must match what LMStudio has loaded. The current config expects `lm_studio/qwen3-coder-next` but the loaded model may differ. Update `engrave.toml` [roles.generator] to match the actually-loaded model.

4. **Test MIDI files exist:**
   Download at least 2 big band MIDI files from the bTd archive:
   ```bash
   mkdir -p test-fixtures
   curl -o test-fixtures/chattanooga.mid "https://www.dongrays.com/midi/archive/jazz/bigband/chatchoo.mid"
   curl -o test-fixtures/inmood.mid "https://www.dongrays.com/midi/archive/jazz/bigband/inmood.mid"
   ```
   Verify they downloaded correctly (non-zero size, valid MIDI):
   ```bash
   uv run python -c "import pretty_midi; m = pretty_midi.PrettyMIDI('test-fixtures/chattanooga.mid'); print(f'{len(m.instruments)} tracks'); [print(f'  {i.program}: {i.name}') for i in m.instruments]"
   ```

## What You Must Do

### Phase 1: MIDI-Only Pipeline (No Audio)

Run the MIDI-only path first because it's simpler and faster to debug.

```bash
uv run engrave generate test-fixtures/inmood.mid --output jobs/e2e-test/inmood/
```

**This will almost certainly fail.** That's the point. Common failure modes:

- LLM returns content the LilyPond parser can't extract → fix `extract_lilypond_from_response` or prompt
- LLM generates invalid LilyPond → the fix loop should handle this, but check it's actually retrying
- `generate_from_midi` signature has changed since Phase 6/7 → the CLI may be calling it with wrong args
- Template variable names don't match what the LLM generates → fix `parse_instrument_blocks`
- Section detection produces 0 sections or weird boundaries → check `detect_sections` on this MIDI
- `generate_from_midi` needs parameters that the CLI doesn't pass (e.g., `output_dir`) → fix the CLI

**Fix each failure. Re-run. Repeat until `engrave generate` completes successfully.**

Then render:

```bash
uv run engrave render jobs/e2e-test/inmood/ --title "In The Mood"
```

**This will also probably fail.** Common failure modes:

- The generated LilyPond references variables that the renderer doesn't know about
- `music-definitions.ly` format doesn't match what `render` expects
- The assembled LilyPond has syntax errors that compilation catches
- The render pipeline expects `json_sections` or `instrument_names` it doesn't have from the CLI path

**Fix each failure. Re-run. Repeat until a ZIP file is produced.**

### Phase 2: Verify the Output

Once you have a ZIP file:

```bash
ls -la jobs/e2e-test/inmood/render/*.zip
unzip -l jobs/e2e-test/inmood/render/*.zip
```

The ZIP must contain:
- At least 1 conductor score PDF
- Individual part PDFs (one per instrument)
- `.ly` source files
- Optionally `.musicxml` and MIDI

Open a PDF and verify it's not empty:
```bash
# On macOS:
open jobs/e2e-test/inmood/render/*.zip
# Then open a PDF from the extracted contents
```

### Phase 3: Run the Smoke Harness on Real Output

```bash
uv run engrave smoke-test test-fixtures/
```

This runs the full pipeline on every file in test-fixtures/ and checks:
- No exceptions
- Compilable LilyPond (every .ly has a .pdf)
- Valid PDFs (non-empty)
- Valid MusicXML (if present)
- All parts present (17 big band instruments + score)
- Correct transpositions
- Note count > 0 per non-drum part
- PDF file size > 50KB
- ZIP file count in expected range

**Fix every failing check. Re-run until the smoke harness reports all green.**

### Phase 4: Run the Second MIDI File

Repeat Phases 1-3 with `chattanooga.mid`. This is a longer, more complex chart with all 17 big band voices. It may expose different failures than the shorter `inmood.mid`.

### Phase 5: Verify the Web UI Works

```bash
uv run engrave serve
```

Open the browser URL. Upload `inmood.mid` through the web interface. Click Engrave. Wait for completion. Download the ZIP.

If this fails, fix the web app's pipeline integration. The web app calls the same Python APIs as the CLI — if the CLI works but the web doesn't, the issue is in the web endpoint's call to the pipeline functions.

## Definition of Done

ALL of the following must be true. Not some. ALL.

1. `uv run engrave check generator` passes with a REAL LLM (not mocked)
2. `uv run engrave generate test-fixtures/inmood.mid` produces a directory with generated LilyPond
3. `uv run engrave render` on that directory produces a ZIP file containing real PDFs with real music notation (not empty pages, not error pages)
4. `uv run engrave generate test-fixtures/chattanooga.mid` also works end-to-end
5. `uv run engrave smoke-test test-fixtures/` passes ALL 9 checks on BOTH MIDI files
6. The smoke test JSON report is saved to `jobs/e2e-test/smoke-results.json`
7. `uv run engrave serve` starts and a MIDI file can be uploaded and processed through the web UI, producing a downloadable ZIP
8. No mocks anywhere in this process. Real LLM inference. Real LilyPond compilation. Real PDF rendering. Real ZIP files on disk that a human can open.

## What to Do When (Not If) Things Break

1. Read the actual error message and stack trace
2. Look at the actual source code that's failing (not the test code — the real code)
3. Fix the real code
4. Run the real pipeline again
5. Repeat

Do NOT:
- Add mocks to "get past" a failure
- Skip a step because it's "not working yet"
- Mark something as passing when it produced no output
- Assume that passing unit tests mean the real pipeline works
- Ask the user to test something you haven't tested yourself

## Key Project Files

- `engrave.toml` — LLM provider config, model names, role mappings
- `src/engrave/cli.py` — CLI entry points (`generate`, `render`, `serve`, `smoke-test`)
- `src/engrave/generation/pipeline.py` — Core generation pipeline (`generate_from_midi`)
- `src/engrave/rendering/packager.py` — Render pipeline (`RenderPipeline.render`)
- `src/engrave/smoke/runner.py` — Smoke test runner
- `src/engrave/smoke/checks.py` — 9 structural checks
- `src/engrave/web/app.py` — FastAPI web app
- `src/engrave/llm/router.py` — LLM inference router
- `src/engrave/lilypond/compiler.py` — LilyPond compilation
- `src/engrave/lilypond/fixer.py` — Compile-fix retry loop
