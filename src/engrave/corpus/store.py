"""ChromaDB wrapper for corpus storage and retrieval.

Provides a ``CorpusStore`` class that wraps ChromaDB's PersistentClient
with a typed interface using the Pydantic models from ``models.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import chromadb

from engrave.corpus.embeddings import get_embedding_function
from engrave.corpus.models import Chunk, RetrievalQuery, RetrievalResult, ScoreMetadata

if TYPE_CHECKING:
    from engrave.config.settings import CorpusConfig


class CorpusStore:
    """ChromaDB-backed store for LilyPond phrase chunks.

    Parameters
    ----------
    config:
        Corpus configuration (embedding model, db path, collection name).
    client:
        Optional ChromaDB client for test injection.  When *None*, a
        ``PersistentClient`` is created using ``config.db_path``.
    """

    def __init__(self, config: CorpusConfig, client: chromadb.ClientAPI | None = None) -> None:
        self._config = config
        self._client = client or chromadb.PersistentClient(path=config.db_path)
        ef = get_embedding_function(config.embedding_model)
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """Add *chunks* to the collection and return the count added.

        Each chunk's ``description`` is stored as the ChromaDB document
        (used for embedding).  The LilyPond source is stored in the
        ``ly_source`` metadata field alongside the full ``ScoreMetadata``.
        """
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for chunk in chunks:
            ids.append(chunk.id)
            documents.append(chunk.description)
            meta = chunk.metadata.model_dump()
            meta["ly_source"] = chunk.source
            # ChromaDB metadata values must be str, int, float, or bool.
            # Remove None values to avoid TypeError from the Rust bindings.
            meta = {k: v for k, v in meta.items() if v is not None}
            metadatas.append(meta)

        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def query(self, query: RetrievalQuery) -> list[RetrievalResult]:
        """Query the collection with optional metadata filters.

        Builds a ChromaDB ``where`` clause from the optional filter
        fields on *query*, then queries by embedding similarity using
        the query text.
        """
        where = self._build_where(query)
        results = self._collection.query(
            query_texts=[query.query_text],
            n_results=query.n_results,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

        return self._format_results(results)

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self._collection.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where(query: RetrievalQuery) -> dict | None:
        """Build a ChromaDB ``where`` clause from query filter fields."""
        clauses: list[dict] = []
        if query.instrument_family is not None:
            clauses.append({"instrument_family": query.instrument_family})
        if query.ensemble_type is not None:
            clauses.append({"ensemble_type": query.ensemble_type})
        if query.style is not None:
            clauses.append({"style": query.style})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _format_results(raw: dict) -> list[RetrievalResult]:
        """Convert raw ChromaDB query results to ``RetrievalResult`` list."""
        out: list[RetrievalResult] = []
        if not raw["ids"] or not raw["ids"][0]:
            return out

        ids = raw["ids"][0]
        docs = raw["documents"][0]
        metas = raw["metadatas"][0]
        dists = raw["distances"][0]

        for doc_id, doc, meta, dist in zip(ids, docs, metas, dists, strict=True):
            ly_source = meta.pop("ly_source", "")
            score_meta = ScoreMetadata(**meta)
            chunk = Chunk(
                id=doc_id,
                source=ly_source,
                description=doc,
                metadata=score_meta,
            )
            out.append(RetrievalResult(chunk=chunk, distance=dist))

        return out
