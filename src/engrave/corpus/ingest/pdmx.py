"""PDMX-specific ingestion: MusicXML discovery, conversion, and corpus import.

PDMX provides ~254K MusicXML scores.  This module discovers them, converts
them to LilyPond via ``musicxml2ly`` (ships with LilyPond), stores the
original MusicXML alongside the conversion, and feeds the result into the
shared ingestion pipeline.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from engrave.corpus.ingest.pipeline import IngestionResult, ingest_score

if TYPE_CHECKING:
    from engrave.corpus.store import CorpusStore
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

logger = logging.getLogger(__name__)

# MusicXML file extensions to discover
_MXL_EXTENSIONS = frozenset({".mxl", ".musicxml", ".xml"})


def discover_pdmx_scores(
    data_path: Path,
    rated_only: bool = True,
) -> list[Path]:
    """Find MusicXML files in the PDMX data directory.

    If ``rated_only`` is True (the default, per research recommendation),
    attempts to filter to the deduplicated+rated subset using PDMX metadata
    files.  Falls back to all MusicXML files if no metadata is available.

    Args:
        data_path: Root of the PDMX data directory.
        rated_only: Whether to limit to the rated subset.

    Returns:
        Sorted list of Path objects for MusicXML files.
    """
    if not data_path.is_dir():
        logger.warning("PDMX data path does not exist: %s", data_path)
        return []

    # Look for the rated subset list (PDMX convention)
    rated_list_path = data_path / "rated_files.txt"
    rated_set: set[str] | None = None
    if rated_only and rated_list_path.exists():
        try:
            rated_set = {
                line.strip()
                for line in rated_list_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            logger.info("Loaded %d rated file entries from PDMX metadata", len(rated_set))
        except OSError:
            rated_set = None

    mxl_files: list[Path] = []
    for ext in _MXL_EXTENSIONS:
        for path in data_path.rglob(f"*{ext}"):
            if rated_set is not None:
                relative = str(path.relative_to(data_path))
                if relative not in rated_set:
                    continue
            mxl_files.append(path)

    mxl_files.sort()
    return mxl_files


def convert_musicxml_to_ly(
    mxl_path: Path,
    output_dir: Path,
) -> tuple[Path | None, str | None]:
    """Convert a MusicXML file to LilyPond via ``musicxml2ly``.

    ``musicxml2ly`` ships with LilyPond.  It reads MusicXML and writes
    a ``.ly`` file.

    Args:
        mxl_path: Path to the MusicXML file (.mxl, .musicxml, .xml).
        output_dir: Directory for the output .ly file.

    Returns:
        Tuple of ``(ly_path, None)`` on success, or ``(None, error_message)``
        on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{mxl_path.stem}.ly"

    try:
        result = subprocess.run(
            [
                "musicxml2ly",
                "--output",
                str(output_file),
                str(mxl_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return None, "musicxml2ly not found. Ensure LilyPond is installed."
    except subprocess.TimeoutExpired:
        return None, "musicxml2ly conversion timed out after 60 seconds"

    if result.returncode != 0:
        return None, f"musicxml2ly failed (rc={result.returncode}): {result.stderr}"

    if not output_file.exists():
        return None, f"musicxml2ly did not produce output file: {output_file}"

    return output_file, None


def store_original_mxl(mxl_path: Path, storage_dir: Path) -> Path:
    """Copy the original MusicXML file to the storage directory.

    Stores the original alongside the converted LilyPond per user decision
    (keep both formats for provenance and potential re-conversion).

    Args:
        mxl_path: Path to the original MusicXML file.
        storage_dir: Directory where the copy should be stored.

    Returns:
        Path to the stored copy.
    """
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / mxl_path.name
    shutil.copy2(mxl_path, dest)
    return dest


async def ingest_pdmx_corpus(
    data_path: Path,
    compiler: LilyPondCompiler,
    store: CorpusStore,
    router: InferenceRouter | None = None,
    rated_only: bool = True,
    max_scores: int | None = None,
) -> list[IngestionResult]:
    """Ingest scores from a PDMX data directory into the corpus.

    For each MusicXML file:
    1. Convert via ``musicxml2ly``
    2. Store original MusicXML alongside
    3. Read converted LilyPond
    4. Ingest via shared pipeline with ``source_collection="pdmx"``

    Args:
        data_path: Root of the PDMX data directory.
        compiler: LilyPondCompiler for validation.
        store: CorpusStore for indexing.
        router: Optional InferenceRouter for compile-fix loop.
        rated_only: Whether to limit to the rated subset.
        max_scores: Maximum number of scores to ingest.

    Returns:
        List of IngestionResult, one per score file.
    """
    scores = discover_pdmx_scores(data_path, rated_only=rated_only)
    if max_scores is not None:
        scores = scores[:max_scores]

    logger.info("Discovered %d PDMX scores to ingest", len(scores))
    results: list[IngestionResult] = []

    conversion_dir = data_path / "_converted_ly"
    originals_dir = data_path / "_originals"

    for i, mxl_path in enumerate(scores):
        if (i + 1) % 100 == 0:
            logger.info("PDMX ingestion progress: %d/%d", i + 1, len(scores))

        # Convert MusicXML to LilyPond
        ly_path, error = convert_musicxml_to_ly(mxl_path, conversion_dir)
        if error is not None:
            results.append(
                IngestionResult(
                    source_path=mxl_path,
                    skipped=True,
                    skip_reason=f"Conversion failed: {error}",
                    errors=[error],
                )
            )
            continue

        assert ly_path is not None  # Guaranteed by convert success

        # Store original MusicXML
        store_original_mxl(mxl_path, originals_dir)

        # Read converted LilyPond
        try:
            ly_source = ly_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            results.append(
                IngestionResult(
                    source_path=mxl_path,
                    skipped=True,
                    skip_reason=f"Could not read converted file: {e}",
                    errors=[str(e)],
                )
            )
            continue

        # PDMX does not have Mutopia-style headers; provide minimal metadata
        header_metadata = {
            "source": str(mxl_path),
        }

        ingestion_result = await ingest_score(
            ly_source=ly_source,
            source_path=mxl_path,
            source_collection="pdmx",
            header_metadata=header_metadata,
            compiler=compiler,
            store=store,
            router=router,
        )
        results.append(ingestion_result)

    ingested = sum(1 for r in results if not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    total_chunks = sum(r.chunks_indexed for r in results)
    logger.info(
        "PDMX ingestion complete: %d ingested, %d skipped, %d total chunks",
        ingested,
        skipped,
        total_chunks,
    )

    return results
