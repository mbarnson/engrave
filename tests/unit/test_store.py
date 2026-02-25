"""Unit tests for ChromaDB corpus store and data models."""

from __future__ import annotations

import chromadb
import pytest

from engrave.corpus.embeddings import get_embedding_function
from engrave.corpus.models import Chunk, RetrievalQuery, RetrievalResult, ScoreMetadata
from engrave.corpus.store import CorpusStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_metadata(**overrides: object) -> ScoreMetadata:
    """Build a ScoreMetadata with sensible defaults, overrideable for filtering tests."""
    defaults = {
        "source_collection": "mutopia",
        "source_path": "ftp/BachJS/BWV846/bwv846.ly",
        "chunk_index": 0,
        "bar_start": 1,
        "bar_end": 8,
        "chunk_type": "single_instrument",
        "key_signature": "C major",
        "time_signature": "4/4",
        "tempo": "Allegro",
        "instrument": "Piano",
        "instrument_family": "keyboard",
        "clef": "treble",
        "ensemble_type": "solo",
        "style": "Baroque",
        "composer": "BachJS",
        "note_density": 12.5,
        "dynamic_range": "mf-f",
        "articulation_count": 3,
        "has_chord_symbols": False,
        "has_midi": True,
        "rich_description": "",
    }
    defaults.update(overrides)
    return ScoreMetadata(**defaults)


def _sample_chunk(
    id: str = "chunk_001",
    source: str = "\\relative c' { c4 d e f | g2 g | }",
    description: str = "Key: C major. Time: 4/4. Instrument: Piano. Bars 1-8.",
    **meta_overrides: object,
) -> Chunk:
    return Chunk(
        id=id,
        source=source,
        description=description,
        metadata=_sample_metadata(**meta_overrides),
    )


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestScoreMetadata:
    def test_creates_with_all_fields(self) -> None:
        meta = _sample_metadata()
        assert meta.source_collection == "mutopia"
        assert meta.instrument_family == "keyboard"
        assert meta.rich_description == ""

    def test_rich_description_defaults_empty(self) -> None:
        """Music Flamingo enrichment placeholder defaults to empty string."""
        meta = _sample_metadata()
        assert meta.rich_description == ""

    def test_optional_note_density(self) -> None:
        meta = _sample_metadata(note_density=None)
        assert meta.note_density is None

    def test_chunk_type_literal(self) -> None:
        meta = _sample_metadata(chunk_type="full_score")
        assert meta.chunk_type == "full_score"


class TestChunk:
    def test_creates_with_metadata(self) -> None:
        chunk = _sample_chunk()
        assert chunk.id == "chunk_001"
        assert chunk.source.startswith("\\relative")
        assert chunk.metadata.key_signature == "C major"

    def test_optional_midi_features(self) -> None:
        chunk = _sample_chunk()
        assert chunk.midi_features is None

    def test_with_midi_features(self) -> None:
        features = {"velocity_hist": [0.1, 0.5, 0.4], "pitch_range": (48, 84)}
        chunk = Chunk(
            id="midi_chunk",
            source="{ c4 }",
            description="test",
            metadata=_sample_metadata(),
            midi_features=features,
        )
        assert chunk.midi_features == features


class TestRetrievalQuery:
    def test_defaults(self) -> None:
        q = RetrievalQuery(query_text="brass section forte")
        assert q.n_results == 5
        assert q.instrument_family is None
        assert q.ensemble_type is None
        assert q.style is None

    def test_with_filters(self) -> None:
        q = RetrievalQuery(
            query_text="swing trumpet",
            instrument_family="brass",
            ensemble_type="big_band",
            style="Jazz",
            n_results=10,
        )
        assert q.instrument_family == "brass"
        assert q.n_results == 10


class TestRetrievalResult:
    def test_structure(self) -> None:
        chunk = _sample_chunk()
        result = RetrievalResult(chunk=chunk, distance=0.123)
        assert result.distance == 0.123
        assert result.chunk.id == "chunk_001"


# ---------------------------------------------------------------------------
# Embedding function tests
# ---------------------------------------------------------------------------


class TestEmbeddingFunction:
    def test_get_embedding_function_returns_callable(self) -> None:
        """get_embedding_function should return a ChromaDB-compatible embedding function."""
        ef = get_embedding_function("all-MiniLM-L6-v2")
        assert callable(ef)

    def test_default_model_config(self) -> None:
        """Default embedding model in CorpusConfig is nomic-embed-text per user decision."""
        from engrave.config.settings import CorpusConfig

        config = CorpusConfig()
        assert config.embedding_model == "nomic-embed-text"


# ---------------------------------------------------------------------------
# CorpusStore tests
# ---------------------------------------------------------------------------


class TestCorpusStore:
    @pytest.fixture()
    def store(self, tmp_path, request) -> CorpusStore:
        """Create a CorpusStore backed by an in-memory ChromaDB client for test speed.

        Each test gets a unique collection name to avoid cross-test contamination
        (chromadb.Client() is a process-wide singleton in-memory store).
        """
        from engrave.config.settings import CorpusConfig

        # Use the test node id to guarantee a unique collection per test
        unique_name = request.node.name.replace("[", "_").replace("]", "_")[:50]
        config = CorpusConfig(
            embedding_model="all-MiniLM-L6-v2",
            db_path=str(tmp_path / "test_db"),
            collection_name=f"test_{unique_name}",
        )
        client = chromadb.Client()
        return CorpusStore(config=config, client=client)

    def test_initializes_with_collection(self, store: CorpusStore) -> None:
        """Store should create a named collection on init."""
        assert store.count() == 0

    def test_add_chunks_stores_documents(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(id="c1", description="Key: C major. Piano solo."),
            _sample_chunk(
                id="c2",
                description="Key: G major. Violin duet.",
                key_signature="G major",
                instrument="Violin",
                instrument_family="strings",
            ),
        ]
        added = store.add_chunks(chunks)
        assert added == 2
        assert store.count() == 2

    def test_add_chunks_includes_rich_description_placeholder(self, store: CorpusStore) -> None:
        """ChromaDB schema includes empty rich_description for Music Flamingo enrichment."""
        chunk = _sample_chunk(id="rich_test")
        store.add_chunks([chunk])
        # Retrieve raw from collection to verify metadata field
        result = store._collection.get(ids=["rich_test"], include=["metadatas"])
        assert result["metadatas"][0]["rich_description"] == ""

    def test_add_chunks_stores_ly_source_in_metadata(self, store: CorpusStore) -> None:
        chunk = _sample_chunk(id="src_test", source="{ c4 d e f }")
        store.add_chunks([chunk])
        result = store._collection.get(ids=["src_test"], include=["metadatas"])
        assert result["metadatas"][0]["ly_source"] == "{ c4 d e f }"

    def test_query_returns_retrieval_results(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(id="q1", description="Key: C major. Fast piano passage."),
            _sample_chunk(
                id="q2", description="Key: A minor. Slow violin melody.", key_signature="A minor"
            ),
        ]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="piano passage in C major")
        results = store.query(query)
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert all(isinstance(r.distance, float) for r in results)
        assert all(r.chunk.id in ("q1", "q2") for r in results)

    def test_query_with_metadata_filter_instrument_family(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(
                id="brass1",
                description="Trumpet fanfare.",
                instrument_family="brass",
                instrument="Trumpet",
            ),
            _sample_chunk(
                id="str1",
                description="Violin melody.",
                instrument_family="strings",
                instrument="Violin",
            ),
            _sample_chunk(
                id="brass2",
                description="Trombone bass line.",
                instrument_family="brass",
                instrument="Trombone",
            ),
        ]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="fanfare", instrument_family="brass", n_results=5)
        results = store.query(query)
        assert all(r.chunk.metadata.instrument_family == "brass" for r in results)

    def test_query_with_metadata_filter_ensemble_type(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(id="solo1", description="Solo piano.", ensemble_type="solo"),
            _sample_chunk(id="orch1", description="Orchestra tutti.", ensemble_type="orchestra"),
        ]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="tutti", ensemble_type="orchestra")
        results = store.query(query)
        assert all(r.chunk.metadata.ensemble_type == "orchestra" for r in results)

    def test_query_with_metadata_filter_style(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(id="jazz1", description="Swing trumpet.", style="Jazz"),
            _sample_chunk(id="class1", description="Baroque harpsichord.", style="Baroque"),
        ]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="swing", style="Jazz")
        results = store.query(query)
        assert all(r.chunk.metadata.style == "Jazz" for r in results)

    def test_query_with_combined_metadata_filters(self, store: CorpusStore) -> None:
        chunks = [
            _sample_chunk(
                id="jb1", description="Jazz brass.", style="Jazz", instrument_family="brass"
            ),
            _sample_chunk(
                id="cb1",
                description="Classical brass.",
                style="Classical",
                instrument_family="brass",
            ),
            _sample_chunk(
                id="js1", description="Jazz strings.", style="Jazz", instrument_family="strings"
            ),
        ]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="brass jazz", instrument_family="brass", style="Jazz")
        results = store.query(query)
        assert len(results) == 1
        assert results[0].chunk.id == "jb1"

    def test_query_respects_n_results(self, store: CorpusStore) -> None:
        chunks = [_sample_chunk(id=f"n{i}", description=f"Chunk {i}") for i in range(10)]
        store.add_chunks(chunks)
        query = RetrievalQuery(query_text="chunk", n_results=3)
        results = store.query(query)
        assert len(results) <= 3

    def test_collection_uses_cosine_distance(self, store: CorpusStore) -> None:
        """Collection must use cosine distance metric."""
        coll_meta = store._collection.metadata
        assert coll_meta.get("hnsw:space") == "cosine"
