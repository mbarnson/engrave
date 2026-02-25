"""Integration test: graceful degradation for MusicXML export.

Validates that invalid JSON, None sections, partial failures, and
RenderPipeline integration handle errors gracefully without crashing
the pipeline.  LilyPond output is never affected by MusicXML failures.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from engrave.generation.json_assembler import assemble_musicxml
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


# ---------------------------------------------------------------------------
# Tests: assemble_musicxml degradation
# ---------------------------------------------------------------------------


class TestAssembleDegradation:
    """Graceful degradation scenarios for assemble_musicxml."""

    def test_all_sections_none(self, tmp_path: Path) -> None:
        """All sections None -> returns (False, None), does not crash."""
        success, path = assemble_musicxml(
            json_sections=[None, None],
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=tmp_path / "score.musicxml",
        )

        assert success is False
        assert path is None

    def test_invalid_pydantic_structure(self, tmp_path: Path) -> None:
        """JSON with missing required fields -> returns (False, None), logs warning."""
        # MeasureData requires 'number' and 'notes'; this dict is missing both
        invalid_json = [{"instrument": "trumpet_1"}]  # Missing 'measures'

        success, path = assemble_musicxml(
            json_sections=[invalid_json],
            instrument_names=["Trumpet 1"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=tmp_path / "score.musicxml",
        )

        assert success is False
        assert path is None

    def test_partial_sections_mixed_valid_and_none(self, tmp_path: Path) -> None:
        """Mixture of valid and None sections -> partial assembly succeeds."""
        valid_section = {
            "instrument": "trumpet_1",
            "key": "bf_major",
            "time_signature": "4/4",
            "measures": [
                {
                    "number": 1,
                    "notes": [
                        {"pitch": "bf4", "beat": 1.0, "duration": 4.0, "dynamic": "f"},
                    ],
                }
            ],
        }

        json_sections: list[list[dict] | None] = [
            None,  # First section failed
            [valid_section],  # Second section valid
        ]

        success, path = assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=tmp_path / "score.musicxml",
        )

        assert success is True
        assert path is not None
        assert path.exists()

    def test_invalid_pitch_format_degrades_gracefully(self, tmp_path: Path) -> None:
        """Invalid pitch format in JSON -> that item skipped, no crash."""
        bad_section = {
            "instrument": "trumpet_1",
            "measures": [
                {
                    "number": 1,
                    "notes": [
                        {"pitch": "INVALID_PITCH", "beat": 1.0, "duration": 1.0},
                    ],
                }
            ],
        }

        success, path = assemble_musicxml(
            json_sections=[[bad_section]],
            instrument_names=["Trumpet 1"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=tmp_path / "score.musicxml",
        )

        # Should return (False, None) because Pydantic validation rejects the pitch
        assert success is False
        assert path is None


# ---------------------------------------------------------------------------
# Tests: RenderPipeline MusicXML degradation
# ---------------------------------------------------------------------------


class TestRenderPipelineMusicXMLDegradation:
    """RenderPipeline with MusicXML failures still produces ZIP without crash."""

    def test_zip_without_musicxml_when_json_none(self, tmp_path: Path) -> None:
        """include_musicxml=True but json_sections=None -> ZIP has .ly/.pdf, no .musicxml."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=mock_compiler,
            include_musicxml=True,
        )

        music_vars: dict[str, str] = {}
        for inst in BIG_BAND.instruments:
            music_vars[inst.variable_name] = "c'4 d' e' f' | g'1 |"
            if inst.is_grand_staff:
                music_vars[f"{inst.variable_name}Left"] = "c4 d e f | g1 |"

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4 \\key c \\major s1*2 |",
            chord_symbols=None,
            song_title="No MusicXML Test",
            output_dir=tmp_path,
            json_sections=None,  # No JSON data
            instrument_names=None,
        )

        assert result.zip_path.exists()

        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()

        # ZIP should have .ly and .pdf files
        ly_files = [n for n in names if n.endswith(".ly")]
        assert len(ly_files) > 0

        # ZIP should NOT have .musicxml (no JSON data available)
        musicxml_files = [n for n in names if n.endswith(".musicxml")]
        assert len(musicxml_files) == 0

    def test_zip_without_musicxml_when_all_json_none(self, tmp_path: Path) -> None:
        """include_musicxml=True but all json_sections are None -> ZIP without .musicxml."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=mock_compiler,
            include_musicxml=True,
        )

        music_vars: dict[str, str] = {}
        for inst in BIG_BAND.instruments:
            music_vars[inst.variable_name] = "c'4 d' e' f' | g'1 |"
            if inst.is_grand_staff:
                music_vars[f"{inst.variable_name}Left"] = "c4 d e f | g1 |"

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="All None JSON",
            output_dir=tmp_path,
            json_sections=[None, None],  # All sections failed
            instrument_names=["Trumpet 1", "Alto Sax"],
        )

        assert result.zip_path.exists()

        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()

        # No MusicXML because all sections are None (has_data check fails)
        musicxml_files = [n for n in names if n.endswith(".musicxml")]
        assert len(musicxml_files) == 0

    def test_no_musicxml_flag_excludes_musicxml(self, tmp_path: Path) -> None:
        """include_musicxml=False -> ZIP never has .musicxml even with valid JSON."""
        mock_compiler = _make_mock_compiler()
        pipeline = RenderPipeline(
            preset=BIG_BAND,
            compiler=mock_compiler,
            include_musicxml=False,
        )

        music_vars: dict[str, str] = {}
        for inst in BIG_BAND.instruments:
            music_vars[inst.variable_name] = "c'4 d' e' f' |"
            if inst.is_grand_staff:
                music_vars[f"{inst.variable_name}Left"] = "c4 d e f |"

        valid_section = {
            "instrument": "trumpet_1",
            "key": "bf_major",
            "time_signature": "4/4",
            "measures": [
                {
                    "number": 1,
                    "notes": [{"pitch": "bf4", "beat": 1.0, "duration": 4.0}],
                }
            ],
        }

        result = pipeline.render(
            music_vars=music_vars,
            global_music="\\time 4/4",
            chord_symbols=None,
            song_title="No MusicXML Flag",
            output_dir=tmp_path,
            json_sections=[[valid_section]],
            instrument_names=["Trumpet 1"],
        )

        assert result.zip_path.exists()

        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()

        musicxml_files = [n for n in names if n.endswith(".musicxml")]
        assert len(musicxml_files) == 0
