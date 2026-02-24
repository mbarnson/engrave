"""Typer CLI entry point with check command."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="engrave",
    help="AI-powered music engraving pipeline",
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
