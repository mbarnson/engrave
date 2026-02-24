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
    input_file: str = typer.Argument(..., help="LilyPond source file"),
) -> None:
    """Compile a LilyPond file to PDF with optional LLM error fixing."""
    typer.echo("Not yet implemented")
    raise typer.Exit(code=0)
