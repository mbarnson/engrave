"""Corpus storage and retrieval for LilyPond phrase examples.

Public API::

    from engrave.corpus import retrieve
    from engrave.corpus import ingest_score, ingest_mutopia_corpus, ingest_pdmx_corpus
"""

from engrave.corpus.ingest import (
    ingest_mutopia_corpus,
    ingest_pdmx_corpus,
    ingest_score,
)
from engrave.corpus.retrieval import retrieve

__all__ = [
    "ingest_mutopia_corpus",
    "ingest_pdmx_corpus",
    "ingest_score",
    "retrieve",
]
