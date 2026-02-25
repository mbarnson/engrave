r"""Mutopia-specific ingestion: file discovery and header parsing.

Mutopia LilyPond scores use a custom ``\header`` block with fields like
``mutopiatitle``, ``mutopiacomposer``, etc.  This module extracts those
fields and maps them to the ``ScoreMetadata`` schema.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instrument family classification
# ---------------------------------------------------------------------------

_INSTRUMENT_FAMILY: dict[str, str] = {
    # Keyboard
    "piano": "keyboard",
    "organ": "keyboard",
    "harpsichord": "keyboard",
    "clavichord": "keyboard",
    "celesta": "keyboard",
    # Strings
    "violin": "strings",
    "viola": "strings",
    "cello": "strings",
    "contrabass": "strings",
    "double bass": "strings",
    "bass": "strings",
    "harp": "strings",
    "guitar": "strings",
    "lute": "strings",
    "mandolin": "strings",
    "banjo": "strings",
    "ukulele": "strings",
    # Woodwinds
    "flute": "woodwind",
    "piccolo": "woodwind",
    "oboe": "woodwind",
    "clarinet": "woodwind",
    "bassoon": "woodwind",
    "english horn": "woodwind",
    "recorder": "woodwind",
    "saxophone": "woodwind",
    # Brass
    "trumpet": "brass",
    "trombone": "brass",
    "french horn": "brass",
    "horn": "brass",
    "tuba": "brass",
    "cornet": "brass",
    "flugelhorn": "brass",
    # Percussion
    "timpani": "percussion",
    "drums": "percussion",
    "percussion": "percussion",
    "marimba": "percussion",
    "vibraphone": "percussion",
    "xylophone": "percussion",
    # Voice
    "voice": "vocal",
    "soprano": "vocal",
    "alto": "vocal",
    "tenor": "vocal",
    "baritone": "vocal",
    "bass voice": "vocal",
    "choir": "vocal",
    "chorus": "vocal",
}

# Directories to skip when discovering scores
_SKIP_DIRS = frozenset(
    {
        "documentation",
        "templates",
        "template",
        "web",
        "datafiles",
        ".git",
        "__pycache__",
    }
)


def _classify_instrument_family(instrument: str) -> str:
    """Classify an instrument name into its family.

    Performs case-insensitive matching against the lookup table.
    Falls back to ``"other"`` for unrecognised instruments.
    """
    lower = instrument.lower().strip()
    # Direct match
    if lower in _INSTRUMENT_FAMILY:
        return _INSTRUMENT_FAMILY[lower]
    # Partial match (e.g. "Piano and Cello" -> keyboard, "Bb Clarinet" -> woodwind)
    for key, family in _INSTRUMENT_FAMILY.items():
        if key in lower:
            return family
    return "other"


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

# Regex to find a \header { ... } block
_HEADER_BLOCK_RE = re.compile(r"\\header\s*\{", re.DOTALL)

# Fields we want to extract from Mutopia headers
_MUTOPIA_FIELDS = (
    "mutopiatitle",
    "mutopiacomposer",
    "mutopiainstrument",
    "style",
    "source",
    "license",
    "date",
    "mutopiaopus",
    "title",
    "composer",
    "instrument",
)


def _find_matching_brace(source: str, open_pos: int) -> int:
    """Find the matching closing brace for an opening brace."""
    depth = 0
    for i in range(open_pos, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_mutopia_header(ly_source: str) -> dict[str, str]:
    r"""Parse a ``\header { }`` block for Mutopia-specific fields.

    Extracts fields like ``mutopiatitle``, ``mutopiacomposer``, etc.
    Handles both quoted and unquoted values, and multiline values
    enclosed in quotes.

    Args:
        ly_source: LilyPond source text containing a header block.

    Returns:
        Dict of field name to value string.  Missing fields are omitted.
    """
    header_match = _HEADER_BLOCK_RE.search(ly_source)
    if not header_match:
        return {}

    brace_start = ly_source.index("{", header_match.start())
    brace_end = _find_matching_brace(ly_source, brace_start)
    if brace_end == -1:
        return {}

    header_block = ly_source[brace_start + 1 : brace_end]

    result: dict[str, str] = {}
    for field_name in _MUTOPIA_FIELDS:
        # Match field = "value" (possibly multiline) or field = value
        pattern = re.compile(
            rf'{field_name}\s*=\s*"((?:[^"\\]|\\.)*)"',
            re.DOTALL,
        )
        match = pattern.search(header_block)
        if match:
            # Clean up multiline values
            value = match.group(1).strip().replace("\n", " ")
            result[field_name] = value
            continue

        # Try unquoted value (single word or simple string)
        pattern_unquoted = re.compile(rf"{field_name}\s*=\s*(\S+)")
        match = pattern_unquoted.search(header_block)
        if match:
            result[field_name] = match.group(1).strip()

    return result


def map_mutopia_to_metadata(header: dict[str, str]) -> dict:
    """Map Mutopia header fields to ScoreMetadata-compatible fields.

    Maps:
    - ``mutopiacomposer`` -> ``composer``
    - ``mutopiainstrument`` -> ``instrument`` + ``instrument_family``
    - ``style`` -> ``style``
    - ``date`` -> infers ``era`` if recognisable
    - ``mutopiatitle`` -> ``title``

    Args:
        header: Dict from ``extract_mutopia_header``.

    Returns:
        Dict with ScoreMetadata-compatible keys.
    """
    metadata: dict = {}

    # Composer: prefer mutopiacomposer, fallback to composer
    composer = header.get("mutopiacomposer") or header.get("composer", "")
    if composer:
        metadata["composer"] = composer

    # Instrument
    instrument = header.get("mutopiainstrument") or header.get("instrument", "")
    if instrument:
        metadata["instrument"] = instrument
        metadata["instrument_family"] = _classify_instrument_family(instrument)

    # Style
    style = header.get("style", "")
    if style:
        metadata["style"] = style

    # Era inference from style or date
    era = _infer_era(header)
    if era:
        metadata["era"] = era

    # Title
    title = header.get("mutopiatitle") or header.get("title", "")
    if title:
        metadata["title"] = title

    return metadata


def _infer_era(header: dict[str, str]) -> str:
    """Infer musical era from style or date fields.

    Mapping:
    - ``Baroque`` style -> ``Baroque``
    - ``Classical`` style -> ``Classical``
    - ``Romantic`` style -> ``Romantic``
    - Date-based: pre-1600 -> Renaissance, 1600-1750 -> Baroque,
      1750-1820 -> Classical, 1820-1900 -> Romantic, 1900+ -> Modern
    """
    style = header.get("style", "").lower()
    era_map = {
        "baroque": "Baroque",
        "classical": "Classical",
        "romantic": "Romantic",
        "modern": "Modern",
        "renaissance": "Renaissance",
        "contemporary": "Modern",
        "jazz": "Modern",
        "folk": "",
        "popular": "Modern",
    }
    for key, era in era_map.items():
        if key in style and era:
            return era

    # Try date-based inference
    date_str = header.get("date", "")
    year_match = re.search(r"(\d{4})", date_str)
    if year_match:
        year = int(year_match.group(1))
        if year < 1600:
            return "Renaissance"
        if year < 1750:
            return "Baroque"
        if year < 1820:
            return "Classical"
        if year < 1900:
            return "Romantic"
        return "Modern"

    return ""


def discover_mutopia_scores(repo_path: Path) -> list[Path]:
    """Walk a Mutopia repository directory to find all ``.ly`` files.

    Skips documentation, template, and web directories.  Returns a
    sorted list of absolute paths.

    Args:
        repo_path: Root of the Mutopia repository clone.

    Returns:
        Sorted list of Path objects for ``.ly`` files.
    """
    if not repo_path.is_dir():
        logger.warning("Mutopia repo path does not exist: %s", repo_path)
        return []

    ly_files: list[Path] = []
    for ly_path in repo_path.rglob("*.ly"):
        # Skip files in excluded directories
        parts = set(ly_path.relative_to(repo_path).parts)
        if parts & _SKIP_DIRS:
            continue
        ly_files.append(ly_path)

    ly_files.sort()
    return ly_files
