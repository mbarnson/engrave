"""Ingestion pipeline for corpus score sources (Mutopia, PDMX)."""

from engrave.corpus.ingest.midi_injection import ensure_midi_block
from engrave.corpus.ingest.mutopia import (
    discover_mutopia_scores,
    extract_mutopia_header,
    map_mutopia_to_metadata,
)
from engrave.corpus.ingest.pdmx import (
    convert_musicxml_to_ly,
    discover_pdmx_scores,
    ingest_pdmx_corpus,
)
from engrave.corpus.ingest.pipeline import ingest_mutopia_corpus, ingest_score

__all__ = [
    "convert_musicxml_to_ly",
    "discover_mutopia_scores",
    "discover_pdmx_scores",
    "ensure_midi_block",
    "extract_mutopia_header",
    "ingest_mutopia_corpus",
    "ingest_pdmx_corpus",
    "ingest_score",
    "map_mutopia_to_metadata",
]
