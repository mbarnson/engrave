"""Integration tests for the full render pipeline."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from engrave.lilypond.compiler import LilyPondCompiler, RawCompileResult
from engrave.rendering.ensemble import BIG_BAND
from engrave.rendering.packager import RenderPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_compiler(*, fail_files: set[str] | None = None) -> MagicMock:
    """Create a mock compiler that produces fake PDFs and MIDI."""
    fail_files = fail_files or set()
    mock = MagicMock(spec=LilyPondCompiler)

    def _compile(source: str, output_dir: Path | None = None) -> RawCompileResult:
        match = re.search(r'\\bookOutputName\s+"([^"]+)"', source)
        stem = match.group(1) if match else "output"
        out_dir = output_dir or Path(".")

        if f"{stem}.ly" in fail_files:
            return RawCompileResult(
                success=False,
                returncode=1,
                stdout="",
                stderr=f"Error compiling {stem}",
                output_path=None,
            )

        pdf_path = out_dir / f"{stem}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        if stem == "score":
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


def test_full_render_pipeline(tmp_path: Path) -> None:
    """End-to-end test: generate .ly files, compile, and package ZIP.

    Uses a subset of instruments (alto sax 1, trumpet 1, guitar, bass) to
    verify the full pipeline flow with mocked compilation.
    """
    mock_compiler = _make_mock_compiler()
    pipeline = RenderPipeline(
        preset=BIG_BAND,
        compiler=mock_compiler,
    )

    # Provide music content for all 17 instruments (required by BIG_BAND preset)
    music_vars: dict[str, str] = {}
    for inst in BIG_BAND.instruments:
        music_vars[inst.variable_name] = "c'4 d' e' f' | g'1 |"
        if inst.is_grand_staff:
            music_vars[f"{inst.variable_name}Left"] = "c4 d e f | g1 |"

    global_music = "\\time 4/4 \\key c \\major s1*2 |"
    chord_symbols = "\\chordmode { c1 g1 }"

    result = pipeline.render(
        music_vars=music_vars,
        global_music=global_music,
        chord_symbols=chord_symbols,
        song_title="Integration Test Song",
        output_dir=tmp_path,
    )

    # Assertions
    assert result.zip_path.exists()
    assert result.success is True
    assert len(result.failed) == 0
    assert len(result.compiled) == 18  # score + 17 parts

    with zipfile.ZipFile(result.zip_path) as zf:
        names = zf.namelist()

    # Score PDF and MIDI
    assert "score.pdf" in names
    assert "score.mid" in names

    # Part PDFs
    part_pdfs = [n for n in names if n.startswith("part-") and n.endswith(".pdf")]
    assert len(part_pdfs) == 17

    # LilyPond source files
    ly_files = [n for n in names if n.endswith(".ly")]
    assert "music-definitions.ly" in ly_files
    assert "score.ly" in ly_files
    assert len(ly_files) == 19  # music-definitions + score + 17 parts

    # ZIP filename pattern
    assert "integration-test-song-" in result.zip_path.name
    assert result.zip_path.name.endswith(".zip")


def test_render_partial_failure(tmp_path: Path) -> None:
    """Pipeline handles compilation failure for one part gracefully.

    One part (drums) fails to compile. The pipeline should complete without
    raising, report the failure, and include all other successfully compiled
    files in the ZIP.
    """
    mock_compiler = _make_mock_compiler(fail_files={"part-drums.ly"})
    pipeline = RenderPipeline(
        preset=BIG_BAND,
        compiler=mock_compiler,
    )

    music_vars: dict[str, str] = {}
    for inst in BIG_BAND.instruments:
        music_vars[inst.variable_name] = "c'4 d' e' f' |"
        if inst.is_grand_staff:
            music_vars[f"{inst.variable_name}Left"] = "c4 d e f |"

    result = pipeline.render(
        music_vars=music_vars,
        global_music="\\time 4/4",
        chord_symbols=None,
        song_title="Partial Failure Test",
        output_dir=tmp_path,
    )

    # Pipeline completes without exception
    assert result.zip_path.exists()

    # Success is False (one part failed)
    assert result.success is False

    # Drums is in failed list
    assert "part-drums.ly" in result.failed
    assert "part-drums.ly" in result.errors

    # Score and other parts compiled successfully
    assert "score.ly" in result.compiled
    assert len(result.compiled) == 17  # score + 16 of 17 parts

    # ZIP still contains all other files
    with zipfile.ZipFile(result.zip_path) as zf:
        names = zf.namelist()
    assert "score.pdf" in names
    assert "part-alto-sax-1.pdf" in names
    # Drums PDF should NOT be in ZIP (compilation failed)
    assert "part-drums.pdf" not in names
    # But drums .ly source IS in ZIP (source files always included)
    assert "part-drums.ly" in names
