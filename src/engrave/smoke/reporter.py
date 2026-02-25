"""Smoke test output formatting: Rich terminal tables and JSON serialization.

Two output functions:
- ``format_terminal`` -- Rich console output with color-coded pass/fail
- ``format_json`` -- Structured JSON matching the documented schema
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from engrave.smoke.runner import SmokeResult, smoke_result_to_dict


def format_terminal(result: SmokeResult, console: Console) -> None:
    """Print smoke test results to terminal using Rich formatting.

    For each input, displays a section header and a table of check results
    with color-coded pass/fail indicators. Ends with an aggregate summary.

    Args:
        result: The smoke test result to display.
        console: Rich console instance for output.
    """
    if not result.inputs:
        console.print("[yellow]No inputs processed.[/yellow]")
        return

    for input_result in result.inputs:
        # Section header
        path_display = str(input_result.input_path)
        header = Text()
        header.append(f"\n{path_display}", style="bold")
        header.append(f"  ({input_result.pipeline_path})", style="dim")
        if input_result.elapsed_seconds > 0:
            header.append(f"  {input_result.elapsed_seconds:.1f}s", style="dim cyan")
        console.print(header)

        if input_result.error:
            console.print(f"  [red]ERROR:[/red] {input_result.error}")

        # Check results table
        if input_result.checks:
            table = Table(show_header=True, show_lines=False, pad_edge=False, box=None)
            table.add_column("", width=3)
            table.add_column("Check", style="white")
            table.add_column("Message", style="dim")

            for check in input_result.checks:
                if check.passed:
                    if "SKIPPED" in check.message:
                        icon = "[yellow]-[/yellow]"
                    else:
                        icon = "[green]OK[/green]"
                else:
                    icon = "[red]X[/red]"

                msg = check.message if check.message else ""
                table.add_row(icon, check.name, msg)

            console.print(table)

    # Summary line
    total_inputs = len(result.inputs)
    console.print()

    summary = Text()
    summary.append(f"{result.total_passed} passed", style="bold green")
    summary.append(", ")
    if result.total_failed > 0:
        summary.append(f"{result.total_failed} failed", style="bold red")
    else:
        summary.append(f"{result.total_failed} failed", style="dim")
    summary.append(", ")
    if result.total_errors > 0:
        summary.append(f"{result.total_errors} errors", style="bold red")
    else:
        summary.append(f"{result.total_errors} errors", style="dim")
    summary.append(f" across {total_inputs} input(s)")
    summary.append(f"  ({result.elapsed_seconds:.1f}s total)", style="dim")

    console.print(summary)


def format_json(result: SmokeResult, test_dir: str = "") -> str:
    """Serialize SmokeResult to JSON matching the documented schema.

    Includes run_timestamp (ISO 8601), test_dir, inputs with all checks,
    and summary totals.

    Args:
        result: The smoke test result to serialize.
        test_dir: The test directory path string.

    Returns:
        Pretty-printed JSON string.
    """
    data = smoke_result_to_dict(result)

    # Wrap in the documented schema
    output: dict[str, Any] = {
        "run_timestamp": datetime.now(tz=UTC).isoformat(),
        "test_dir": test_dir,
        "inputs": [],
        "summary": {
            "total_inputs": len(result.inputs),
            "passed": result.total_passed,
            "failed": result.total_failed,
            "errors": result.total_errors,
        },
    }

    # Reshape inputs to match schema (checks as dict keyed by name)
    for inp in data["inputs"]:
        checks_dict: dict[str, Any] = {}
        for check in inp.get("checks", []):
            check_entry: dict[str, Any] = {
                "passed": check["passed"],
                "message": check.get("message", ""),
            }
            if check.get("details"):
                check_entry["details"] = check["details"]
            checks_dict[check["name"]] = check_entry

        output["inputs"].append(
            {
                "input_path": inp["input_path"],
                "pipeline_path": inp["pipeline_path"],
                "elapsed_seconds": inp.get("elapsed_seconds", 0),
                "error": inp.get("error"),
                "checks": checks_dict,
            }
        )

    return json.dumps(output, indent=2, default=str)
