"""Integration tests for PDMX ingestion pipeline.

Uses the simple_score.musicxml fixture and mocked musicxml2ly subprocess
to verify the full PDMX ingestion path: discovery -> conversion ->
compilation -> chunking -> ChromaDB indexing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from engrave.config.settings import CorpusConfig
from engrave.corpus.ingest.pdmx import (
    convert_musicxml_to_ly,
    discover_pdmx_scores,
    ingest_pdmx_corpus,
    store_original_mxl,
)
from engrave.corpus.store import CorpusStore
from engrave.lilypond.compiler import RawCompileResult

# A minimal converted LilyPond source that musicxml2ly would produce
_CONVERTED_LY = r"""
\version "2.24.4"

\header {
  title = "Simple Test Score"
  composer = "Test Composer"
}

\score {
  \new Staff {
    \clef treble
    \key c \major
    \time 4/4
    c'4 d' e' f' |
    g'2 a'2 |
    b'4 c'' d'' e'' |
    c''1 |
  }
  \layout { }
}
"""


@pytest.fixture
def _pdmx_store(request, tmp_path: Path):
    """CorpusStore backed by an in-memory ChromaDB client with unique collection."""
    config = CorpusConfig(
        embedding_model="all-MiniLM-L6-v2",
        db_path=str(tmp_path / "test_corpus_db"),
        collection_name=f"test_pdmx_{request.node.name}",
    )
    client = chromadb.Client()
    return CorpusStore(config=config, client=client)


@pytest.fixture
def _pdmx_compiler(tmp_path: Path):
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


@pytest.fixture
def _pdmx_data_dir(tmp_path: Path) -> Path:
    """Create a fake PDMX data directory with one MusicXML file."""
    data_dir = tmp_path / "pdmx_data"
    data_dir.mkdir()
    fixture_path = Path(__file__).parent.parent / "fixtures" / "musicxml" / "simple_score.musicxml"
    dest = data_dir / "simple_score.musicxml"
    dest.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")
    return data_dir


class TestDiscoverPdmxScores:
    """Tests for discover_pdmx_scores()."""

    def test_discovers_musicxml_files(self, _pdmx_data_dir: Path):
        """Discovers .musicxml files in the data directory."""
        scores = discover_pdmx_scores(_pdmx_data_dir, rated_only=False)
        assert len(scores) == 1
        assert scores[0].suffix == ".musicxml"

    def test_nonexistent_path_returns_empty(self, tmp_path: Path):
        """Non-existent data path returns empty list."""
        scores = discover_pdmx_scores(tmp_path / "nonexistent", rated_only=False)
        assert scores == []


class TestConvertMusicxmlToLy:
    """Tests for convert_musicxml_to_ly()."""

    def test_calls_subprocess_correctly(self, tmp_path: Path, _pdmx_data_dir: Path):
        """convert_musicxml_to_ly calls musicxml2ly with correct arguments."""
        mxl_path = _pdmx_data_dir / "simple_score.musicxml"
        output_dir = tmp_path / "converted"

        with patch("engrave.corpus.ingest.pdmx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            # Create the expected output file to simulate musicxml2ly writing it
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "simple_score.ly").write_text(_CONVERTED_LY)

            ly_path, error = convert_musicxml_to_ly(mxl_path, output_dir)

            assert error is None
            assert ly_path is not None
            assert ly_path.suffix == ".ly"
            # Verify subprocess was called with musicxml2ly
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "musicxml2ly"
            assert "--output" in call_args

    def test_handles_conversion_failure(self, tmp_path: Path, _pdmx_data_dir: Path):
        """Conversion failure returns (None, error_message)."""
        mxl_path = _pdmx_data_dir / "simple_score.musicxml"
        output_dir = tmp_path / "converted"

        with patch("engrave.corpus.ingest.pdmx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Conversion error",
            )

            ly_path, error = convert_musicxml_to_ly(mxl_path, output_dir)

            assert ly_path is None
            assert error is not None
            assert "failed" in error.lower()


class TestStoreOriginalMxl:
    """Tests for store_original_mxl()."""

    def test_copies_original_file(self, tmp_path: Path, _pdmx_data_dir: Path):
        """Original MusicXML is copied to storage directory."""
        mxl_path = _pdmx_data_dir / "simple_score.musicxml"
        storage_dir = tmp_path / "originals"

        stored = store_original_mxl(mxl_path, storage_dir)

        assert stored.exists()
        assert stored.name == "simple_score.musicxml"
        assert stored.read_text() == mxl_path.read_text()


class TestIngestPdmxCorpus:
    """Integration tests for ingest_pdmx_corpus()."""

    async def test_produces_indexed_chunks(
        self, tmp_path: Path, _pdmx_store, _pdmx_compiler, _pdmx_data_dir
    ):
        """Ingesting PDMX data produces indexed chunks with source_collection='pdmx'."""

        # Mock musicxml2ly to write a converted file
        def fake_run(cmd, **kwargs):
            # Write converted LilyPond file
            output_idx = cmd.index("--output")
            output_file = Path(cmd[output_idx + 1])
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(_CONVERTED_LY)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("engrave.corpus.ingest.pdmx.subprocess.run", side_effect=fake_run):
            results = await ingest_pdmx_corpus(
                data_path=_pdmx_data_dir,
                compiler=_pdmx_compiler,
                store=_pdmx_store,
                rated_only=False,
                max_scores=1,
            )

        assert len(results) == 1
        assert not results[0].skipped
        assert results[0].chunks_indexed > 0
        assert _pdmx_store.count() > 0

        # Verify source_collection in stored chunks
        from engrave.corpus.models import RetrievalQuery

        query_results = _pdmx_store.query(RetrievalQuery(query_text="test score", n_results=10))
        for r in query_results:
            assert r.chunk.metadata.source_collection == "pdmx"

    async def test_original_stored_alongside(
        self, tmp_path: Path, _pdmx_store, _pdmx_compiler, _pdmx_data_dir
    ):
        """Original MusicXML file is stored alongside converted LilyPond."""

        def fake_run(cmd, **kwargs):
            output_idx = cmd.index("--output")
            output_file = Path(cmd[output_idx + 1])
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(_CONVERTED_LY)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("engrave.corpus.ingest.pdmx.subprocess.run", side_effect=fake_run):
            await ingest_pdmx_corpus(
                data_path=_pdmx_data_dir,
                compiler=_pdmx_compiler,
                store=_pdmx_store,
                rated_only=False,
                max_scores=1,
            )

        originals_dir = _pdmx_data_dir / "_originals"
        assert originals_dir.exists()
        stored_files = list(originals_dir.iterdir())
        assert len(stored_files) == 1
        assert stored_files[0].suffix == ".musicxml"
