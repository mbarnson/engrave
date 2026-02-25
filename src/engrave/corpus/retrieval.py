"""Hybrid retrieval interface for corpus LilyPond phrase examples.

Provides the ``retrieve()`` convenience function that Phase 3's generation
pipeline calls to get few-shot examples.  The heavy lifting (embedding
similarity + metadata filtering) is delegated to :class:`CorpusStore.query`.

Usage::

    from engrave.corpus import retrieve

    results = retrieve(
        query_text="big band trumpet section, swing style",
        instrument_family="brass",
        style="Jazz",
        n_results=5,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engrave.corpus.models import RetrievalQuery, RetrievalResult

if TYPE_CHECKING:
    from engrave.config.settings import CorpusConfig
    from engrave.corpus.store import CorpusStore


def retrieve(
    query_text: str,
    instrument_family: str | None = None,
    ensemble_type: str | None = None,
    style: str | None = None,
    n_results: int = 5,
    store: CorpusStore | None = None,
    config: CorpusConfig | None = None,
) -> list[RetrievalResult]:
    """Retrieve relevant LilyPond phrase examples from the corpus.

    This is a thin convenience wrapper around :meth:`CorpusStore.query` that
    makes the common case easy while allowing callers to pass a pre-configured
    store directly (e.g. for batch operations or testing).

    Parameters
    ----------
    query_text:
        Natural language description of the desired musical content.
        Used for embedding similarity search.
    instrument_family:
        Optional filter: only return chunks matching this instrument family
        (e.g. "brass", "keyboard", "strings", "woodwind").
    ensemble_type:
        Optional filter: only return chunks matching this ensemble type
        (e.g. "solo", "big_band", "chamber").
    style:
        Optional filter: only return chunks matching this style
        (e.g. "Jazz", "Baroque", "Classical", "Romantic").
    n_results:
        Maximum number of results to return.  Defaults to 5.
    store:
        Pre-configured :class:`CorpusStore` instance.  When *None*, a new
        store is created from *config* (or the default ``CorpusConfig``).
    config:
        Corpus configuration for creating a new store.  Ignored when
        *store* is provided.

    Returns
    -------
    list[RetrievalResult]
        Results ranked by embedding similarity (lowest distance first),
        each containing the matched :class:`Chunk` and its cosine distance.
        Returns an empty list when no chunks match the filters.
    """
    if store is None:
        from engrave.config.settings import CorpusConfig as _CorpusConfig
        from engrave.corpus.store import CorpusStore as _CorpusStore

        _config = config or _CorpusConfig()
        store = _CorpusStore(config=_config)

    query = RetrievalQuery(
        query_text=query_text,
        instrument_family=instrument_family,
        ensemble_type=ensemble_type,
        style=style,
        n_results=n_results,
    )

    return store.query(query)
