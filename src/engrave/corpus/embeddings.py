"""Configurable embedding function wrapper for ChromaDB.

The factory approach makes it trivial to swap embedding models for A/B
testing: change ``corpus.embedding_model`` in ``engrave.toml``, restart.
"""

from __future__ import annotations

from chromadb.api.types import EmbeddingFunction
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


def get_embedding_function(model_name: str) -> EmbeddingFunction:
    """Return a ChromaDB-compatible embedding function for *model_name*.

    Uses ``SentenceTransformerEmbeddingFunction`` under the hood, which
    delegates to the ``sentence-transformers`` library.  The default model
    (configured in ``engrave.toml``) is ``nomic-embed-text``.
    """
    return SentenceTransformerEmbeddingFunction(model_name=model_name)
