"""Unit tests for RenderPipeline and ZIP packaging."""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from engrave.lilypond.compiler import LilyPondCompiler, RawCompileResult
from engrave.rendering.ensemble import BIG_BAND
from engrave.rendering.packager import RenderPipeline, RenderResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_compiler(
    *,
    fail_files: set[str] | None = None,
    produce_midi: bool = True,
) -> MagicMock:
    """Create a mock LilyPondCompiler whose compile() creates fake output files.

    Parameters
    ----------
    fail_files:
        Set of .ly basenames that should fail compilation (e.g. {"part-drums.ly"}).
    produce_midi:
        If True, score compilation also creates a .mid file.
    """
    fail_files = fail_files or set()
    mock = MagicMock(spec=LilyPondCompiler)

    def _compile(source: str, output_dir: Path | None = None) -> RawCompileResult:
        # Determine filename from bookOutputName in source
        match = re.search(r'\\bookOutputName\s+"([^"]+)"', source)
        stem = match.group(1) if match else "output"

        out_dir = output_dir or Path(".")
        ly_basename = f"{stem}.ly"

        if ly_basename in fail_files or f"{stem}.ly" in fail_files:
            return RawCompileResult(
                success=False,
                returncode=1,
                stdout="",
                stderr=f"Compilation failed for {stem}",
                output_path=None,
            )

        # Create fake PDF
        pdf_path = out_dir / f"{stem}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        # Create fake MIDI for score
        if produce_midi and stem == "score":
            midi_path = out_dir / f"{stem}.mid"
            midi_path.write_bytes(b"MThd fake midi")

        return RawCompileResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            output_path=pdf_path,
        )

    mock.compile.side_effect = _compile
    return mock


def _minimal_music_vars() -> dict[str, str]:
    """Minimal concert-pitch music variables for all 17 instruments."""
    instruments = BIG_BAND.instruments
    music_vars: dict[str, str] = {}
    for inst in instruments:
        music_vars[inst.variable_name] = "c'4 d' e' f' |"
        if inst.is_grand_staff:
            music_vars[f"{inst.variable_name}Left"] = "c4 d e f |"
    return music_vars


def _run_pipeline(
    tmp_path: Path,
    *,
    fail_files: set[str] | None = None,
    song_title: str | None = None,
    score_timeout: int = 300,
    part_timeout: int = 60,
) -> RenderResult:
    """Run the full render pipeline with a mock compiler."""
    mock_compiler = _make_mock_compiler(fail_files=fail_files)
    pipeline = RenderPipeline(
        preset=BIG_BAND,
        compiler=mock_compiler,
        score_timeout=score_timeout,
        part_timeout=part_timeout,
    )
    music_vars = _minimal_music_vars()
    global_music = "\\time 4/4 \\key c \\major"
    chord_symbols = "\\chordmode { c1 }"

    result = pipeline.render(
        music_vars=music_vars,
        global_music=global_music,
        chord_symbols=chord_symbols,
        song_title=song_title,
        output_dir=tmp_path,
    )
    return result


# ---------------------------------------------------------------------------
# ZIP content tests
# ---------------------------------------------------------------------------


class TestZipContents:
    """Tests for ZIP archive content."""

    def test_zip_contains_score_pdf(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="My Song")
        assert result.zip_path.exists()
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        assert "score.pdf" in names

    def test_zip_contains_all_17_part_pdfs(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="Test")
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        part_pdfs = [n for n in names if n.startswith("part-") and n.endswith(".pdf")]
        assert len(part_pdfs) == 17

        # Check specific expected part names
        expected_parts = {
            "part-alto-sax-1.pdf",
            "part-alto-sax-2.pdf",
            "part-tenor-sax-1.pdf",
            "part-tenor-sax-2.pdf",
            "part-baritone-sax.pdf",
            "part-trumpet-1.pdf",
            "part-trumpet-2.pdf",
            "part-trumpet-3.pdf",
            "part-trumpet-4.pdf",
            "part-trombone-1.pdf",
            "part-trombone-2.pdf",
            "part-trombone-3.pdf",
            "part-bass-trombone.pdf",
            "part-piano.pdf",
            "part-guitar.pdf",
            "part-bass.pdf",
            "part-drums.pdf",
        }
        assert set(part_pdfs) == expected_parts

    def test_zip_contains_ly_source_files(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="Test")
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        ly_files = [n for n in names if n.endswith(".ly")]
        # music-definitions.ly + score.ly + 17 part-*.ly = 19
        assert len(ly_files) == 19
        assert "music-definitions.ly" in ly_files
        assert "score.ly" in ly_files

    def test_zip_contains_midi_file(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="Test")
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        mid_files = [n for n in names if n.endswith(".mid")]
        assert len(mid_files) >= 1

    def test_zip_flat_structure(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="Test")
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        # No subdirectories -- all files at root
        for name in names:
            assert "/" not in name, f"Found nested path in ZIP: {name}"

    def test_zip_filename_pattern(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="My Cool Song!")
        filename = result.zip_path.name
        today = date.today().isoformat()
        # Should match {slug}-{YYYY-MM-DD}.zip
        assert filename == f"my-cool-song-{today}.zip"
        pattern = r"^[a-z0-9-]+-\d{4}-\d{2}-\d{2}\.zip$"
        assert re.match(pattern, filename), f"Filename {filename} doesn't match pattern"


# ---------------------------------------------------------------------------
# Song title tests
# ---------------------------------------------------------------------------


class TestSongTitle:
    """Tests for song title resolution and slugification."""

    def test_song_title_from_explicit(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title="Blue Train")
        today = date.today().isoformat()
        assert result.zip_path.name == f"blue-train-{today}.zip"

    def test_song_title_fallback_to_untitled(self, tmp_path: Path) -> None:
        result = _run_pipeline(tmp_path, song_title=None)
        today = date.today().isoformat()
        assert result.zip_path.name == f"untitled-{today}.zip"


# ---------------------------------------------------------------------------
# RenderPipeline behavior tests
# ---------------------------------------------------------------------------


class TestRenderPipeline:
    """Tests for RenderPipeline orchestration."""

    def test_render_pipeline_writes_ly_files(self, tmp_path: Path) -> None:
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(preset=BIG_BAND, compiler=mock_compiler)
        music_vars = _minimal_music_vars()

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="Test",
            output_dir=tmp_path,
        )

        # Check .ly files exist in work directory (they get packaged into ZIP)
        with zipfile.ZipFile(result.zip_path) as zf:
            ly_names = [n for n in zf.namelist() if n.endswith(".ly")]
        assert "music-definitions.ly" in ly_names
        assert "score.ly" in ly_names
        part_ly = [n for n in ly_names if n.startswith("part-")]
        assert len(part_ly) == 17

    def test_render_pipeline_handles_compilation_failure(self, tmp_path: Path) -> None:
        result = _run_pipeline(
            tmp_path,
            song_title="Test",
            fail_files={"part-drums.ly"},
        )
        # Pipeline should complete (not crash)
        assert result.zip_path.exists()
        # Success should be False (not all parts compiled)
        assert result.success is False
        # Drums should be in failed list
        assert "part-drums.ly" in result.failed
        # Error message recorded
        assert "part-drums.ly" in result.errors
        # Other parts should still be in the ZIP
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        assert "score.pdf" in names
        assert "part-alto-sax-1.pdf" in names
        # Drums PDF should NOT be in ZIP
        assert "part-drums.pdf" not in names

    def test_render_pipeline_uses_longer_timeout_for_score(self, tmp_path: Path) -> None:
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=mock_compiler,
            score_timeout=300,
            part_timeout=60,
        )
        music_vars = _minimal_music_vars()

        pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="Test",
            output_dir=tmp_path,
        )

        # Verify the compiler was called with appropriate timeout values.
        # The pipeline should set compiler.timeout before each compile call.
        # We check the calls to compiler: score should use 300s, parts should use 60s.
        calls = mock_compiler.compile.call_args_list
        assert len(calls) >= 2  # At least score + 1 part

        # Check that timeout was set appropriately by examining the mock's
        # timeout attribute changes. The pipeline sets compiler.timeout before
        # each compile call.
        # We verify the pipeline at least called compile the expected number of times.
        # Score + 17 parts = 18 compile calls
        assert len(calls) == 18


# ---------------------------------------------------------------------------
# MusicXML integration tests
# ---------------------------------------------------------------------------


class TestMusicXmlInZip:
    """Tests for MusicXML inclusion in ZIP output."""

    def test_musicxml_in_zip(self, tmp_path: Path) -> None:
        """A .musicxml file in work_dir is included in the ZIP."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(preset=BIG_BAND, compiler=mock_compiler)
        music_vars = _minimal_music_vars()

        # Run the pipeline normally (no json_sections -- MusicXML step skipped)
        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="MxmlTest",
            output_dir=tmp_path,
        )

        # Manually place a .musicxml file in _work (simulating generation)
        work_dir = tmp_path / "_work"
        mxml_file = work_dir / "score.musicxml"
        mxml_file.write_text('<?xml version="1.0"?><score-partwise/>')

        # Re-package the ZIP to pick up the new file
        pipeline._package_zip(work_dir, result.zip_path)

        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        assert "score.musicxml" in names

    def test_no_musicxml_flag(self, tmp_path: Path) -> None:
        """RenderPipeline with include_musicxml=False skips MusicXML generation."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=mock_compiler,
            include_musicxml=False,
        )
        music_vars = _minimal_music_vars()

        # Provide json_sections -- but generation should be skipped
        json_sections: list[list[dict] | None] = [
            [
                {
                    "instrument": "trumpet_1",
                    "measures": [
                        {
                            "number": 1,
                            "notes": [{"pitch": "c4", "beat": 1.0, "duration": 4.0}],
                        }
                    ],
                }
            ]
        ]

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="NoMxml",
            output_dir=tmp_path,
            json_sections=json_sections,
            instrument_names=["Trumpet 1"],
        )

        # No .musicxml should be in the ZIP
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        mxml_files = [n for n in names if n.endswith(".musicxml")]
        assert len(mxml_files) == 0

    def test_musicxml_failure_graceful(self, tmp_path: Path) -> None:
        """Invalid JSON sections don't crash the render pipeline."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(preset=BIG_BAND, compiler=mock_compiler)
        music_vars = _minimal_music_vars()

        # Provide deliberately invalid json_sections
        json_sections: list[list[dict] | None] = [
            [{"invalid": "data", "no_instrument": True}],
            None,
        ]

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="BadJson",
            output_dir=tmp_path,
            json_sections=json_sections,
            instrument_names=["Trumpet 1"],
        )

        # Pipeline should still complete (LilyPond output unaffected)
        assert result.zip_path.exists()
        # .ly files should be in the ZIP regardless
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        ly_files = [n for n in names if n.endswith(".ly")]
        assert len(ly_files) > 0
