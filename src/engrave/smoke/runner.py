"""Smoke test runner: input discovery, pipeline orchestration, result aggregation.

Discovers audio (.wav, .mp3, .flac, .aiff) and MIDI (.mid, .midi) files in a
test directory, runs each through the appropriate Engrave pipeline path, and
collects per-input results with timing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".aiff"}
MIDI_EXTENSIONS = {".mid", ".midi"}


@dataclass
class CheckResult:
    """Result of a single check on a pipeline output."""

    name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputResult:
    """Result for a single test input file."""

    input_path: Path
    pipeline_path: str  # "audio" or "midi"
    checks: list[CheckResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    error: str | None = None  # Pipeline-level exception if any


@dataclass
class SmokeResult:
    """Aggregate result of a full smoke test run."""

    inputs: list[InputResult] = field(default_factory=list)
    total_passed: int = 0
    total_failed: int = 0
    total_errors: int = 0
    elapsed_seconds: float = 0.0


def discover_inputs(test_dir: Path) -> list[tuple[Path, str]]:
    """Discover test input files by extension.

    Returns list of (path, pipeline_type) tuples where
    pipeline_type is ``"audio"`` or ``"midi"``.
    """
    inputs: list[tuple[Path, str]] = []
    for f in sorted(test_dir.iterdir()):
        if f.is_file():
            ext = f.suffix.lower()
            if ext in AUDIO_EXTENSIONS:
                inputs.append((f, "audio"))
            elif ext in MIDI_EXTENSIONS:
                inputs.append((f, "midi"))
    return inputs


def _check_llm_connectivity() -> str | None:
    """Verify LLM provider is reachable.

    Returns None on success or an error message string on failure.
    """
    try:
        from engrave.config.settings import Settings
        from engrave.llm.router import InferenceRouter

        settings = Settings()
        router = InferenceRouter(settings)
        result = asyncio.run(
            router.complete(
                role="generator",
                messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
                max_tokens=5,
            )
        )
        if result:
            return None
        return "LLM returned empty response"
    except Exception as exc:
        return f"LLM connectivity check failed: {exc}"


async def _run_audio_pipeline(input_path: Path, job_dir: Path) -> Path:
    """Run the audio-in pipeline path: process -> generate -> render.

    Returns the path to the output ZIP file.
    """
    from engrave.audio.pipeline import AudioPipeline
    from engrave.config.settings import Settings
    from engrave.generation.pipeline import generate_from_midi
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter
    from engrave.rendering.ensemble import BIG_BAND
    from engrave.rendering.packager import RenderPipeline

    settings = Settings()
    audio_pipeline = AudioPipeline(config=settings.audio)
    job_result = audio_pipeline.process(input_path, job_dir / "audio")

    # Generate from transcribed stems
    router = InferenceRouter(settings)
    compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

    # Use the first stem's MIDI as input
    if not job_result.stem_results:
        msg = "Audio pipeline produced no stems"
        raise RuntimeError(msg)

    midi_path = job_result.stem_results[0].midi_path
    gen_result = await generate_from_midi(
        midi_path=str(midi_path),
        router=router,
        compiler=compiler,
        output_dir=str(job_dir / "generation"),
    )

    if not gen_result.success:
        msg = f"Generation failed at section {gen_result.sections_completed}/{gen_result.total_sections}"
        raise RuntimeError(msg)

    # Render
    from engrave.generation.templates import sanitize_var_name

    music_vars = {}
    for name in gen_result.instrument_names:
        var_name = sanitize_var_name(name)
        music_vars[var_name] = ""

    render_pipeline = RenderPipeline(preset=BIG_BAND, compiler=compiler)
    render_result = render_pipeline.render(
        music_vars=music_vars,
        global_music="",
        chord_symbols=None,
        song_title=input_path.stem,
        output_dir=job_dir / "render",
        json_sections=gen_result.json_sections,
        instrument_names=gen_result.instrument_names,
    )

    return render_result.zip_path


async def _run_midi_pipeline(input_path: Path, job_dir: Path) -> Path:
    """Run the MIDI-only pipeline path: generate -> compile -> package.

    Compiles the assembled LilyPond directly (it is a complete score with
    all variable definitions inline) rather than routing through the render
    pipeline which expects canonical instrument variable names.

    Returns the path to the output ZIP file.
    """
    import zipfile
    from datetime import date

    from engrave.config.settings import Settings
    from engrave.generation.pipeline import generate_from_midi
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

    settings = Settings()
    router = InferenceRouter(settings)
    compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

    gen_dir = job_dir / "generation"
    gen_dir.mkdir(parents=True, exist_ok=True)

    gen_result = await generate_from_midi(
        midi_path=str(input_path),
        router=router,
        compiler=compiler,
        output_dir=str(gen_dir),
    )

    if not gen_result.success:
        msg = f"Generation failed at section {gen_result.sections_completed}/{gen_result.total_sections}"
        raise RuntimeError(msg)

    # Save and compile the assembled .ly directly.
    score_path = job_dir / "score.ly"
    score_path.write_text(gen_result.ly_source)

    compile_result = compiler.compile(gen_result.ly_source, output_dir=job_dir)

    # Package ZIP.
    title_slug = input_path.stem
    zip_name = f"{title_slug}-{date.today().isoformat()}.zip"
    zip_path = job_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(score_path, "score.ly")
        if compile_result.output_path and compile_result.output_path.exists():
            zf.write(compile_result.output_path, "score.pdf")

    return zip_path


def _run_checks(
    zip_path: Path | None,
    error: str | None,
    expected_pdf_count: int = 1,
    expected_file_min: int = 2,
    expected_file_max: int = 3,
) -> list[CheckResult]:
    """Run all 9 checks on a pipeline output.

    Args:
        zip_path: Path to the output ZIP, or None if pipeline failed.
        error: Pipeline-level error string, or None if no error.
        expected_pdf_count: Expected number of PDFs (1 for score-only,
            N+1 for score + parts).
        expected_file_min: Minimum expected files in ZIP.
        expected_file_max: Maximum expected files in ZIP.

    Returns:
        List of 9 CheckResult objects.
    """
    from engrave.smoke.checks import (
        check_all_parts_present,
        check_compilable_ly,
        check_correct_transpositions,
        check_no_exceptions,
        check_note_count,
        check_pdf_file_size,
        check_valid_musicxml,
        check_valid_pdfs,
        check_zip_file_count,
    )

    results: list[CheckResult] = []

    # Check 1: No exceptions
    results.append(check_no_exceptions(error))

    if zip_path is None or not zip_path.exists():
        # All remaining checks cannot run without a ZIP
        for name in [
            "compilable_ly",
            "valid_pdfs",
            "valid_musicxml",
            "all_parts_present",
            "correct_transpositions",
            "note_count",
            "pdf_file_size",
            "zip_file_count",
        ]:
            results.append(CheckResult(name=name, passed=False, message="No ZIP file produced"))
        return results

    # Check 2: Compilable LilyPond
    results.append(check_compilable_ly(zip_path))

    # Check 3: Valid PDFs
    results.append(check_valid_pdfs(zip_path))

    # Check 4: Valid MusicXML
    results.append(check_valid_musicxml(zip_path))

    # Check 5: All parts present (score-only: expects 1 PDF)
    results.append(check_all_parts_present(zip_path, expected_pdf_count - 1))

    # Check 6: Correct transpositions
    results.append(check_correct_transpositions(zip_path))

    # Check 7: Note count
    results.append(check_note_count(zip_path))

    # Check 8: PDF file size
    results.append(check_pdf_file_size(zip_path))

    # Check 9: ZIP file count
    results.append(check_zip_file_count(zip_path, expected_file_min, expected_file_max))

    return results


async def run_smoke_test(test_dir: Path) -> SmokeResult:
    """Run the full smoke test suite on all inputs in a directory.

    Discovers audio and MIDI files, runs each through the appropriate
    pipeline path, performs 9 structural checks, and aggregates results.

    Args:
        test_dir: Directory containing test input files.

    Returns:
        SmokeResult with per-input results and aggregate totals.
    """
    t0 = time.monotonic()

    # Check LLM connectivity before running any inputs
    llm_error = _check_llm_connectivity()
    if llm_error:
        logger.error("LLM provider not available: %s", llm_error)
        return SmokeResult(
            total_errors=1,
            elapsed_seconds=time.monotonic() - t0,
            inputs=[
                InputResult(
                    input_path=test_dir,
                    pipeline_path="pre-flight",
                    error=llm_error,
                    checks=[
                        CheckResult(
                            name="llm_connectivity",
                            passed=False,
                            message=llm_error,
                        )
                    ],
                )
            ],
        )

    discovered = discover_inputs(test_dir)
    if not discovered:
        logger.warning("No audio or MIDI inputs found in %s", test_dir)
        return SmokeResult(elapsed_seconds=time.monotonic() - t0)

    results: list[InputResult] = []
    total_passed = 0
    total_failed = 0
    total_errors = 0

    for input_path, pipeline_type in discovered:
        input_t0 = time.monotonic()
        error: str | None = None
        zip_path: Path | None = None

        # Create per-input job directory
        job_dir = test_dir / ".smoke" / input_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            if pipeline_type == "audio":
                zip_path = await _run_audio_pipeline(input_path, job_dir)
            else:
                zip_path = await _run_midi_pipeline(input_path, job_dir)
        except Exception as exc:
            error = str(exc)
            logger.error("Pipeline error for %s: %s", input_path.name, error)

        # Run checks -- direct compilation produces score.ly + score.pdf (2 files)
        checks = _run_checks(
            zip_path,
            error,
            expected_pdf_count=1,
            expected_file_min=2,
            expected_file_max=2,
        )

        input_elapsed = time.monotonic() - input_t0
        input_result = InputResult(
            input_path=input_path,
            pipeline_path=pipeline_type,
            checks=checks,
            elapsed_seconds=round(input_elapsed, 2),
            error=error,
        )
        results.append(input_result)

        # Tally
        if error:
            total_errors += 1
        for check in checks:
            if check.passed:
                total_passed += 1
            else:
                total_failed += 1

    elapsed = time.monotonic() - t0
    return SmokeResult(
        inputs=results,
        total_passed=total_passed,
        total_failed=total_failed,
        total_errors=total_errors,
        elapsed_seconds=round(elapsed, 2),
    )


def smoke_result_to_dict(result: SmokeResult) -> dict[str, Any]:
    """Convert a SmokeResult to a JSON-serializable dict.

    Handles Path objects by converting them to strings.
    """

    def _convert(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(item) for item in obj]
        return obj

    raw = asdict(result)
    return _convert(raw)
