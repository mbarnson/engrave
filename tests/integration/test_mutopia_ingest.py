"""Integration tests for Mutopia ingestion pipeline.

Uses the mutopia_bach.ly fixture and mocked LilyPondCompiler to verify the
full ingestion path: MIDI injection -> compilation -> chunking -> metadata
extraction -> ChromaDB indexing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import chromadb
import pytest

from engrave.config.settings import CorpusConfig
from engrave.corpus.ingest.mutopia import extract_mutopia_header, map_mutopia_to_metadata
from engrave.corpus.ingest.pipeline import ingest_mutopia_corpus, ingest_score
from engrave.corpus.store import CorpusStore
from engrave.lilypond.compiler import RawCompileResult


@pytest.fixture
def _ingest_store(request, tmp_path: Path):
    """CorpusStore backed by an in-memory ChromaDB client with unique collection."""
    config = CorpusConfig(
        embedding_model="all-MiniLM-L6-v2",
        db_path=str(tmp_path / "test_corpus_db"),
        collection_name=f"test_ingest_{request.node.name}",
    )
    client = chromadb.Client()
    return CorpusStore(config=config, client=client)


@pytest.fixture
def _ingest_compiler(tmp_path: Path):
    """Mock compiler that writes fake MIDI and PDF files."""
    pdf_path = tmp_path / "out.pdf"
    midi_path = tmp_path / "out.midi"

    def fake_compile(source: str, output_dir: Path | None = None):
        pdf_path.write_text("fake pdf")
        midi_path.write_bytes(b"")
        return RawCompileResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            output_path=pdf_path,
        )

    compiler = MagicMock()
    compiler.compile.side_effect = fake_compile
    return compiler


class TestIngestScore:
    """Integration tests for ingest_score()."""

    @pytest.fixture(autouse=True)
    def _setup(self, _ingest_store, _ingest_compiler, sample_mutopia_score):
        self.store = _ingest_store
        self.compiler = _ingest_compiler
        self.ly_source = sample_mutopia_score

    async def test_produces_chunks_in_store(self):
        """ingest_score produces chunks that are indexed in ChromaDB."""
        header = extract_mutopia_header(self.ly_source)
        header_meta = map_mutopia_to_metadata(header)

        result = await ingest_score(
            ly_source=self.ly_source,
            source_path=Path("test/mutopia_bach.ly"),
            source_collection="mutopia",
            header_metadata=header_meta,
            compiler=self.compiler,
            store=self.store,
        )

        assert not result.skipped
        assert result.chunks_indexed > 0
        assert self.store.count() > 0

    async def test_chunks_have_correct_source_collection(self):
        """Chunks have source_collection='mutopia' in their metadata."""
        header = extract_mutopia_header(self.ly_source)
        header_meta = map_mutopia_to_metadata(header)

        await ingest_score(
            ly_source=self.ly_source,
            source_path=Path("test/mutopia_bach.ly"),
            source_collection="mutopia",
            header_metadata=header_meta,
            compiler=self.compiler,
            store=self.store,
        )

        # Query the store and verify source_collection
        from engrave.corpus.models import RetrievalQuery

        results = self.store.query(RetrievalQuery(query_text="Bach Invention", n_results=10))
        assert len(results) > 0
        for r in results:
            assert r.chunk.metadata.source_collection == "mutopia"

    async def test_chunks_have_descriptions(self):
        """Chunks have non-empty structured descriptions."""
        header = extract_mutopia_header(self.ly_source)
        header_meta = map_mutopia_to_metadata(header)

        await ingest_score(
            ly_source=self.ly_source,
            source_path=Path("test/mutopia_bach.ly"),
            source_collection="mutopia",
            header_metadata=header_meta,
            compiler=self.compiler,
            store=self.store,
        )

        from engrave.corpus.models import RetrievalQuery

        results = self.store.query(RetrievalQuery(query_text="Bach Invention", n_results=10))
        for r in results:
            assert r.chunk.description, "Chunk description should not be empty"

    async def test_midi_block_injected(self):
        """The source passed to the compiler contains \\midi after injection."""
        header = extract_mutopia_header(self.ly_source)
        header_meta = map_mutopia_to_metadata(header)

        # The fixture score does NOT have \midi, so injection should add it
        assert r"\midi" not in self.ly_source

        await ingest_score(
            ly_source=self.ly_source,
            source_path=Path("test/mutopia_bach.ly"),
            source_collection="mutopia",
            header_metadata=header_meta,
            compiler=self.compiler,
            store=self.store,
        )

        # Check the source that was passed to the compiler
        compiled_source = self.compiler.compile.call_args[0][0]
        assert r"\midi" in compiled_source


class TestIngestMutopiaCo:
    """Integration tests for ingest_mutopia_corpus()."""

    async def test_single_fixture_file(self, tmp_path: Path, _ingest_store, _ingest_compiler):
        """Ingesting a directory with one fixture file produces one IngestionResult."""
        # Copy fixture to tmp_path structure
        fixture_path = Path(__file__).parent.parent / "fixtures" / "corpus" / "mutopia_bach.ly"
        dest = tmp_path / "scores" / "mutopia_bach.ly"
        dest.parent.mkdir(parents=True)
        dest.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

        results = await ingest_mutopia_corpus(
            repo_path=tmp_path / "scores",
            compiler=_ingest_compiler,
            store=_ingest_store,
            max_scores=1,
        )

        assert len(results) == 1
        assert not results[0].skipped
        assert results[0].chunks_indexed > 0
