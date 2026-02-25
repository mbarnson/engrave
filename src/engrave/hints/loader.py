"""Hint loading with inline text vs file path auto-detection.

User hints are free text -- no DSL, no regex extraction, the LLM is the parser.
Hints are not routed to specific sections; the full hint block goes into every
section prompt.  No echo/confirmation; hints flow silently.  Fresh each run,
no persistence.
"""

from __future__ import annotations

from pathlib import Path


def load_hints(raw: str | None) -> str:
    """Load user hints from inline text or a file path.

    Auto-detection logic:
    - If *raw* is ``None``, return ``""``.
    - If *raw* is a path to an existing file, read and return its content
      (UTF-8, stripped of leading/trailing whitespace).
    - Otherwise treat *raw* as inline hint text and return it stripped.

    Args:
        raw: Inline hint text, a file path, or ``None``.

    Returns:
        Resolved hint text (possibly empty string).
    """
    if raw is None:
        return ""

    # Check if it's a path to an existing file
    try:
        p = Path(raw)
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except OSError:
        # Path operations can raise on certain invalid strings -- treat as inline
        pass

    return raw.strip()
