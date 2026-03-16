"""Unit tests for Mutopia header extraction and metadata mapping."""

from __future__ import annotations

from engrave.corpus.ingest.mutopia import (
    extract_mutopia_header,
    map_mutopia_to_metadata,
)

# Sample Mutopia header block for testing
_SAMPLE_HEADER = r"""
\version "2.24.0"

\header {
  mutopiatitle = "Invention No. 1 in C Major"
  mutopiacomposer = "BachJS"
  mutopiainstrument = "Piano"
  style = "Baroque"
  source = "Bach-Gesellschaft Ausgabe Band III"
  license = "Public Domain"
  date = "1723"
  mutopiaopus = "BWV 772"
  title = "Invention No. 1"
  composer = "J.S. Bach"
}

\score {
  \new Staff { c'4 d' e' f' | }
  \layout { }
}
"""


class TestExtractMutopiaHeader:
    """Tests for extract_mutopia_header()."""

    def test_extracts_all_standard_fields(self):
        """All Mutopia header fields are extracted from a complete header."""
        header = extract_mutopia_header(_SAMPLE_HEADER)
        assert header["mutopiatitle"] == "Invention No. 1 in C Major"
        assert header["mutopiacomposer"] == "BachJS"
        assert header["mutopiainstrument"] == "Piano"
        assert header["style"] == "Baroque"
        assert header["source"] == "Bach-Gesellschaft Ausgabe Band III"
        assert header["license"] == "Public Domain"
        assert header["date"] == "1723"
        assert header["mutopiaopus"] == "BWV 772"

    def test_handles_missing_fields_gracefully(self):
        """Missing fields are simply omitted from the result dict."""
        source = r"""
\header {
  mutopiatitle = "Simple Piece"
  mutopiacomposer = "Anonymous"
}
"""
        header = extract_mutopia_header(source)
        assert header["mutopiatitle"] == "Simple Piece"
        assert header["mutopiacomposer"] == "Anonymous"
        assert "mutopiainstrument" not in header
        assert "style" not in header
        assert "date" not in header

    def test_handles_multiline_header_values(self):
        """Multiline quoted values are collapsed into a single line."""
        source = r"""
\header {
  mutopiatitle = "Suite No. 1 in
    G Major"
  mutopiacomposer = "BachJS"
}
"""
        header = extract_mutopia_header(source)
        assert "Suite No. 1 in" in header["mutopiatitle"]
        assert "G Major" in header["mutopiatitle"]

    def test_empty_source_returns_empty_dict(self):
        """Source with no header block returns empty dict."""
        header = extract_mutopia_header("")
        assert header == {}

    def test_header_without_mutopia_fields(self):
        """Standard LilyPond header without Mutopia fields extracts what is available."""
        source = r"""
\header {
  title = "My Piece"
  composer = "Someone"
}
"""
        header = extract_mutopia_header(source)
        assert header["title"] == "My Piece"
        assert header["composer"] == "Someone"
        assert "mutopiatitle" not in header


class TestMapMutopiaToMetadata:
    """Tests for map_mutopia_to_metadata()."""

    def test_maps_composer_from_mutopiacomposer(self):
        """mutopiacomposer is preferred over composer field."""
        header = {"mutopiacomposer": "BachJS", "composer": "J.S. Bach"}
        meta = map_mutopia_to_metadata(header)
        assert meta["composer"] == "BachJS"

    def test_falls_back_to_composer_field(self):
        """Falls back to composer when mutopiacomposer is missing."""
        header = {"composer": "J.S. Bach"}
        meta = map_mutopia_to_metadata(header)
        assert meta["composer"] == "J.S. Bach"

    def test_instrument_family_keyboard(self):
        """Piano is classified as keyboard family."""
        header = {"mutopiainstrument": "Piano"}
        meta = map_mutopia_to_metadata(header)
        assert meta["instrument"] == "Piano"
        assert meta["instrument_family"] == "keyboard"

    def test_instrument_family_brass(self):
        """Trumpet is classified as brass family."""
        header = {"mutopiainstrument": "Trumpet"}
        meta = map_mutopia_to_metadata(header)
        assert meta["instrument_family"] == "brass"

    def test_instrument_family_strings(self):
        """Violin is classified as strings family."""
        header = {"mutopiainstrument": "Violin"}
        meta = map_mutopia_to_metadata(header)
        assert meta["instrument_family"] == "strings"

    def test_instrument_family_woodwind(self):
        """Clarinet is classified as woodwind family."""
        header = {"mutopiainstrument": "Clarinet"}
        meta = map_mutopia_to_metadata(header)
        assert meta["instrument_family"] == "woodwind"

    def test_instrument_family_unknown(self):
        """Unrecognized instrument is classified as other."""
        header = {"mutopiainstrument": "Theremin"}
        meta = map_mutopia_to_metadata(header)
        assert meta["instrument_family"] == "other"

    def test_era_inferred_from_style(self):
        """Baroque style maps to Baroque era."""
        header = {"style": "Baroque"}
        meta = map_mutopia_to_metadata(header)
        assert meta["era"] == "Baroque"

    def test_era_inferred_from_date(self):
        """Year 1723 maps to Baroque era."""
        header = {"date": "1723"}
        meta = map_mutopia_to_metadata(header)
        assert meta["era"] == "Baroque"

    def test_era_classical_from_date(self):
        """Year 1790 maps to Classical era."""
        header = {"date": "1790"}
        meta = map_mutopia_to_metadata(header)
        assert meta["era"] == "Classical"

    def test_empty_header_returns_empty_metadata(self):
        """Empty header produces empty metadata."""
        meta = map_mutopia_to_metadata({})
        assert meta == {}
