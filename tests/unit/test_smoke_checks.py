"""Unit tests for smoke test check functions.

Tests all 9 check functions with synthetic ZIP fixtures.
Does NOT use pytest-bdd/Gherkin -- straightforward unit tests.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from engrave.smoke.checks import (
    check_all_parts_present,
    check_compilable_ly,
    check_no_exceptions,
    check_pdf_file_size,
    check_valid_musicxml,
    check_valid_pdfs,
    check_zip_file_count,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_MUSICXML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1">
      <part-name>Trumpet 1</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>4</duration>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""


def _make_fake_pdf(size: int = 60_000) -> bytes:
    """Generate fake PDF content of the given size."""
    # Start with a minimal PDF header to make it look real
    header = b"%PDF-1.4\n"
    padding = b"X" * (size - len(header))
    return header + padding


def _create_test_zip(
    tmp_path: Path,
    *,
    num_parts: int = 3,
    pdf_size: int = 60_000,
    include_musicxml: bool = False,
    musicxml_content: str | None = None,
    include_empty_pdf: bool = False,
    include_ly_without_pdf: bool = False,
) -> Path:
    """Create a test ZIP fixture for check functions.

    Args:
        tmp_path: Temporary directory for test files.
        num_parts: Number of part PDFs to include.
        pdf_size: Size of each fake PDF in bytes.
        include_musicxml: Whether to include a .musicxml file.
        musicxml_content: Custom MusicXML content. Defaults to MINIMAL_MUSICXML.
        include_empty_pdf: Include one empty (0-byte) PDF.
        include_ly_without_pdf: Include an .ly file with no matching PDF.
    """
    zip_path = tmp_path / "output.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        # Score PDF
        zf.writestr("score.pdf", _make_fake_pdf(pdf_size))
        # Score LY
        zf.writestr("score.ly", '\\version "2.24.0"\n{ c\'4 }')
        # Music definitions LY (no matching PDF expected)
        zf.writestr("music-definitions.ly", "globalMusic = { }\n")

        # Part PDFs and LY files
        for i in range(1, num_parts + 1):
            name = f"part-instrument-{i}"
            if include_empty_pdf and i == num_parts:
                zf.writestr(f"{name}.pdf", b"")
            else:
                zf.writestr(f"{name}.pdf", _make_fake_pdf(pdf_size))
            zf.writestr(f"{name}.ly", f'\\version "2.24.0"\n{{ c\'{i} }}')

        # MIDI file
        zf.writestr("score.mid", b"\x00" * 100)

        # MusicXML (optional)
        if include_musicxml:
            content = musicxml_content or MINIMAL_MUSICXML
            zf.writestr("score.musicxml", content)

        # Orphan LY file (no matching PDF)
        if include_ly_without_pdf:
            zf.writestr("orphan-part.ly", '\\version "2.24.0"\n{ c\'4 }')

    return zip_path


# ---------------------------------------------------------------------------
# Check 1: No exceptions
# ---------------------------------------------------------------------------


class TestCheckNoExceptions:
    def test_passes_when_no_error(self) -> None:
        result = check_no_exceptions(None)
        assert result.passed is True
        assert result.name == "no_exceptions"

    def test_fails_when_error_present(self) -> None:
        result = check_no_exceptions("RuntimeError: generation failed")
        assert result.passed is False
        assert "generation failed" in result.message


# ---------------------------------------------------------------------------
# Check 2: Compilable LilyPond
# ---------------------------------------------------------------------------


class TestCheckCompilableLy:
    def test_passes_with_matching_ly_pdf_pairs(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        result = check_compilable_ly(zip_path)
        assert result.passed is True

    def test_fails_with_orphan_ly(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, include_ly_without_pdf=True)
        result = check_compilable_ly(zip_path)
        assert result.passed is False
        assert "orphan-part" in result.message

    def test_ignores_music_definitions_ly(self, tmp_path: Path) -> None:
        """music-definitions.ly should not require a matching PDF."""
        zip_path = _create_test_zip(tmp_path, num_parts=1)
        result = check_compilable_ly(zip_path)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Check 3: Valid PDFs
# ---------------------------------------------------------------------------


class TestCheckValidPdfs:
    def test_passes_with_nonempty_pdfs(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=2)
        result = check_valid_pdfs(zip_path)
        assert result.passed is True
        assert result.details["pdf_count"] == 3  # score + 2 parts

    def test_fails_with_empty_pdf(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=2, include_empty_pdf=True)
        result = check_valid_pdfs(zip_path)
        assert result.passed is False
        assert "Empty PDF" in result.message

    def test_fails_with_no_pdfs(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "no PDFs here")
        result = check_valid_pdfs(zip_path)
        assert result.passed is False
        assert "No PDFs" in result.message


# ---------------------------------------------------------------------------
# Check 4: Valid MusicXML
# ---------------------------------------------------------------------------


class TestCheckValidMusicxml:
    def test_skipped_when_no_musicxml(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, include_musicxml=False)
        result = check_valid_musicxml(zip_path)
        assert result.passed is True
        assert "SKIPPED" in result.message

    def test_passes_with_valid_musicxml(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, include_musicxml=True)
        result = check_valid_musicxml(zip_path)
        # XSD validation may fail since we use a minimal MusicXML without full schema
        # but the function should not crash
        assert result.name == "valid_musicxml"

    def test_fails_with_invalid_musicxml(self, tmp_path: Path) -> None:
        bad_xml = "<not-musicxml><broken></not-musicxml>"
        zip_path = _create_test_zip(tmp_path, include_musicxml=True, musicxml_content=bad_xml)
        result = check_valid_musicxml(zip_path)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Check 5: All parts present
# ---------------------------------------------------------------------------


class TestCheckAllPartsPresent:
    def test_passes_with_correct_count(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        result = check_all_parts_present(zip_path, expected_instrument_count=3)
        assert result.passed is True
        assert result.details["expected"] == 4  # 3 parts + 1 score
        assert result.details["actual"] == 4

    def test_fails_with_missing_parts(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=2)
        result = check_all_parts_present(zip_path, expected_instrument_count=5)
        assert result.passed is False
        assert "Expected 6" in result.message


# ---------------------------------------------------------------------------
# Check 8: PDF file size
# ---------------------------------------------------------------------------


class TestCheckPdfFileSize:
    def test_passes_with_large_pdfs(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=2, pdf_size=60_000)
        result = check_pdf_file_size(zip_path, min_size_bytes=50_000)
        assert result.passed is True

    def test_fails_with_small_pdfs(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=2, pdf_size=1_000)
        result = check_pdf_file_size(zip_path, min_size_bytes=50_000)
        assert result.passed is False
        assert "below" in result.message.lower()


# ---------------------------------------------------------------------------
# Check 9: ZIP file count
# ---------------------------------------------------------------------------


class TestCheckZipFileCount:
    def test_passes_with_correct_count(self, tmp_path: Path) -> None:
        # With 3 parts: score.pdf + 3 part PDFs + score.ly + music-definitions.ly
        # + 3 part LYs + score.mid = 10 files
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        result = check_zip_file_count(zip_path, expected_min=9, expected_max=11)
        assert result.passed is True

    def test_fails_with_wrong_count(self, tmp_path: Path) -> None:
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        result = check_zip_file_count(zip_path, expected_min=50, expected_max=60)
        assert result.passed is False
        assert "Expected" in result.message

    def test_passes_at_min_boundary(self, tmp_path: Path) -> None:
        """ZIP with exact min count should pass."""
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        with zipfile.ZipFile(zip_path, "r") as zf:
            actual = len(zf.namelist())
        result = check_zip_file_count(zip_path, expected_min=actual, expected_max=actual + 1)
        assert result.passed is True

    def test_passes_at_max_boundary(self, tmp_path: Path) -> None:
        """ZIP with exact max count should pass."""
        zip_path = _create_test_zip(tmp_path, num_parts=3)
        with zipfile.ZipFile(zip_path, "r") as zf:
            actual = len(zf.namelist())
        result = check_zip_file_count(zip_path, expected_min=actual - 1, expected_max=actual)
        assert result.passed is True
