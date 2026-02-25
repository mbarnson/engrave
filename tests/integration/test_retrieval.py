"""Integration tests for corpus retrieval interface.

Tests hybrid retrieval (metadata filter + embedding similarity) using a
pre-populated in-memory ChromaDB store with diverse test chunks spanning
different instrument families, ensemble types, and styles.
"""

from __future__ import annotations

import pytest

from engrave.corpus.models import RetrievalResult
from engrave.corpus.retrieval import retrieve


class TestRetrieve:
    """Integration tests for the retrieve() public API."""

    @pytest.fixture(autouse=True)
    def _setup(self, populated_corpus_store):
        self.store = populated_corpus_store

    def test_no_filters_returns_n_results_ranked_by_similarity(self):
        """retrieve() with no filters returns n_results chunks ranked by embedding similarity."""
        results = retrieve(
            query_text="brass section swing",
            n_results=5,
            store=self.store,
        )
        assert len(results) == 5
        # Results should be sorted by distance (ascending = most similar first)
        distances = [r.distance for r in results]
        assert distances == sorted(distances)

    def test_instrument_family_brass_filter(self):
        """retrieve() with instrument_family='brass' returns only brass chunks."""
        results = retrieve(
            query_text="trumpet section",
            instrument_family="brass",
            store=self.store,
        )
        assert len(results) > 0
        for r in results:
            assert r.chunk.metadata.instrument_family == "brass"

    def test_ensemble_type_big_band_filter(self):
        """retrieve() with ensemble_type='big_band' returns only big band chunks."""
        results = retrieve(
            query_text="jazz ensemble",
            ensemble_type="big_band",
            store=self.store,
        )
        assert len(results) > 0
        for r in results:
            assert r.chunk.metadata.ensemble_type == "big_band"

    def test_style_jazz_filter(self):
        """retrieve() with style='Jazz' returns only jazz-style chunks."""
        results = retrieve(
            query_text="swing feel",
            style="Jazz",
            store=self.store,
        )
        assert len(results) > 0
        for r in results:
            assert r.chunk.metadata.style == "Jazz"

    def test_multiple_filters_intersection(self):
        """retrieve() with multiple filters returns their intersection."""
        results = retrieve(
            query_text="brass jazz swing",
            instrument_family="brass",
            style="Jazz",
            store=self.store,
        )
        assert len(results) > 0
        for r in results:
            assert r.chunk.metadata.instrument_family == "brass"
            assert r.chunk.metadata.style == "Jazz"

    def test_n_results_parameter(self):
        """retrieve() with n_results=3 returns exactly 3 results."""
        results = retrieve(
            query_text="music score",
            n_results=3,
            store=self.store,
        )
        assert len(results) == 3

    def test_returns_retrieval_result_objects(self):
        """retrieve() returns RetrievalResult objects with chunk and distance fields."""
        results = retrieve(
            query_text="piano sonata",
            n_results=2,
            store=self.store,
        )
        assert len(results) > 0
        for r in results:
            assert isinstance(r, RetrievalResult)
            assert r.chunk is not None
            assert r.chunk.source  # LilyPond source is non-empty
            assert r.chunk.description  # Description is non-empty
            assert isinstance(r.distance, float)

    def test_embedding_similarity_brass_jazz_preference(self):
        """retrieve() with query 'big band trumpet section, swing style' returns brass/jazz preferentially."""
        results = retrieve(
            query_text="big band trumpet section, swing style",
            n_results=3,
            store=self.store,
        )
        # At least the top result should be brass or jazz related
        top_families = [r.chunk.metadata.instrument_family for r in results]
        top_styles = [r.chunk.metadata.style for r in results]
        # The embedding should prefer brass and/or jazz chunks
        assert "brass" in top_families or "Jazz" in top_styles

    def test_no_matching_filters_returns_empty_list(self):
        """retrieve() with no matching filters returns empty list, not an error."""
        results = retrieve(
            query_text="something",
            instrument_family="nonexistent_family",
            store=self.store,
        )
        assert results == []
