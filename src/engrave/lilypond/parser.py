"""LilyPond error output parser: stderr -> structured errors."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Pattern: filename:line:column: severity: message
# Matches "error", "warning", and "fatal error" severities
ERROR_PATTERN = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<severity>fatal error|error|warning):\s+"
    r"(?P<message>.+)$"
)


@dataclass
class LilyPondError:
    """A single parsed error from LilyPond compilation."""

    file: str
    line: int
    column: int
    severity: str  # "error", "warning", "fatal error"
    message: str
    offending_line: str  # The source line that caused the error


def parse_lilypond_errors(output: str) -> list[LilyPondError]:
    """Parse LilyPond stderr/stdout into structured error objects.

    LilyPond outputs errors in the format:
        filename:lineno:columnno: severity: message
    followed by the offending source line.

    Both stderr and stdout may contain error information (Pitfall 2),
    so this function accepts combined output or either stream.

    Args:
        output: Combined stderr+stdout or just stderr from LilyPond.

    Returns:
        List of LilyPondError objects, empty if no errors found.
    """
    errors: list[LilyPondError] = []
    lines = output.splitlines()

    for i, line in enumerate(lines):
        match = ERROR_PATTERN.match(line)
        if match:
            # Next line is typically the offending source line
            offending = lines[i + 1] if i + 1 < len(lines) else ""
            errors.append(
                LilyPondError(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("col")),
                    severity=match.group("severity"),
                    message=match.group("message"),
                    offending_line=offending.strip(),
                )
            )

    return errors
