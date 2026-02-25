"""Typer CLI entry point with check and corpus commands."""

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
