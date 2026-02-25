"""Unit tests for MusicXML XSD validation."""

from __future__ import annotations

from pathlib import Path

import music21

from engrave.musicxml.validator import validate_musicxml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_valid_musicxml(path: Path) -> Path:
    """Write a minimal valid MusicXML file using music21."""
    s = music21.stream.Score()
    p = music21.stream.Part()
    p.partName = "Test"
    m = music21.stream.Measure(number=1)
    m.append(music21.meter.TimeSignature("4/4"))
    n = music21.note.Note("C4")
    n.quarterLength = 4.0
    m.append(n)
    p.append(m)
    s.insert(0, p)
    out = path / "valid.musicxml"
    s.write("musicxml", fp=str(out))
    return out


def _write_invalid_xml(path: Path) -> Path:
    """Write an XML file that is not valid MusicXML."""
    out = path / "invalid.musicxml"
    out.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<not-musicxml><bogus>content</bogus></not-musicxml>\n"
    )
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateMusicxml:
    """Tests for validate_musicxml()."""

    def test_valid_musicxml_passes(self, tmp_path: Path) -> None:
        """Valid music21-generated MusicXML passes XSD validation."""
        mxml_path = _write_valid_musicxml(tmp_path)
        is_valid, error = validate_musicxml(mxml_path)
        assert is_valid is True
        assert error == ""

    def test_invalid_xml_fails_with_message(self, tmp_path: Path) -> None:
        """Non-MusicXML XML fails validation with a descriptive error."""
        mxml_path = _write_invalid_xml(tmp_path)
        is_valid, error = validate_musicxml(mxml_path)
        assert is_valid is False
        assert len(error) > 0

    def test_missing_file_handled_gracefully(self, tmp_path: Path) -> None:
        """Non-existent file returns (False, error) without raising."""
        missing = tmp_path / "does-not-exist.musicxml"
        is_valid, error = validate_musicxml(missing)
        assert is_valid is False
        assert "not found" in error.lower()

    def test_missing_xsd_handled_gracefully(self, tmp_path: Path) -> None:
        """Non-existent XSD returns (False, error) without raising."""
        mxml_path = _write_valid_musicxml(tmp_path)
        fake_xsd = tmp_path / "missing.xsd"
        is_valid, error = validate_musicxml(mxml_path, xsd_path=fake_xsd)
        assert is_valid is False
        assert "not found" in error.lower()

    def test_custom_xsd_path(self, tmp_path: Path) -> None:
        """Custom XSD path is used when provided."""
        mxml_path = _write_valid_musicxml(tmp_path)
        # Use the vendored schema explicitly
        default_xsd = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "engrave"
            / "musicxml"
            / "schema"
            / "musicxml.xsd"
        )
        is_valid, error = validate_musicxml(mxml_path, xsd_path=default_xsd)
        assert is_valid is True
        assert error == ""

    def test_malformed_xml_handled(self, tmp_path: Path) -> None:
        """Completely malformed (non-XML) content fails gracefully."""
        bad_file = tmp_path / "garbage.musicxml"
        bad_file.write_text("this is not xml at all")
        is_valid, error = validate_musicxml(bad_file)
        assert is_valid is False
        assert len(error) > 0
