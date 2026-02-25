"""Typer CLI entry point with check, corpus, and generate commands."""

from __future__ import annotations

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
                    max_tokens=5,
                )
            )
            console.print(f"[green]OK[/green] {role_name}: {result.strip()}")
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
) -> None:
    """Generate LilyPond source from a MIDI file."""
    import asyncio
    import json
    import logging
    from pathlib import Path

    from rich.console import Console

    console = Console()
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
        from engrave.lilypond.compiler import LilyPondCompiler
        from engrave.llm.router import InferenceRouter

        settings = Settings()
        router = InferenceRouter(settings)
        compiler = LilyPondCompiler(timeout=settings.lilypond.compile_timeout)

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
            )
        )

        if result.success:
            output_path.write_text(result.ly_source)
            console.print(f"[green]Success:[/green] {output_path}")
            console.print(f"  Sections: {result.sections_completed}/{result.total_sections}")
            console.print(f"  Instruments: {', '.join(result.instrument_names)}")
            console.print(f"  Output: {output_path}")
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
        )

        # Read music variables from input directory
        # For now, read the music-definitions.ly file and extract variables
        # This is a placeholder interface -- Phase 3's assembler will produce
        # the dict[str, str] of music variables directly
        defs_file = source_dir / "music-definitions.ly"
        if not defs_file.exists():
            console.print(f"[red]Error:[/red] music-definitions.ly not found in {input_dir}")
            raise typer.Exit(code=1)

        # Read the raw content and parse music variables
        defs_content = defs_file.read_text()

        # Extract globalMusic and instrument variables from definitions file
        # Simple regex-based parsing of LilyPond variable definitions
        music_vars: dict[str, str] = {}
        global_music = ""
        chord_symbols: str | None = None

        # Match variable = { content } blocks
        var_pattern = re.compile(
            r"^(\w+)\s*=\s*\{(.*?)\}",
            re.MULTILINE | re.DOTALL,
        )
        for match in var_pattern.finditer(defs_content):
            var_name = match.group(1)
            content = match.group(2).strip()
            if var_name == "globalMusic":
                global_music = content
            elif var_name == "chordSymbols":
                chord_symbols = content
            else:
                music_vars[var_name] = content

        if not music_vars:
            console.print("[red]Error:[/red] No music variables found in music-definitions.ly")
            raise typer.Exit(code=1)

        console.print(f"[bold]Rendering {len(music_vars)} instruments...[/bold]")

        result = pipeline.render(
            music_vars=music_vars,
            global_music=global_music,
            chord_symbols=chord_symbols,
            song_title=title,
            output_dir=output_path,
        )

        # Report results
        if result.success:
            console.print(f"[green]Success:[/green] {result.zip_path}")
            console.print(f"  Compiled: {len(result.compiled)} files")
        else:
            # Check if score failed
            score_failed = "score.ly" in result.failed
            if score_failed:
                console.print("[red]Score compilation failed[/red]")
                if "score.ly" in result.errors:
                    console.print(f"  Error: {result.errors['score.ly']}")
                raise typer.Exit(code=1)

            # Some parts failed
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
