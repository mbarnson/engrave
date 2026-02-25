"""Pydantic models for corpus data: chunks, metadata, queries, results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ScoreMetadata(BaseModel):
    """Structured metadata attached to every indexed chunk.

    The ``rich_description`` field is an empty placeholder for future Music
    Flamingo enrichment (per user decision -- NOT a v1 dependency).
    """

    source_collection: str
    source_path: str
    chunk_index: int
    bar_start: int
    bar_end: int
    chunk_type: Literal["single_instrument", "full_score"]
    key_signature: str
    time_signature: str
    tempo: str
    instrument: str
    instrument_family: str
    clef: str
    ensemble_type: str
    style: str
    composer: str
    note_density: float | None = None
    dynamic_range: str = ""
    articulation_count: int = 0
    has_chord_symbols: bool = False
    has_midi: bool = False
    rich_description: str = ""


class Chunk(BaseModel):
    """A phrase-level LilyPond fragment with its description and metadata."""

    id: str
    source: str  # The LilyPond fragment
    description: str  # Structured text description (for embedding)
    metadata: ScoreMetadata
    midi_features: dict | None = None  # velocity histogram, pitch range, etc.


class RetrievalQuery(BaseModel):
    """Parameters for a corpus retrieval request."""

    query_text: str
    instrument_family: str | None = None
    ensemble_type: str | None = None
    style: str | None = None
    n_results: int = 5


class RetrievalResult(BaseModel):
    """A single result from corpus retrieval: the chunk and its distance."""

    chunk: Chunk
    distance: float
