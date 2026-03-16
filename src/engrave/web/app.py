"""FastAPI app for the minimal Engrave web UI.

Provides four endpoints:
- ``GET /``          -- Serve the single-page HTML template
- ``POST /engrave``  -- Accept file upload + hints, start pipeline
- ``GET /status/{job_id}`` -- Poll job status (htmx polling target)
- ``GET /download/{job_id}`` -- Download the output ZIP

Pipeline execution runs as an ``asyncio.create_task`` in the event loop
(not via BackgroundTasks) to avoid UploadFile closure and async issues.
The in-memory ``jobs`` dict is sufficient for single-user local use.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from enum import Enum
from html import escape as html_escape
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

# Default pipeline timeout in seconds (60 minutes for local 30B models).
PIPELINE_TIMEOUT_SECONDS = 60 * 60


class JobStatus(str, Enum):
    """Pipeline job lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


# In-memory job store -- single user, local machine per CONTEXT.md decision.
jobs: dict[str, dict] = {}

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable ``Xm Ys`` string."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    if mins > 0:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"


def create_app() -> FastAPI:
    """Create and return the FastAPI application.

    Returns:
        Configured FastAPI instance with all endpoints registered.
    """
    app = FastAPI(title="Engrave", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # ------------------------------------------------------------------
    # GET / -- serve the single-page HTML
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html")

    # ------------------------------------------------------------------
    # POST /engrave -- accept upload, start pipeline
    # ------------------------------------------------------------------

    @app.post("/engrave", response_class=HTMLResponse)
    async def start_engrave(
        file: UploadFile,
        hints: str = Form(""),
    ) -> HTMLResponse:
        """Accept file upload, save to disk, start pipeline in background."""
        job_id = str(uuid.uuid4())[:8]
        job_dir = Path("jobs") / f"web_{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file to disk BEFORE the handler returns.
        # (UploadFile is closed after the request handler completes -- Pitfall 1.)
        filename = file.filename or f"upload{job_id}"
        input_path = job_dir / filename
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        jobs[job_id] = {
            "status": JobStatus.PROCESSING,
            "input_path": input_path,
            "hints": hints,
            "zip_path": None,
            "error": None,
            "start_time": time.monotonic(),
        }

        # Start pipeline as an asyncio task (NOT BackgroundTasks -- Pitfall 2).
        task = asyncio.create_task(_run_pipeline(job_id, input_path, hints, job_dir))
        jobs[job_id]["task"] = task

        # Return the initial polling div for htmx.
        return HTMLResponse(
            f'<div id="status" hx-get="/status/{job_id}" '
            f'hx-trigger="every 3s" hx-swap="outerHTML">'
            f"<p>Processing...</p></div>"
        )

    # ------------------------------------------------------------------
    # GET /status/{job_id} -- htmx polling target
    # ------------------------------------------------------------------

    @app.get("/status/{job_id}", response_class=HTMLResponse)
    async def get_status(job_id: str) -> HTMLResponse:
        """Return job status HTML fragment for htmx polling."""
        job = jobs.get(job_id)
        if job is None:
            return HTMLResponse("<p>Job not found</p>", status_code=404)

        if job["status"] == JobStatus.PROCESSING:
            elapsed = time.monotonic() - job["start_time"]
            elapsed_str = _format_elapsed(elapsed)
            return HTMLResponse(
                f'<div id="status" hx-get="/status/{job_id}" '
                f'hx-trigger="every 3s" hx-swap="outerHTML">'
                f"<p>Processing... ({elapsed_str})</p></div>"
            )

        if job["status"] == JobStatus.COMPLETE:
            # HTTP 286 stops htmx polling.
            return HTMLResponse(
                f'<div id="status"><p>Complete!</p>'
                f'<a href="/download/{job_id}" '
                f'style="display:inline-block;margin-top:0.5em;padding:0.4em 1.2em;'
                f'background:#2563eb;color:#fff;border-radius:4px;text-decoration:none">'
                f"Download ZIP</a></div>",
                status_code=286,
            )

        # FAILED
        error_msg = html_escape(job.get("error", "Unknown error"))
        return HTMLResponse(
            f'<div id="status"><p style="color:#dc2626">Error: {error_msg}</p></div>',
            status_code=286,
        )

    # ------------------------------------------------------------------
    # GET /download/{job_id} -- serve the ZIP
    # ------------------------------------------------------------------

    @app.get("/download/{job_id}", response_model=None)
    async def download(job_id: str) -> FileResponse | HTMLResponse:
        """Serve the output ZIP file for a completed job."""
        job = jobs.get(job_id)
        if job is None or job.get("zip_path") is None:
            return HTMLResponse("Not found", status_code=404)
        zip_path = Path(job["zip_path"])
        return FileResponse(str(zip_path), filename=zip_path.name)

    return app


# ----------------------------------------------------------------------
# Background pipeline execution
# ----------------------------------------------------------------------


async def _run_pipeline(
    job_id: str,
    input_path: Path,
    hints: str,
    job_dir: Path,
) -> None:
    """Execute the full Engrave pipeline for a web upload.

    Determines pipeline path by file extension:
    - Audio (.wav/.mp3/.flac/.aiff): AudioPipeline -> generate -> render
    - MIDI (.mid/.midi): generate -> render

    On success, updates job status to COMPLETE and stores zip_path.
    On exception, updates to FAILED with error message.
    """
    try:
        ext = input_path.suffix.lower()

        if ext in {".wav", ".mp3", ".flac", ".aiff"}:
            zip_path = await asyncio.wait_for(
                _run_audio_pipeline(input_path, hints, job_dir),
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
        elif ext in {".mid", ".midi"}:
            zip_path = await asyncio.wait_for(
                _run_midi_pipeline(input_path, hints, job_dir),
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
        else:
            msg = f"Unsupported file type: {ext}"
            raise ValueError(msg)

        jobs[job_id]["status"] = JobStatus.COMPLETE
        jobs[job_id]["zip_path"] = str(zip_path)
        logger.info("Job %s complete: %s", job_id, zip_path)

    except TimeoutError:
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = "Pipeline timed out (30 min limit)"
        logger.error("Job %s timed out", job_id)
    except Exception as exc:
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(exc)
        logger.exception("Job %s failed: %s", job_id, exc)


async def _run_audio_pipeline(
    input_path: Path,
    hints: str,
    job_dir: Path,
) -> Path:
    """Audio pipeline path: separate -> transcribe -> generate -> render.

    Returns the path to the output ZIP file.
    """
    from engrave.audio.pipeline import AudioPipeline
    from engrave.config.settings import Settings

    settings = Settings()
    pipeline = AudioPipeline(config=settings.audio)

    # Run audio pipeline (sync -- wrap in executor to avoid blocking).
    loop = asyncio.get_running_loop()
    audio_result = await loop.run_in_executor(None, pipeline.process, input_path, job_dir)

    # Find the first stem MIDI for generation.
    midi_paths = [sr.midi_path for sr in audio_result.stem_results if sr.midi_path.exists()]
    if not midi_paths:
        msg = "Audio pipeline produced no MIDI files"
        raise RuntimeError(msg)

    # Use the first MIDI for generation (simplification for minimal UI).
    return await _generate_and_render(midi_paths[0], hints, job_dir, settings)


async def _run_midi_pipeline(
    input_path: Path,
    hints: str,
    job_dir: Path,
) -> Path:
    """MIDI-only pipeline path: generate -> render.

    Returns the path to the output ZIP file.
    """
    from engrave.config.settings import Settings

    settings = Settings()
    return await _generate_and_render(input_path, hints, job_dir, settings)


async def _generate_and_render(
    midi_path: Path,
    hints: str,
    job_dir: Path,
    settings: object,
) -> Path:
    """Shared generation + render step for both pipeline paths.

    Compiles the assembled LilyPond source directly (the assembler already
    produces a complete score with header, paper, layout, and all staves).
    This avoids the variable-name mismatch between LLM-generated names and
    the render pipeline's canonical instrument names.

    Args:
        midi_path: Path to MIDI file (from audio pipeline or direct upload).
        hints: User-provided hints text.
        job_dir: Job working directory.
        settings: Engrave settings instance.

    Returns:
        Path to the output ZIP file.
    """
    import zipfile
    from datetime import date

    from engrave.config.settings import Settings
    from engrave.generation.pipeline import generate_from_midi
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

    settings = Settings() if not isinstance(settings, Settings) else settings
    router = InferenceRouter(settings)
    compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

    gen_result = await generate_from_midi(
        midi_path=str(midi_path),
        router=router,
        compiler=compiler,
        output_dir=str(job_dir),
        user_hints=hints,
        max_concurrent_groups=settings.pipeline.max_concurrent_groups,
    )

    if not gen_result.success:
        msg = f"Generation failed at section {gen_result.sections_completed}/{gen_result.total_sections}"
        raise RuntimeError(msg)

    # Save assembled source.
    score_path = job_dir / "score.ly"
    score_path.write_text(gen_result.ly_source)

    # Compile the assembled .ly directly -- it is already a complete score
    # with header, paper, layout, staves, and all variable definitions inline.
    compile_result = compiler.compile(gen_result.ly_source, output_dir=job_dir)

    if not compile_result.success:
        logger.error("Score compilation failed: %s", compile_result.stderr[:500])

    # Package ZIP with whatever we have (PDF if compilation succeeded, .ly always).
    title_slug = midi_path.stem
    zip_name = f"{title_slug}-{date.today().isoformat()}.zip"
    zip_path = job_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(score_path, "score.ly")
        if compile_result.output_path and compile_result.output_path.exists():
            zf.write(compile_result.output_path, "score.pdf")

    return zip_path
