r"""MIDI block injection into LilyPond source.

Ensures that LilyPond scores include a ``\midi { }`` block inside
``\score { }``, which is required for LilyPond to produce MIDI output
alongside the PDF.  Scores from Mutopia and PDMX typically include
``\layout { }`` but omit ``\midi { }``.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def _find_matching_brace(source: str, open_pos: int) -> int:
    """Find the matching closing brace for an opening brace.

    Args:
        source: The full source text.
        open_pos: Position of the opening '{'.

    Returns:
        Position of the matching '}', or -1 if not found.
    """
    depth = 0
    for i in range(open_pos, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def ensure_midi_block(ly_source: str) -> str:
    r"""Inject ``\midi { }`` into ``\score { }`` if not already present.

    Strategy:
    1. If ``\midi`` is already in the source, return unchanged.
    2. Find ``\layout { ... }`` and insert ``\midi { }`` after it.
    3. If no ``\layout``, find ``\score {`` and insert before its
       closing brace.
    4. If injection fails, log a warning and return unchanged.

    Args:
        ly_source: LilyPond source text.

    Returns:
        Source with ``\midi { }`` injected, or unchanged if already present
        or injection not possible.
    """
    # Already has \midi — nothing to do
    if re.search(r"\\midi\s*\{", ly_source):
        return ly_source

    # Strategy 1: Insert after \layout { ... }
    layout_match = re.search(r"\\layout\s*\{", ly_source)
    if layout_match:
        brace_start = ly_source.index("{", layout_match.start())
        brace_end = _find_matching_brace(ly_source, brace_start)
        if brace_end != -1:
            insert_pos = brace_end + 1
            return ly_source[:insert_pos] + "\n  \\midi { }" + ly_source[insert_pos:]

    # Strategy 2: Insert before closing brace of \score { ... }
    score_match = re.search(r"\\score\s*\{", ly_source)
    if score_match:
        brace_start = ly_source.index("{", score_match.start())
        brace_end = _find_matching_brace(ly_source, brace_start)
        if brace_end != -1:
            return ly_source[:brace_end] + "  \\midi { }\n" + ly_source[brace_end:]

    # Cannot inject — return unchanged
    logger.warning("Could not inject \\midi block: no \\score or \\layout found")
    return ly_source
