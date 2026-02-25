"""Shared ingestion pipeline: compile, chunk, extract metadata, index.

Orchestrates the full ingestion flow for a single LilyPond score:
MIDI injection -> compilation -> chunking -> metadata extraction ->
description generation -> ChromaDB indexing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from engrave.corpus.chunker import chunk_score
from engrave.corpus.description import generate_description
from engrave.corpus.ingest.midi_injection import ensure_midi_block
from engrave.corpus.ingest.mutopia import (
    discover_mutopia_scores,
    extract_mutopia_header,
    map_mutopia_to_metadata,
)
from engrave.corpus.metadata import extract_metadata
from engrave.corpus.models import Chunk, ScoreMetadata

if TYPE_CHECKING:
    from engrave.corpus.store import CorpusStore
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

logger = logging.getLogger(__name__)

# Minimum note count to consider a score non-degenerate
_MIN_NOTE_COUNT = 2
_MIN_SOURCE_LENGTH = 10


@dataclass
class IngestionResult:
    """Result of ingesting a single score."""

    source_path: Path
    chunks_indexed: int = 0
    midi_generated: bool = False
    errors: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


def _count_notes_quick(ly_source: str) -> int:
    """Quick note count for degenerate-case filtering.

    Counts characters a-g that are likely note names (outside of commands).
    This is intentionally rough -- just a quality gate.
    """
    import re

    # Strip commands and strings
    cleaned = re.sub(r"\\[a-zA-Z]+", " ", ly_source)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    cleaned = re.sub(r"%[^\n]*", "", cleaned)
    notes = re.findall(r"(?<![a-zA-Z])[a-g](?![a-zA-Z])", cleaned)
    return len(notes)


def _extract_midi_features(midi_path: Path) -> dict | None:
    """Extract MIDI features (velocity histogram, pitch range, rhythmic complexity).

    Returns None if mido is not available or the file cannot be read.
    """
    try:
        import mido
    except ImportError:
        return None

    try:
        mid = mido.MidiFile(str(midi_path))
    except Exception:
        logger.warning("Could not read MIDI file: %s", midi_path)
        return None

    velocities: list[int] = []
    pitches: list[int] = []
    note_on_times: list[float] = []
    current_time = 0.0

    for track in mid.tracks:
        current_time = 0.0
        for msg in track:
            current_time += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                velocities.append(msg.velocity)
                pitches.append(msg.note)
                note_on_times.append(current_time)

    if not pitches:
        return None

    # Velocity histogram (8 bins for 0-127)
    vel_bins = [0] * 8
    for v in velocities:
        bin_idx = min(v // 16, 7)
        vel_bins[bin_idx] += 1

    # Rhythmic complexity: variance of inter-onset intervals
    ioi_variance = 0.0
    if len(note_on_times) > 1:
        intervals = [note_on_times[i + 1] - note_on_times[i] for i in range(len(note_on_times) - 1)]
        mean_interval = sum(intervals) / len(intervals)
        ioi_variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)

    return {
        "velocity_histogram": vel_bins,
        "pitch_range": [min(pitches), max(pitches)],
        "mean_velocity": round(sum(velocities) / len(velocities), 1),
        "note_count": len(pitches),
        "rhythmic_complexity": round(ioi_variance, 4),
    }


async def ingest_score(
    ly_source: str,
    source_path: Path,
    source_collection: str,
    header_metadata: dict,
    compiler: LilyPondCompiler,
    store: CorpusStore,
    router: InferenceRouter | None = None,
) -> IngestionResult:
    """Ingest a single LilyPond score into the corpus.

    Full pipeline:
    1. Quality filter (degenerate cases)
    2. MIDI block injection
    3. Compilation (with fix loop if router provided)
    4. Chunking
    5. Metadata extraction + description generation per chunk
    6. MIDI feature extraction (if available)
    7. ChromaDB indexing

    Args:
        ly_source: LilyPond source text.
        source_path: Path to the original file.
        source_collection: Collection identifier ("mutopia", "pdmx").
        header_metadata: Pre-extracted header metadata dict.
        compiler: LilyPondCompiler for validation.
        store: CorpusStore for indexing.
        router: Optional InferenceRouter for compile-fix loop.

    Returns:
        IngestionResult with statistics and errors.
    """
    result = IngestionResult(source_path=source_path)

    # 1. Quality filter
    if len(ly_source) < _MIN_SOURCE_LENGTH:
        result.skipped = True
        result.skip_reason = f"Source too short ({len(ly_source)} chars)"
        return result

    note_count = _count_notes_quick(ly_source)
    if note_count < _MIN_NOTE_COUNT:
        result.skipped = True
        result.skip_reason = f"Too few notes ({note_count})"
        return result

    # 2. MIDI injection
    ly_source = ensure_midi_block(ly_source)

    # 3. Compilation
    compile_result = compiler.compile(ly_source)

    if not compile_result.success:
        # Try compile-fix loop if router is available
        if router is not None:
            from engrave.lilypond.fixer import compile_with_fix_loop

            fix_result = await compile_with_fix_loop(
                source=ly_source,
                router=router,
                compiler=compiler,
            )
            if fix_result.success:
                ly_source = fix_result.source
                compile_result = compiler.compile(ly_source)
            else:
                result.skipped = True
                result.skip_reason = f"Compilation failed after fix loop: {fix_result.final_errors}"
                result.errors = [str(e) for e in fix_result.final_errors]
                return result
        else:
            result.skipped = True
            result.skip_reason = f"Compilation failed: {compile_result.stderr}"
            result.errors = [compile_result.stderr]
            return result

    # 4. Check for MIDI output
    if compile_result.output_path:
        midi_path = compile_result.output_path.with_suffix(".midi")
        if midi_path.exists():
            result.midi_generated = True

    # 5. Chunking
    raw_chunks = chunk_score(
        ly_source=ly_source,
        source_path=str(source_path),
        source_collection=source_collection,
        header_metadata=header_metadata,
    )

    if not raw_chunks:
        result.skipped = True
        result.skip_reason = "No chunks produced"
        return result

    # 6. Build Chunk model objects
    chunks: list[Chunk] = []
    for raw_chunk in raw_chunks:
        bar_start = raw_chunk["bar_start"]
        bar_end = raw_chunk["bar_end"]
        chunk_type = raw_chunk["chunk_type"]
        instrument_from_chunk = raw_chunk.get("instrument")

        # Extract metadata for this chunk
        chunk_metadata = extract_metadata(
            ly_fragment=raw_chunk["source"],
            bar_start=bar_start,
            bar_end=bar_end,
            header_metadata=header_metadata,
        )

        # Merge header metadata into chunk metadata for description
        desc_metadata = {
            **header_metadata,
            **chunk_metadata,
            "source_collection": source_collection,
        }
        description = generate_description(desc_metadata)

        # Resolve instrument: chunk-level > metadata-level > header-level
        instrument = (
            instrument_from_chunk
            or chunk_metadata.get("instrument")
            or header_metadata.get("instrument", "unknown")
        )
        instrument_family = header_metadata.get("instrument_family", "")
        if not instrument_family and instrument:
            from engrave.corpus.ingest.mutopia import _classify_instrument_family

            instrument_family = _classify_instrument_family(instrument)

        # Build ScoreMetadata
        score_meta = ScoreMetadata(
            source_collection=source_collection,
            source_path=str(source_path),
            chunk_index=raw_chunk["chunk_index"],
            bar_start=bar_start,
            bar_end=bar_end,
            chunk_type=chunk_type,
            key_signature=chunk_metadata.get("key_signature") or "",
            time_signature=chunk_metadata.get("time_signature") or "",
            tempo=chunk_metadata.get("tempo") or "",
            instrument=instrument or "",
            instrument_family=instrument_family,
            clef=chunk_metadata.get("clef") or "",
            ensemble_type=header_metadata.get("ensemble_type", "solo"),
            style=header_metadata.get("style", ""),
            composer=header_metadata.get("composer", ""),
            note_density=chunk_metadata.get("note_density"),
            dynamic_range=chunk_metadata.get("dynamic_range") or "",
            articulation_count=chunk_metadata.get("articulation_count", 0),
            has_chord_symbols=chunk_metadata.get("has_chord_symbols", False),
            has_midi=result.midi_generated,
        )

        # MIDI features
        midi_features = None
        if result.midi_generated and compile_result.output_path:
            midi_path = compile_result.output_path.with_suffix(".midi")
            if midi_path.exists():
                midi_features = _extract_midi_features(midi_path)

        chunk = Chunk(
            id=f"{source_collection}_{source_path.stem}_{raw_chunk['chunk_index']}_{uuid.uuid4().hex[:8]}",
            source=raw_chunk["source"],
            description=description,
            metadata=score_meta,
            midi_features=midi_features,
        )
        chunks.append(chunk)

    # 7. Index into store
    if chunks:
        store.add_chunks(chunks)
        result.chunks_indexed = len(chunks)

    return result


async def ingest_mutopia_corpus(
    repo_path: Path,
    compiler: LilyPondCompiler,
    store: CorpusStore,
    router: InferenceRouter | None = None,
    max_scores: int | None = None,
) -> list[IngestionResult]:
    """Ingest scores from a Mutopia repository into the corpus.

    Discovers all ``.ly`` files, extracts Mutopia headers, and runs
    each through the shared ingestion pipeline.

    Args:
        repo_path: Root of the Mutopia repository clone.
        compiler: LilyPondCompiler for validation.
        store: CorpusStore for indexing.
        router: Optional InferenceRouter for compile-fix loop.
        max_scores: Maximum number of scores to ingest (for testing/debugging).

    Returns:
        List of IngestionResult, one per score file.
    """
    scores = discover_mutopia_scores(repo_path)
    if max_scores is not None:
        scores = scores[:max_scores]

    logger.info("Discovered %d Mutopia scores to ingest", len(scores))
    results: list[IngestionResult] = []

    for i, score_path in enumerate(scores):
        if (i + 1) % 100 == 0:
            logger.info("Mutopia ingestion progress: %d/%d", i + 1, len(scores))

        try:
            ly_source = score_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            results.append(
                IngestionResult(
                    source_path=score_path,
                    skipped=True,
                    skip_reason=f"Could not read file: {e}",
                    errors=[str(e)],
                )
            )
            continue

        header = extract_mutopia_header(ly_source)
        header_metadata = map_mutopia_to_metadata(header)

        ingestion_result = await ingest_score(
            ly_source=ly_source,
            source_path=score_path,
            source_collection="mutopia",
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
        "Mutopia ingestion complete: %d ingested, %d skipped, %d total chunks",
        ingested,
        skipped,
        total_chunks,
    )

    return results
