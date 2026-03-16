"""Typer CLI entry point with check, corpus, generate, and benchmark commands."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(
    name="engrave",
    help="AI-powered music engraving pipeline",
)

# ---------------------------------------------------------------------------
# Corpus command group
# ---------------------------------------------------------------------------

corpus_app = typer.Typer(help="Corpus storage, retrieval, and ingestion commands.")
app.add_typer(corpus_app, name="corpus")


@corpus_app.command()
def query(
    text: str = typer.Argument(..., help="Natural language query for retrieval"),
    instrument_family: str | None = typer.Option(
        None, "--instrument-family", "-i", help="Filter by instrument family"
    ),
    ensemble_type: str | None = typer.Option(
        None, "--ensemble-type", "-e", help="Filter by ensemble type"
    ),
    style: str | None = typer.Option(None, "--style", "-s", help="Filter by style"),
    n_results: int = typer.Option(5, "--n-results", "-n", help="Number of results"),
) -> None:
    """Run a retrieval query against the corpus and display results."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    try:
        from engrave.config.settings import Settings
        from engrave.corpus.retrieval import retrieve
        from engrave.corpus.store import CorpusStore

        settings = Settings()
        store = CorpusStore(config=settings.corpus)

        results = retrieve(
            query_text=text,
            instrument_family=instrument_family,
            ensemble_type=ensemble_type,
            style=style,
            n_results=n_results,
            store=store,
        )

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            raise typer.Exit(code=0)

        console.print(f"\n[bold]Found {len(results)} result(s):[/bold]\n")

        for idx, r in enumerate(results, 1):
            meta = r.chunk.metadata
            # Truncate LilyPond source to first ~5 lines
            ly_lines = r.chunk.source.strip().splitlines()
            ly_preview = "\n".join(ly_lines[:5])
            if len(ly_lines) > 5:
                ly_preview += "\n..."

            # Truncate description
            desc = r.chunk.description
            if len(desc) > 120:
                desc = desc[:117] + "..."

            header = Text()
            header.append(f"#{idx} ", style="bold cyan")
            header.append(f"{meta.source_path}", style="bold")
            header.append(f"  bars {meta.bar_start}-{meta.bar_end}", style="dim")
            header.append(f"  distance: {r.distance:.4f}", style="magenta")

            body = (
                f"[dim]{meta.instrument_family} / {meta.ensemble_type} / {meta.style}[/dim]\n"
                f"{desc}\n\n"
                f"[green]{ly_preview}[/green]"
            )

            console.print(Panel(body, title=header, expand=False))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@corpus_app.command()
def stats() -> None:
    """Display corpus statistics: chunk count, source breakdown, embedding model."""
    from rich.console import Console

    console = Console()

    try:
        from engrave.config.settings import Settings
        from engrave.corpus.store import CorpusStore

        settings = Settings()
        store = CorpusStore(config=settings.corpus)
        total = store.count()

        console.print("\n[bold]Corpus Statistics[/bold]\n")
        console.print(f"  Embedding model: [cyan]{settings.corpus.embedding_model}[/cyan]")
        console.print(f"  Collection:      [cyan]{settings.corpus.collection_name}[/cyan]")
        console.print(f"  DB path:         [cyan]{settings.corpus.db_path}[/cyan]")
        console.print(f"  Total chunks:    [bold green]{total}[/bold green]")

        if total > 0:
            # Get breakdown by source_collection
            from engrave.corpus.models import RetrievalQuery

            # Query all with a generic query to get counts
            # ChromaDB doesn't have a direct group-by, so we count via filter
            for source in ("mutopia", "pdmx"):
                try:
                    results = store.query(RetrievalQuery(query_text="music", n_results=total))
                    count = sum(1 for r in results if r.chunk.metadata.source_collection == source)
                    if count > 0:
                        console.print(f"    {source}: {count}")
                except Exception:
                    pass

        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@corpus_app.command()
def ingest() -> None:
    """Placeholder for corpus ingestion commands."""
    from rich.console import Console

    console = Console()
    console.print(
        "[yellow]Use specific ingestion commands:[/yellow]\n"
        "  [bold]engrave corpus ingest-mutopia[/bold] -- Ingest Mutopia repository scores\n"
        "  [bold]engrave corpus ingest-pdmx[/bold]    -- Ingest PDMX MusicXML scores\n"
        "\n"
        "These commands are not yet implemented in the CLI.\n"
        "Use the Python API directly:\n"
        "  [dim]from engrave.corpus import ingest_mutopia_corpus, ingest_pdmx_corpus[/dim]"
    )


@app.command()
def check(
    role: str = typer.Argument(
        ...,
        help="Role to test (e.g., 'compile_fixer', 'describer') or 'all' for every configured role",
    ),
) -> None:
    """Test connectivity to an LLM provider by sending a trivial completion."""
    import asyncio

    from rich.console import Console

    from engrave.config.settings import Settings
    from engrave.llm.exceptions import ProviderError, RoleNotFoundError
    from engrave.llm.router import InferenceRouter

    console = Console()
    settings = Settings()
    router = InferenceRouter(settings)

    roles_to_test: list[str] = list(settings.roles.keys()) if role == "all" else [role]

    for role_name in roles_to_test:
        try:
            result = asyncio.run(
                router.complete(
                    role=role_name,
                    messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
                )
            )
            text = (result or "").strip() or "(empty response)"
            console.print(f"[green]OK[/green] {role_name}: {text}")
        except RoleNotFoundError as e:
            console.print(f"[red]ERROR[/red] {e}")
            raise typer.Exit(code=1) from e
        except ProviderError as e:
            console.print(f"[red]FAIL[/red] {role_name}: {e}")
            raise typer.Exit(code=1) from e


@app.command()
def version() -> None:
    """Print the Engrave package version."""
    from engrave import __version__

    typer.echo(f"engrave {__version__}")


@app.command()
def compile(
    input_file: str = typer.Argument(..., help="LilyPond source file (.ly)"),
    fix: bool = typer.Option(True, help="Enable LLM-assisted error fixing"),
    max_attempts: int = typer.Option(5, help="Max fix attempts before giving up"),
    role: str = typer.Option("compile_fixer", help="LLM role for fixing errors"),
) -> None:
    """Compile a LilyPond file to PDF with optional LLM error fixing."""
    import asyncio
    from pathlib import Path

    from rich.console import Console

    console = Console()
    source_path = Path(input_file)

    if not source_path.exists():
        console.print(f"[red]Error:[/red] File not found: {input_file}")
        raise typer.Exit(code=1)

    source = source_path.read_text()

    try:
        from engrave.lilypond.compiler import LilyPondCompiler

        if fix:
            from engrave.config.settings import Settings
            from engrave.lilypond.fixer import compile_with_fix_loop
            from engrave.llm.router import InferenceRouter

            settings = Settings()
            router = InferenceRouter(settings)
            compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

            result = asyncio.run(
                compile_with_fix_loop(
                    source=source,
                    router=router,
                    compiler=compiler,
                    max_attempts=max_attempts,
                    context_lines=settings.lilypond.context_lines,
                )
            )

            if result.success:
                console.print(f"[green]Success:[/green] {result.output_path}")
                if result.attempts:
                    console.print(f"  Fixed after {len(result.attempts)} attempt(s)")
            else:
                console.print("[red]Compilation failed[/red] after fix attempts:")
                for attempt in result.attempts:
                    console.print(f"  Attempt {attempt.attempt_number}: {attempt.error_message}")
                if result.final_errors:
                    console.print("\nFinal errors:")
                    for err in result.final_errors:
                        console.print(
                            f"  {err.file}:{err.line}:{err.column}: {err.severity}: {err.message}"
                        )
                raise typer.Exit(code=1)
        else:
            compiler = LilyPondCompiler()
            raw = compiler.compile(source)
            if raw.success:
                console.print(f"[green]Success:[/green] {raw.output_path}")
            else:
                console.print("[red]Compilation failed:[/red]")
                if raw.stderr:
                    console.print(raw.stderr)
                raise typer.Exit(code=1)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Install LilyPond with: brew install lilypond")
        raise typer.Exit(code=1) from e


@app.command()
def generate(
    midi_path: str = typer.Argument(..., help="Path to MIDI file (.mid)"),
    output: str = typer.Option(
        None, "--output", "-o", help="Output .ly file path (default: input with .ly extension)"
    ),
    role: str = typer.Option("generator", "--role", help="LLM role for generation"),
    labels: str = typer.Option(
        None,
        "--labels",
        help='JSON string of track_index->instrument_name mappings (e.g. \'{"0": "Trumpet", "1": "Bass"}\')',
    ),
    no_rag: bool = typer.Option(
        False, "--no-rag", help="Disable RAG retrieval (proceed without few-shot examples)"
    ),
    hints: str | None = typer.Option(
        None, "--hints", help="Natural language hints (inline text or path to .hints file)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging for pipeline observability"
    ),
) -> None:
    """Generate LilyPond source from a MIDI file."""
    import asyncio
    import json
    import logging
    from pathlib import Path

    from rich.console import Console

    console = Console()

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
        # Quiet down litellm's noise
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    source_path = Path(midi_path)

    if not source_path.exists():
        console.print(f"[red]Error:[/red] File not found: {midi_path}")
        raise typer.Exit(code=1)

    # Determine output path
    output_path = source_path.with_suffix(".ly") if output is None else Path(output)

    # Parse user labels
    user_labels: dict[int, str] | None = None
    if labels:
        try:
            raw = json.loads(labels)
            user_labels = {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError) as e:
            console.print(f"[red]Error:[/red] Invalid --labels JSON: {e}")
            raise typer.Exit(code=1) from e

    try:
        from engrave.config.settings import Settings
        from engrave.generation.pipeline import generate_from_midi
        from engrave.hints import load_hints
        from engrave.lilypond.compiler import LilyPondCompiler
        from engrave.llm.router import InferenceRouter

        settings = Settings()
        router = InferenceRouter(settings)
        compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

        # Load user hints (inline text or file path, silent flow)
        user_hints = load_hints(hints)

        # Set up RAG retriever (if available and not disabled)
        rag_retriever = None
        if not no_rag:
            try:
                from engrave.corpus.retrieval import retrieve
                from engrave.corpus.store import CorpusStore

                store = CorpusStore(config=settings.corpus)

                def _rag_retriever(query: str, limit: int = 3) -> list[str]:
                    results = retrieve(query_text=query, n_results=limit, store=store)
                    return [r.chunk.source for r in results]

                rag_retriever = _rag_retriever
            except Exception:
                logging.getLogger(__name__).warning(
                    "RAG corpus not available. Generation quality may be lower without few-shot examples."
                )

        result = asyncio.run(
            generate_from_midi(
                midi_path=str(source_path),
                router=router,
                compiler=compiler,
                rag_retriever=rag_retriever,
                user_labels=user_labels,
                user_hints=user_hints,
                max_concurrent_groups=settings.pipeline.max_concurrent_groups,
            )
        )

        if result.success:
            output_path.write_text(result.ly_source)
            console.print(f"[green]Success:[/green] {output_path}")
            console.print(f"  Sections: {result.sections_completed}/{result.total_sections}")
            console.print(f"  Instruments: {', '.join(result.instrument_names)}")
            console.print(f"  Output: {output_path}")

            # Display validation results
            if result.validation and result.validation.success and result.validation.parts:
                console.print(
                    f"\n[bold]Quality Validation[/bold] (overall: {result.validation.overall_confidence_pct}% match)"
                )
                for part in result.validation.parts:
                    if part.confidence_pct >= 90:
                        style = "green"
                    elif part.confidence_pct >= 80:
                        style = "yellow"
                    else:
                        style = "red"
                    label = f"  [{style}]{part.part_name}: {part.confidence_pct}% match[/{style}]"
                    if part.needs_review:
                        label += " -- review recommended"
                    console.print(label)
            elif result.validation and not result.validation.success:
                console.print(f"\n[dim]Validation skipped: {result.validation.error}[/dim]")
        else:
            console.print("[red]Generation failed[/red]")
            console.print(
                f"  Sections completed: {result.sections_completed}/{result.total_sections}"
            )
            if result.failure_record:
                console.print(f"  Failed at section: {result.failure_record.section_index}")
                console.print(f"  Error: {result.failure_record.lilypond_error}")
            raise typer.Exit(code=1)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Install LilyPond with: brew install lilypond")
        raise typer.Exit(code=1) from e


@app.command()
def render(
    input_dir: str = typer.Argument(
        ..., help="Directory containing music-definitions.ly or pre-generated .ly content"
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output ZIP path (default: auto-generated in current directory)",
    ),
    title: str | None = typer.Option(None, "--title", "-t", help="Song title for ZIP filename"),
    no_musicxml: bool = typer.Option(
        False, "--no-musicxml", help="Exclude MusicXML from output ZIP"
    ),
) -> None:
    """Render LilyPond sources to PDFs and package into a ZIP archive.

    Reads .ly files from INPUT_DIR, compiles them via LilyPond, and produces
    a ZIP containing score.pdf, individual part PDFs, all .ly source files,
    and MIDI output.

    Exit codes: 0 = all compiled, 1 = score failed, 2 = some parts failed.
    """
    import re
    from pathlib import Path

    from rich.console import Console

    console = Console()
    source_dir = Path(input_dir)

    if not source_dir.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {input_dir}")
        raise typer.Exit(code=1)

    try:
        from engrave.rendering.ensemble import BIG_BAND
        from engrave.rendering.packager import RenderPipeline

        # Determine output directory
        output_path = Path(output).parent if output else Path.cwd()

        output_path.mkdir(parents=True, exist_ok=True)

        # Create pipeline with default compiler
        try:
            from engrave.lilypond.compiler import LilyPondCompiler

            compiler = LilyPondCompiler()
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print("Install LilyPond with: brew install lilypond")
            raise typer.Exit(code=1) from e

        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=compiler,
            include_musicxml=not no_musicxml,
        )

        # Find the LilyPond source file
        defs_file = source_dir / "music-definitions.ly"
        if not defs_file.exists():
            # Fall back to any .ly file in the directory
            ly_files = sorted(source_dir.glob("*.ly"))
            if ly_files:
                defs_file = ly_files[0]
                console.print(f"Using {defs_file.name} as source")
            else:
                console.print(f"[red]Error:[/red] No .ly files found in {input_dir}")
                raise typer.Exit(code=1)

        defs_content = defs_file.read_text()

        # Extract variables from the source file
        music_vars: dict[str, str] = {}
        global_music = ""
        chord_symbols: str | None = None

        var_pattern = re.compile(
            r"^(\w+)\s*=\s*\{(.*?)\n\}",
            re.MULTILINE | re.DOTALL,
        )
        for match in var_pattern.finditer(defs_content):
            var_name = match.group(1)
            content = match.group(2).strip()
            if var_name in ("globalMusic", "global"):
                global_music = content
            elif var_name == "chordSymbols":
                chord_symbols = content
            else:
                music_vars[var_name] = content

        if not music_vars:
            console.print("[red]Error:[/red] No music variables found")
            raise typer.Exit(code=1)

        # Check if variables match the BigBandPreset for full render pipeline
        preset_vars = {i.variable_name for i in BIG_BAND.instruments}
        actual_vars = set(music_vars.keys())
        can_use_preset = actual_vars.issubset(preset_vars)

        if can_use_preset:
            console.print(f"[bold]Rendering {len(music_vars)} instruments...[/bold]")
            result = pipeline.render(
                music_vars=music_vars,
                global_music=global_music,
                chord_symbols=chord_symbols,
                song_title=title,
                output_dir=output_path,
            )
        else:
            # Standalone compilation: variables don't match preset
            # (e.g. section-group names like "trumpets" instead of "trumpetOne")
            console.print(
                f"[bold]Standalone compile: {len(music_vars)} variables (section-group mode)[/bold]"
            )
            import shutil
            import zipfile

            work_dir = output_path / "_work"
            work_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(defs_file, work_dir / defs_file.name)

            compile_result = compiler.compile(defs_content, output_dir=work_dir)
            if not compile_result.success:
                console.print(f"[red]Compilation failed:[/red] {compile_result.stderr[:500]}")
                raise typer.Exit(code=1)

            # Package into ZIP
            zip_name = f"{title or 'score'}.zip"
            zip_path = output_path / zip_name
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for pdf in work_dir.glob("*.pdf"):
                    zf.write(pdf, pdf.name)
                for ly in work_dir.glob("*.ly"):
                    zf.write(ly, ly.name)

            from engrave.rendering.packager import RenderResult

            result = RenderResult(
                zip_path=zip_path,
                success=True,
                compiled=[defs_file.name],
                failed=[],
                errors={},
            )

        # Report results
        if result.success:
            console.print(f"[green]Success:[/green] {result.zip_path}")
            console.print(f"  Compiled: {len(result.compiled)} files")
        else:
            score_failed = "score.ly" in result.failed
            if score_failed:
                console.print("[red]Score compilation failed[/red]")
                if "score.ly" in result.errors:
                    console.print(f"  Error: {result.errors['score.ly']}")
                raise typer.Exit(code=1)

            console.print(f"[yellow]Partial success:[/yellow] {result.zip_path}")
            console.print(f"  Compiled: {len(result.compiled)} files")
            console.print(f"  Failed:   {len(result.failed)} files")
            for fname in result.failed:
                err = result.errors.get(fname, "Unknown error")
                console.print(f"    [red]FAIL[/red] {fname}: {err}")
            raise typer.Exit(code=2)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command("process-audio")
def process_audio(
    input_source: str = typer.Argument(
        ..., help="Path to audio file (MP3/WAV/AIFF/FLAC) or YouTube URL"
    ),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Custom job directory (default: auto-generated in jobs/)"
    ),
    no_separate: bool = typer.Option(
        False, "--no-separate", help="Skip separation (transcribe raw audio directly)"
    ),
    steps: str | None = typer.Option(None, "--steps", help="JSON override for separation steps"),
) -> None:
    """Process audio through the full pipeline: normalize, separate, transcribe, annotate.

    Accepts an audio file path or a YouTube URL. Creates a timestamped job
    directory with all intermediate artifacts (normalized WAV, separated stems,
    MIDI transcriptions, quality annotations).
    """
    import json as json_mod
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    console = Console()

    try:
        from engrave.audio.pipeline import AudioPipeline
        from engrave.audio.youtube import is_youtube_url
        from engrave.config.settings import Settings

        settings = Settings()

        # Optionally override separation steps
        if steps:
            try:
                steps_data = json_mod.loads(steps)
                # Apply steps override to config
                settings.audio.separation.steps = steps_data
            except json_mod.JSONDecodeError as e:
                console.print(f"[red]Error:[/red] Invalid --steps JSON: {e}")
                raise typer.Exit(code=1) from e

        if no_separate:
            # Clear separation steps so pipeline gets empty list
            settings.audio.separation.steps = []

        pipeline = AudioPipeline(config=settings.audio)
        job_dir_path = Path(output_dir) if output_dir else None

        if is_youtube_url(input_source):
            console.print(f"[bold]Downloading from YouTube:[/bold] {input_source}")
            result = pipeline.process_youtube(input_source, job_dir_path)
        else:
            source_path = Path(input_source)
            if not source_path.exists():
                console.print(f"[red]Error:[/red] Audio file not found: {input_source}")
                raise typer.Exit(code=1)
            console.print(f"[bold]Processing audio:[/bold] {source_path}")
            result = pipeline.process(source_path, job_dir_path)

        # Display results
        console.print("\n[green]Pipeline complete![/green]")
        console.print(f"  Job directory: {result.job_dir}")
        console.print(f"  Stems: {len(result.stem_results)}")

        if result.stem_results:
            table = Table(title="Stem Results")
            table.add_column("Stem", style="cyan")
            table.add_column("MIDI Path", style="green")
            table.add_column("Notes", justify="right")
            table.add_column("Quality Issues", justify="right")

            for sr in result.stem_results:
                issues = sr.quality.pitch_range_violations
                table.add_row(
                    sr.stem_name,
                    str(sr.midi_path),
                    str(sr.quality.note_count),
                    str(issues),
                )

            console.print(table)

    except typer.Exit:
        raise
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


# ---------------------------------------------------------------------------
# Smoke test command
# ---------------------------------------------------------------------------


@app.command("smoke-test")
def smoke_test(
    test_dir: str = typer.Argument(..., help="Directory containing test input files"),
    output_json: str | None = typer.Option(None, "--json", "-j", help="Write JSON results to file"),
) -> None:
    """Run smoke tests on all audio/MIDI files in a directory.

    Discovers inputs by extension (.wav, .mp3, .flac, .aiff for audio;
    .mid for MIDI). Runs each through the appropriate pipeline path
    and performs 9 structural checks on the output.
    """
    import asyncio
    from pathlib import Path

    from rich.console import Console

    console = Console()
    dir_path = Path(test_dir)

    if not dir_path.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {test_dir}")
        raise typer.Exit(code=1)

    from engrave.smoke.reporter import format_json, format_terminal
    from engrave.smoke.runner import run_smoke_test

    result = asyncio.run(run_smoke_test(dir_path))

    # Human-readable terminal output
    format_terminal(result, console)

    # JSON output (optional)
    if output_json:
        json_str = format_json(result, test_dir=test_dir)
        json_path = Path(output_json)
        json_path.write_text(json_str)
        console.print(f"\n[dim]JSON results written to {json_path}[/dim]")

    # Exit code: 0 if all passed, 1 if any failures or errors
    if result.total_failed > 0 or result.total_errors > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Web UI serve command
# ---------------------------------------------------------------------------


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
) -> None:
    """Start the minimal web UI for UAT testing."""
    import uvicorn

    from engrave.web.app import create_app

    web_app = create_app()
    typer.echo(f"Starting Engrave web UI at http://{host}:{port}")
    uvicorn.run(web_app, host=host, port=port)


# ---------------------------------------------------------------------------
# Benchmark command group
# ---------------------------------------------------------------------------

benchmark_app = typer.Typer(help="Benchmark and evaluate pipeline accuracy.")
app.add_typer(benchmark_app, name="benchmark")


@benchmark_app.command("run")
def benchmark_run(
    midi_path: str = typer.Argument(..., help="Path to reference MIDI file"),
    results_dir: str | None = typer.Option(
        None,
        "--results-dir",
        "-r",
        help="Directory to save results (default: from config)",
    ),
    soundfont: str | None = typer.Option(
        None, "--soundfont", "-s", help="Override SoundFont (.sf2) path"
    ),
) -> None:
    """Run a benchmark evaluation on a reference MIDI file.

    Renders the MIDI to audio via FluidSynth, processes through the
    separation+transcription pipeline, and diffs against ground truth.
    Results are saved as structured JSON.
    """
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    console = Console()
    source = Path(midi_path)

    if not source.exists():
        console.print(f"[red]Error:[/red] MIDI file not found: {midi_path}")
        raise typer.Exit(code=1)

    try:
        from engrave.audio.pipeline import AudioPipeline
        from engrave.benchmark.harness import BenchmarkConfig, BenchmarkHarness
        from engrave.config.settings import Settings

        settings = Settings()
        bench_cfg = settings.audio.benchmark

        config = BenchmarkConfig(
            soundfont_path=soundfont or bench_cfg.soundfont_path,
            onset_tolerance=bench_cfg.onset_tolerance,
            results_dir=results_dir or bench_cfg.results_dir,
        )

        pipeline = AudioPipeline(config=settings.audio)
        harness = BenchmarkHarness(pipeline=pipeline, config=config)

        console.print(f"[bold]Running benchmark:[/bold] {source}")
        run = harness.run_single(source, results_dir=Path(config.results_dir))

        # Display results
        console.print(f"\n[green]Benchmark complete![/green]  Run ID: {run.run_id}")

        table = Table(title="Per-Stem Metrics")
        table.add_column("Stem", style="cyan")
        table.add_column("F1", justify="right")
        table.add_column("Precision", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("Overlap", justify="right")
        table.add_column("Ref Notes", justify="right")
        table.add_column("Est Notes", justify="right")

        for sm in run.stem_metrics:
            table.add_row(
                sm.stem_name,
                f"{sm.f1:.3f}",
                f"{sm.precision:.3f}",
                f"{sm.recall:.3f}",
                f"{sm.avg_overlap:.3f}",
                str(sm.note_count_ref),
                str(sm.note_count_est),
            )

        console.print(table)

        agg = run.aggregate
        console.print(f"\n  Mean F1: {agg.mean_f1:.3f}")
        console.print(f"  Mean Precision: {agg.mean_precision:.3f}")
        console.print(f"  Mean Recall: {agg.mean_recall:.3f}")
        console.print(f"  Worst Stem: {agg.worst_stem} (F1={agg.worst_f1:.3f})")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@benchmark_app.command("compare")
def benchmark_compare(
    result_files: Annotated[list[str], typer.Argument(help="Paths to benchmark result JSON files")],
) -> None:
    """Compare benchmark results from multiple runs.

    Loads JSON result files and displays a formatted comparison table
    with per-stem and aggregate metrics.
    """
    from pathlib import Path

    from rich.console import Console

    console = Console()

    try:
        from engrave.benchmark.harness import BenchmarkHarness

        paths = [Path(f) for f in result_files]
        for p in paths:
            if not p.exists():
                console.print(f"[red]Error:[/red] Result file not found: {p}")
                raise typer.Exit(code=1)

        output = BenchmarkHarness.compare_runs(paths)
        console.print(output)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
