"""Music-aware phrase chunking for LilyPond scores.

Detects structural boundaries (rehearsal marks, double barlines, key/time changes,
repeat signs) and splits scores into phrase-level chunks with configurable overlap.
Repeats, D.S., and coda structures are expanded (unrolled) before chunking.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Boundary patterns — compiled regexes for LilyPond structural cues
# ---------------------------------------------------------------------------

_BOUNDARY_PATTERN_STRINGS = [
    r"\\mark\s+\\default",  # Rehearsal marks (default)
    r"\\mark\s+\d+",  # Numbered rehearsal marks
    r'\\bar\s+"\\|\\|"',  # Double barlines
    r'\\bar\s+"\\.:',  # Repeat barlines
    r"\\key\s+\w+\s*\\(?:major|minor)",  # Key changes
    r"\\time\s+\d+/\d+",  # Time signature changes
    r"\\repeat\s+(?:volta|segno)",  # Repeat structures
    r"\\section(?!\w)",  # Section divisions (word boundary)
    r"\\fine(?!\w)",  # Fine marks
    r"\\segnoMark(?!\w)",  # Segno marks
    r"\\codaMark(?!\w)",  # Coda marks
]

BOUNDARY_PATTERNS: list[re.Pattern[str]] = [re.compile(p) for p in _BOUNDARY_PATTERN_STRINGS]


def find_phrase_boundaries(ly_source: str) -> list[int]:
    """Find character positions of structural boundaries in LilyPond source.

    Scans the source for rehearsal marks, double barlines, key/time changes,
    repeat structures, section divisions, fine/segno/coda marks.

    Returns:
        Sorted, deduplicated list of character positions.
    """
    boundaries: set[int] = set()
    for pattern in BOUNDARY_PATTERNS:
        for match in pattern.finditer(ly_source):
            boundaries.add(match.start())
    return sorted(boundaries)


# ---------------------------------------------------------------------------
# Repeat expansion
# ---------------------------------------------------------------------------


def _find_matching_brace(source: str, open_pos: int) -> int:
    """Find the position of the matching closing brace for an opening brace.

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


def _extract_braced_block(source: str, start: int) -> tuple[str, int] | None:
    """Extract content within braces starting from a position.

    Scans forward from `start` to find the first '{', then extracts
    the content up to its matching '}'.

    Returns:
        Tuple of (content_inside_braces, position_after_closing_brace) or None.
    """
    brace_start = source.find("{", start)
    if brace_start == -1:
        return None
    brace_end = _find_matching_brace(source, brace_start)
    if brace_end == -1:
        return None
    return source[brace_start + 1 : brace_end].strip(), brace_end + 1


def _extract_alternative_blocks(source: str, start: int) -> tuple[list[str], int] | None:
    r"""Extract alternative blocks from \\alternative { { alt1 } { alt2 } ... }.

    Args:
        source: The full source text.
        start: Position to start scanning from (after the repeat body).

    Returns:
        Tuple of (list_of_alternative_contents, position_after_alternatives) or None.
    """
    # Look for \alternative after the repeat body
    remaining = source[start:]
    alt_match = re.match(r"\s*\\alternative\s*\{", remaining)
    if not alt_match:
        return None

    alt_block_start = start + alt_match.end() - 1  # position of the outer '{'
    alt_block_end = _find_matching_brace(source, alt_block_start)
    if alt_block_end == -1:
        return None

    # Extract inner content of the \alternative { ... } block
    inner = source[alt_block_start + 1 : alt_block_end].strip()

    # Parse individual alternative blocks: { alt1 } { alt2 } ...
    alternatives: list[str] = []
    pos = 0
    while pos < len(inner):
        brace_pos = inner.find("{", pos)
        if brace_pos == -1:
            break
        end_pos = _find_matching_brace(inner, brace_pos)
        if end_pos == -1:
            break
        alternatives.append(inner[brace_pos + 1 : end_pos].strip())
        pos = end_pos + 1

    return alternatives, alt_block_end + 1


def expand_repeats(ly_source: str) -> str:
    r"""Expand \repeat volta and \repeat segno structures into linear form.

    Handles:
    - \repeat volta N { body } \alternative { { alt1 } { alt2 } } -> body+alt1, body+alt2, ...
    - \repeat volta N { body } (no alternatives) -> body repeated N times
    - Nested repeats are handled by recursive expansion.

    This is best-effort: complex nested repeats may not fully unroll.

    Args:
        ly_source: LilyPond source text.

    Returns:
        Source with repeat structures expanded into linear form.
    """
    result = ly_source
    # Keep expanding until no more \repeat patterns are found
    max_iterations = 20  # safety valve for pathological nesting
    for _ in range(max_iterations):
        match = re.search(r"\\repeat\s+(volta|segno)\s+(\d+)\s*\{", result)
        if not match:
            break

        repeat_count = int(match.group(2))
        repeat_start = match.start()

        # Extract the repeat body
        body_brace_start = result.index("{", match.start() + len(match.group(0)) - 1)
        body = _extract_braced_block(result, body_brace_start)
        if body is None:
            # Can't parse — leave as-is and break to avoid infinite loop
            logger.warning("Could not parse repeat body at position %d", repeat_start)
            break

        body_content, after_body = body

        # Check for \alternative block
        alt_result = _extract_alternative_blocks(result, after_body)

        if alt_result is not None:
            alternatives, after_alt = alt_result
            # Expand: for each repetition, body + corresponding alternative
            # If more repetitions than alternatives, last alt is repeated
            expanded_parts: list[str] = []
            for i in range(repeat_count):
                expanded_parts.append(body_content)
                if alternatives:
                    alt_index = min(i, len(alternatives) - 1)
                    expanded_parts.append(alternatives[alt_index])
            expanded = "\n".join(expanded_parts)
            result = result[:repeat_start] + expanded + result[after_alt:]
        else:
            # No alternatives — just repeat the body N times
            expanded = "\n".join([body_content] * repeat_count)
            result = result[:repeat_start] + expanded + result[after_body:]

    return result


# ---------------------------------------------------------------------------
# Bar counting
# ---------------------------------------------------------------------------


def _count_bars(ly_fragment: str) -> int:
    """Count bar checks (|) in a LilyPond fragment.

    Uses simple counting of '|' characters that are not inside strings or
    part of other barline commands. This is a best-effort count.

    Args:
        ly_fragment: A LilyPond source fragment.

    Returns:
        Number of bar checks found.
    """
    count = 0
    in_string = False
    i = 0
    while i < len(ly_fragment):
        ch = ly_fragment[i]
        if ch == '"':
            in_string = not in_string
        elif ch == "|" and not in_string:
            # Check it's not part of "||" inside a \bar command
            # Simple heuristic: standalone | is a bar check
            count += 1
        elif ch == "%" and not in_string:
            # Skip to end of line (line comment)
            newline = ly_fragment.find("\n", i)
            if newline == -1:
                break
            i = newline
        i += 1
    return count


# ---------------------------------------------------------------------------
# Splitting at boundaries
# ---------------------------------------------------------------------------


def _generate_bar_boundaries(ly_source: str, target_bars: int = 8) -> list[int]:
    """Generate synthetic boundaries at bar-check positions for fixed-bar chunking.

    When no structural boundaries exist, this function creates boundaries every
    `target_bars` bar checks to produce chunks in the 4-8 bar range.

    Args:
        ly_source: LilyPond source text.
        target_bars: Number of bars between synthetic boundaries.

    Returns:
        Sorted list of character positions for synthetic boundaries.
    """
    bar_positions: list[int] = []
    in_string = False
    for i, ch in enumerate(ly_source):
        if ch == '"':
            in_string = not in_string
        elif ch == "|" and not in_string:
            bar_positions.append(i)

    boundaries: list[int] = []
    for j in range(target_bars, len(bar_positions), target_bars):
        # Place the boundary right after the bar check
        boundaries.append(bar_positions[j - 1] + 1)

    return boundaries


def _split_at_boundaries(
    ly_source: str,
    boundaries: list[int],
    target_bars: tuple[int, int] = (4, 8),
    overlap_bars: int = 1,
) -> list[tuple[str, int, int]]:
    """Split source at boundary positions with bar-count merging and overlap.

    Splits the source at detected boundary positions. If no boundaries are
    provided, generates synthetic boundaries at bar-check intervals (fallback).
    Adjacent small chunks (below target_bars[0]) are merged to reach the
    4-8 bar target range. Overlap is added from the preceding chunk's tail
    to capture pickup notes and cadential material.

    Args:
        ly_source: LilyPond source text (should have repeats already expanded).
        boundaries: Sorted list of character positions for structural breaks.
        target_bars: (min_bars, max_bars) target range for chunks.
        overlap_bars: Number of bars to overlap between adjacent chunks.

    Returns:
        List of (source_fragment, bar_start, bar_end) tuples.
    """
    if not ly_source.strip():
        return []

    # If no structural boundaries, fall back to fixed bar-count chunking
    if not boundaries:
        boundaries = _generate_bar_boundaries(ly_source, target_bars=target_bars[1])

    # Create split points from boundaries
    split_points = [0, *boundaries, len(ly_source)]
    # Remove duplicates and sort
    split_points = sorted(set(split_points))

    # Create raw segments
    raw_segments: list[str] = []
    for i in range(len(split_points) - 1):
        segment = ly_source[split_points[i] : split_points[i + 1]]
        if segment.strip():
            raw_segments.append(segment)

    if not raw_segments:
        return []

    # Merge small segments to meet the minimum bar target
    min_bars, _max_bars = target_bars
    merged_segments: list[str] = []
    current = raw_segments[0]
    for seg in raw_segments[1:]:
        bar_count = _count_bars(current)
        if bar_count < min_bars:
            current = current + seg
        else:
            merged_segments.append(current)
            current = seg
    merged_segments.append(current)

    # Calculate bar ranges and add overlap
    result: list[tuple[str, int, int]] = []
    cumulative_bar = 1
    for i, segment in enumerate(merged_segments):
        bars_in_segment = max(_count_bars(segment), 1)
        bar_start = cumulative_bar
        bar_end = cumulative_bar + bars_in_segment - 1

        # Add overlap from the previous chunk's tail
        if i > 0 and overlap_bars > 0:
            prev_segment = merged_segments[i - 1]
            # Find the last N bars of the previous segment to use as overlap
            overlap_source = _extract_tail_bars(prev_segment, overlap_bars)
            if overlap_source:
                segment = overlap_source + "\n" + segment
                bar_start = max(1, bar_start - overlap_bars)

        result.append((segment, bar_start, bar_end))
        cumulative_bar += bars_in_segment

    return result


def _extract_tail_bars(ly_fragment: str, n_bars: int) -> str:
    """Extract the last N bars from a LilyPond fragment.

    Finds bar check positions and returns content from the Nth-to-last bar check
    to the end of the fragment.

    Args:
        ly_fragment: LilyPond source fragment.
        n_bars: Number of bars to extract from the tail.

    Returns:
        The tail portion of the fragment, or empty string if not enough bars.
    """
    # Find all bar check positions
    bar_positions: list[int] = []
    in_string = False
    for i, ch in enumerate(ly_fragment):
        if ch == '"':
            in_string = not in_string
        elif ch == "|" and not in_string:
            bar_positions.append(i)

    if len(bar_positions) < n_bars:
        return ""

    # Get content from n_bars before the end
    cut_pos = bar_positions[-(n_bars)]
    return ly_fragment[cut_pos:].strip()


# ---------------------------------------------------------------------------
# Instrument part extraction
# ---------------------------------------------------------------------------


def _extract_instrument_parts(ly_source: str) -> dict[str, str]:
    r"""Parse a multi-part score to extract individual instrument voices.

    Looks for \new Staff \with { instrumentName = "..." } { ... } blocks
    and extracts each instrument's content.

    Args:
        ly_source: LilyPond source text.

    Returns:
        Dict of instrument_name -> ly_source content.
    """
    parts: dict[str, str] = {}

    # Pattern to match \new Staff with optional \with block
    staff_pattern = re.compile(
        r"\\new\s+Staff\s+"
        r"(?:\\with\s*\{([^}]*)\}\s*)?"  # optional \with { ... }
        r"\{",
        re.DOTALL,
    )

    for match in staff_pattern.finditer(ly_source):
        # Extract instrument name from \with block if present
        with_block = match.group(1) or ""
        name_match = re.search(r'instrumentName\s*=\s*"([^"]*)"', with_block)
        instrument_name = name_match.group(1) if name_match else f"Part_{len(parts) + 1}"

        # Extract the staff content
        brace_start = ly_source.index("{", match.start() + len(match.group(0)) - 1)
        brace_end = _find_matching_brace(ly_source, brace_start)
        if brace_end == -1:
            continue

        content = ly_source[brace_start + 1 : brace_end].strip()
        parts[instrument_name] = content

    return parts


def _is_multi_part(ly_source: str) -> bool:
    r"""Check if a LilyPond source contains multiple \new Staff blocks."""
    staff_count = len(re.findall(r"\\new\s+Staff", ly_source))
    return staff_count > 1


def _strip_structure(ly_source: str) -> str:
    r"""Strip outer \score, \new Staff, \version, \header blocks to get music content.

    For single-instrument scores, extracts just the music content from within
    the score/staff structure.
    """
    # Try to find the innermost Staff content
    staff_match = re.search(r"\\new\s+Staff\s*(?:\\with\s*\{[^}]*\}\s*)?\{", ly_source, re.DOTALL)
    if staff_match:
        brace_start = ly_source.index("{", staff_match.start() + len(staff_match.group(0)) - 1)
        brace_end = _find_matching_brace(ly_source, brace_start)
        if brace_end != -1:
            return ly_source[brace_start + 1 : brace_end].strip()

    # Try to find content within \score { ... }
    score_match = re.search(r"\\score\s*\{", ly_source)
    if score_match:
        brace_start = ly_source.index("{", score_match.start())
        brace_end = _find_matching_brace(ly_source, brace_start)
        if brace_end != -1:
            content = ly_source[brace_start + 1 : brace_end].strip()
            # Remove \layout and \midi blocks
            content = re.sub(r"\\layout\s*\{[^}]*\}", "", content)
            content = re.sub(r"\\midi\s*\{[^}]*\}", "", content)
            return content.strip()

    return ly_source


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def chunk_score(
    ly_source: str,
    source_path: str,
    source_collection: str,
    header_metadata: dict | None = None,
) -> list[dict]:
    """Chunk a LilyPond score into phrase-level segments.

    Main entry point for the chunking pipeline:
    1. Expand repeat structures (unroll for linear chunks matching performer reading order).
    2. Detect structural boundaries (rehearsal marks, barlines, key/time changes).
    3. Split at boundaries with 1-bar overlap for pickup/cadential continuity.
    4. For multi-part scores: produce both single-instrument and full-score vertical chunks.

    Args:
        ly_source: Complete LilyPond source text.
        source_path: Path to the source file (for metadata).
        source_collection: Collection name ("mutopia", "pdmx", "test", etc.).
        header_metadata: Optional pre-extracted header metadata dict.

    Returns:
        List of dicts with keys: source, bar_start, bar_end, chunk_type,
        instrument, chunk_index. These are raw chunker output -- Plan 03's
        pipeline converts them to Chunk model objects with full metadata.
    """
    chunks: list[dict] = []

    if _is_multi_part(ly_source):
        chunks = _chunk_multi_part(ly_source, source_path, source_collection, header_metadata)
    else:
        chunks = _chunk_single_part(ly_source, source_path, source_collection, header_metadata)

    # Assign sequential chunk indices
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i

    return chunks


def _chunk_single_part(
    ly_source: str,
    source_path: str,
    source_collection: str,
    header_metadata: dict | None = None,
) -> list[dict]:
    """Chunk a single-instrument score."""
    # Extract music content from structure
    music_content = _strip_structure(ly_source)

    # Expand repeats
    expanded = expand_repeats(music_content)

    # Find boundaries
    boundaries = find_phrase_boundaries(expanded)

    # Split at boundaries with overlap
    segments = _split_at_boundaries(expanded, boundaries, target_bars=(4, 8), overlap_bars=1)

    chunks: list[dict] = []
    for source_fragment, bar_start, bar_end in segments:
        chunks.append(
            {
                "source": source_fragment,
                "bar_start": bar_start,
                "bar_end": bar_end,
                "chunk_type": "single_instrument",
                "instrument": None,
                "chunk_index": 0,  # will be reassigned
            }
        )

    return chunks


def _chunk_multi_part(
    ly_source: str,
    source_path: str,
    source_collection: str,
    header_metadata: dict | None = None,
) -> list[dict]:
    """Chunk a multi-part score into single-instrument and full-score chunks."""
    parts = _extract_instrument_parts(ly_source)
    chunks: list[dict] = []

    # Per-instrument chunks
    for instrument_name, part_source in parts.items():
        expanded = expand_repeats(part_source)
        boundaries = find_phrase_boundaries(expanded)
        segments = _split_at_boundaries(expanded, boundaries, target_bars=(4, 8), overlap_bars=1)

        for source_fragment, bar_start, bar_end in segments:
            chunks.append(
                {
                    "source": source_fragment,
                    "bar_start": bar_start,
                    "bar_end": bar_end,
                    "chunk_type": "single_instrument",
                    "instrument": instrument_name,
                    "chunk_index": 0,  # will be reassigned
                }
            )

    # Full-score vertical chunks: combine all parts at the same bar ranges
    # Use the first instrument's chunking as the reference for bar ranges
    if parts:
        first_instrument = next(iter(parts.values()))
        expanded_ref = expand_repeats(first_instrument)
        boundaries_ref = find_phrase_boundaries(expanded_ref)
        ref_segments = _split_at_boundaries(
            expanded_ref, boundaries_ref, target_bars=(4, 8), overlap_bars=1
        )

        for _, bar_start, bar_end in ref_segments:
            # Combine sources from all parts for this bar range
            combined_parts: list[str] = []
            for instrument_name, part_source in parts.items():
                expanded_part = expand_repeats(part_source)
                # Extract the approximate region for this bar range
                part_segments = _split_at_boundaries(
                    expanded_part,
                    find_phrase_boundaries(expanded_part),
                    target_bars=(4, 8),
                    overlap_bars=1,
                )
                # Find the segment(s) covering this bar range
                for seg_source, seg_start, seg_end in part_segments:
                    if seg_start <= bar_end and seg_end >= bar_start:
                        combined_parts.append(f"% {instrument_name}\n{seg_source}")
                        break

            if combined_parts:
                chunks.append(
                    {
                        "source": "\n\n".join(combined_parts),
                        "bar_start": bar_start,
                        "bar_end": bar_end,
                        "chunk_type": "full_score",
                        "instrument": "all",
                        "chunk_index": 0,  # will be reassigned
                    }
                )

    return chunks
