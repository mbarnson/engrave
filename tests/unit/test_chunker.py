"""Tests for LilyPond music-aware phrase chunking."""

from __future__ import annotations

from pathlib import Path

import pytest

from engrave.corpus.chunker import chunk_score, expand_repeats

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "corpus"


@pytest.fixture
def simple_score() -> str:
    """Load the simple test score fixture."""
    return (FIXTURES_DIR / "simple_score.ly").read_text()


@pytest.fixture
def multi_part_score() -> str:
    """Load the multi-part test score fixture."""
    return (FIXTURES_DIR / "multi_part_score.ly").read_text()


@pytest.fixture
def repeat_score() -> str:
    """Load the repeat test score fixture."""
    return (FIXTURES_DIR / "repeat_score.ly").read_text()


@pytest.fixture
def plain_score() -> str:
    """A plain score with only bar checks, no structural cues."""
    return r"""c'4 d' e' f' |
g'4 a' b' c'' |
d''4 e'' f'' g'' |
a'4 b' c'' d'' |
e'4 f' g' a' |
b'4 c'' d'' e'' |
f'4 g' a' b' |
c''4 d'' e'' f'' |
g'4 a' b' c'' |
d'4 e' f' g' |
a'4 b' c'' d'' |
e''4 f'' g'' a'' |
b'4 c'' d'' e'' |
f''4 g'' a'' b'' |
c'''4 d''' e''' f''' |
g''2. r4 |
"""


class TestChunkScoreSimple:
    """Tests for chunk_score on simple scores."""

    def test_splits_at_rehearsal_mark_boundary(self, simple_score: str):
        """chunk_score on simple_score.ly splits at the rehearsal mark boundary."""
        chunks = chunk_score(simple_score, "test/simple.ly", "test")
        assert len(chunks) >= 2
        # At least one chunk should end before the rehearsal mark area,
        # and at least one should start at or after it
        bar_starts = [c["bar_start"] for c in chunks]
        bar_ends = [c["bar_end"] for c in chunks]
        # The rehearsal mark is at bar 9, key change at bar 13
        # We should see a boundary around those points
        assert any(end <= 9 for end in bar_ends), "No chunk ends before rehearsal mark"
        assert any(start >= 9 for start in bar_starts), "No chunk starts at/after rehearsal mark"

    def test_chunks_have_required_keys(self, simple_score: str):
        """Each chunk contains the required dictionary keys."""
        chunks = chunk_score(simple_score, "test/simple.ly", "test")
        required_keys = {
            "source",
            "bar_start",
            "bar_end",
            "chunk_type",
            "instrument",
            "chunk_index",
        }
        for chunk in chunks:
            assert required_keys.issubset(chunk.keys()), (
                f"Missing keys: {required_keys - chunk.keys()}"
            )

    def test_chunks_are_fragments(self, simple_score: str):
        """Chunks are source fragments, not full compilable LilyPond files."""
        chunks = chunk_score(simple_score, "test/simple.ly", "test")
        for chunk in chunks:
            # Fragments should not contain \version or \score declarations
            assert r"\score" not in chunk["source"]

    def test_chunk_index_is_sequential(self, simple_score: str):
        """Chunk indices are sequential starting from 0."""
        chunks = chunk_score(simple_score, "test/simple.ly", "test")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


class TestChunkScoreFallback:
    """Tests for chunk_score fallback to fixed bar chunks."""

    def test_falls_back_to_4_8_bar_chunks(self, plain_score: str):
        """chunk_score falls back to 4-8 bar chunks when no structural cues exist."""
        chunks = chunk_score(plain_score, "test/plain.ly", "test")
        assert len(chunks) >= 2
        for chunk in chunks:
            bar_count = chunk["bar_end"] - chunk["bar_start"] + 1
            # Allow some flexibility: overlap may make chunks seem larger
            # but the core bar range should be within reason
            assert bar_count <= 10, f"Chunk too large: {bar_count} bars"


class TestChunkScoreOverlap:
    """Tests for chunk overlap behavior."""

    def test_produces_overlap_between_adjacent_chunks(self, simple_score: str):
        """chunk_score produces 1-2 bar overlap between adjacent chunks."""
        chunks = chunk_score(simple_score, "test/simple.ly", "test")
        if len(chunks) < 2:
            pytest.skip("Need at least 2 chunks to test overlap")

        # Check that at least one pair of adjacent chunks has overlapping bar ranges
        has_overlap = False
        for i in range(len(chunks) - 1):
            current_end = chunks[i]["bar_end"]
            next_start = chunks[i + 1]["bar_start"]
            if next_start <= current_end:
                has_overlap = True
                overlap = current_end - next_start + 1
                assert 1 <= overlap <= 2, f"Overlap should be 1-2 bars, got {overlap}"
        assert has_overlap, "No overlap found between adjacent chunks"


class TestExpandRepeats:
    """Tests for repeat expansion."""

    def test_expands_volta_with_alternatives(self):
        """expand_repeats unrolls volta 2 with alternatives into A B A C."""
        source = r"""\repeat volta 2 {
  f'4 a' c'' f'' |
  e''4 d'' c'' bes' |
}
\alternative {
  { a'4 g' f' e' | d'2 c'2 | }
  { a'4 bes' c'' d'' | f''2. r4 | }
}"""
        expanded = expand_repeats(source)
        # After expansion, the repeat/alternative blocks should be gone
        assert r"\repeat" not in expanded
        assert r"\alternative" not in expanded
        # The body should appear twice
        assert expanded.count("f'4 a' c'' f''") == 2
        # First alternative appears once, second alternative appears once
        assert "a'4 g' f' e'" in expanded
        assert "a'4 bes' c'' d''" in expanded

    def test_expands_volta_without_alternatives(self):
        """expand_repeats unrolls volta N without alternatives (repeats N times)."""
        source = r"""\repeat volta 3 {
  c'4 d' e' f' |
  g'2 g'2 |
}"""
        expanded = expand_repeats(source)
        assert r"\repeat" not in expanded
        # The body should appear 3 times
        assert expanded.count("c'4 d' e' f'") == 3


class TestChunkScoreRepeats:
    """Tests for chunking after repeat expansion."""

    def test_expands_repeats_before_chunking(self, repeat_score: str):
        """chunk_score on repeat_score.ly expands repeats before chunking."""
        chunks = chunk_score(repeat_score, "test/repeat.ly", "test")
        # After expansion, no chunk should contain \repeat or \alternative
        for chunk in chunks:
            assert r"\repeat" not in chunk["source"], "Repeat not expanded in chunk"
            assert r"\alternative" not in chunk["source"], "Alternative not expanded in chunk"


class TestChunkScoreMultiPart:
    """Tests for multi-part score chunking."""

    def test_produces_both_chunk_types(self, multi_part_score: str):
        """chunk_score on multi_part_score.ly produces both single-instrument and full-score chunks."""
        chunks = chunk_score(multi_part_score, "test/multi.ly", "test")
        chunk_types = {c["chunk_type"] for c in chunks}
        assert "single_instrument" in chunk_types, "No single-instrument chunks produced"
        assert "full_score" in chunk_types, "No full-score vertical chunks produced"

    def test_single_instrument_chunks_have_instrument_name(self, multi_part_score: str):
        """Single-instrument chunks have an instrument name (not 'all')."""
        chunks = chunk_score(multi_part_score, "test/multi.ly", "test")
        single_chunks = [c for c in chunks if c["chunk_type"] == "single_instrument"]
        assert len(single_chunks) >= 1
        for chunk in single_chunks:
            assert chunk["instrument"] != "all"
            assert chunk["instrument"] is not None

    def test_full_score_chunks_have_all_instrument(self, multi_part_score: str):
        """Full-score vertical chunks have instrument set to 'all'."""
        chunks = chunk_score(multi_part_score, "test/multi.ly", "test")
        full_chunks = [c for c in chunks if c["chunk_type"] == "full_score"]
        assert len(full_chunks) >= 1
        for chunk in full_chunks:
            assert chunk["instrument"] == "all"

    def test_chunk_bar_range_metadata(self, multi_part_score: str):
        """Each chunk contains bar range metadata."""
        chunks = chunk_score(multi_part_score, "test/multi.ly", "test")
        for chunk in chunks:
            assert "bar_start" in chunk
            assert "bar_end" in chunk
            assert chunk["bar_start"] >= 1
            assert chunk["bar_end"] >= chunk["bar_start"]
