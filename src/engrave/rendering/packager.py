"""Render pipeline: write .ly files, compile to PDF, package into ZIP.

Connects the generators (04-02) to the compiler (Phase 1) and produces
the deliverable ZIP archive containing score PDF, 17 part PDFs, all .ly
source files, MIDI output, and optionally a MusicXML file for Dorico import.

Public API
----------
- ``RenderPipeline`` -- orchestrates the full render pipeline
- ``RenderResult`` -- dataclass capturing pipeline output
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from slugify import slugify

from engrave.lilypond.compiler import LilyPondCompiler
from engrave.rendering.ensemble import BigBandPreset
from engrave.rendering.generator import (
    generate_conductor_score,
    generate_music_definitions,
    generate_part,
    restate_dynamics,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify_title(title: str) -> str:
    """Slugify a song title for use in filenames.

    Uses python-slugify for proper Unicode/diacritics handling.
    Song titles may contain non-ASCII characters unlike instrument names.
    """
    return slugify(title)


# ---------------------------------------------------------------------------
# RenderResult
# ---------------------------------------------------------------------------


@dataclass
class RenderResult:
    """Result of a render pipeline run.

    Attributes
    ----------
    zip_path:
        Path to the output ZIP archive.
    success:
        True if score and all parts compiled successfully.
    compiled:
        Filenames that compiled successfully.
    failed:
        Filenames that failed compilation.
    errors:
        Mapping of filename to error message for failures.
    """

    zip_path: Path
    success: bool
    compiled: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# RenderPipeline
# ---------------------------------------------------------------------------


class RenderPipeline:
    """Orchestrate .ly generation, compilation, and ZIP packaging.

    Parameters
    ----------
    preset:
        The ensemble preset (e.g. ``BIG_BAND``).
    compiler:
        A ``LilyPondCompiler`` instance. If ``None``, creates one with
        default settings.
    score_timeout:
        Compilation timeout in seconds for the conductor score (default 300).
    part_timeout:
        Compilation timeout in seconds for individual parts (default 60).
    """

    def __init__(
        self,
        preset: BigBandPreset,
        compiler: LilyPondCompiler | None = None,
        score_timeout: int = 300,
        part_timeout: int = 60,
        include_musicxml: bool = True,
    ) -> None:
        self.preset = preset
        self.compiler = compiler or LilyPondCompiler()
        self.score_timeout = score_timeout
        self.part_timeout = part_timeout
        self.include_musicxml = include_musicxml

    def render(
        self,
        music_vars: dict[str, str],
        global_music: str,
        chord_symbols: str | None,
        song_title: str | None,
        output_dir: Path,
        json_sections: list[list[dict] | None] | None = None,
        instrument_names: list[str] | None = None,
        key_sig: str = "c \\major",
        time_sig: str = "4/4",
        tempo_bpm: int = 120,
    ) -> RenderResult:
        """Run the full render pipeline.

        Parameters
        ----------
        music_vars:
            Mapping of LilyPond variable names to concert-pitch content.
        global_music:
            The globalMusic content (time sig, key, rehearsal marks).
        chord_symbols:
            Optional chordSymbols content in chordmode.
        song_title:
            Song title for the ZIP filename. Falls back to "untitled".
        output_dir:
            Directory where the work files and ZIP are created.
        json_sections:
            Optional per-section JSON notation data for MusicXML generation.
            Each entry is a list of dicts (one per instrument) or None.
        instrument_names:
            Optional list of instrument display names for MusicXML assembly.
        key_sig:
            Key signature for MusicXML (LilyPond-style, e.g. ``"c \\major"``).
        time_sig:
            Time signature for MusicXML (e.g. ``"4/4"``).
        tempo_bpm:
            Tempo in BPM for MusicXML (default 120).

        Returns
        -------
        RenderResult
            Result with ZIP path, success status, and compilation details.
        """
        work_dir = output_dir / "_work"
        work_dir.mkdir(parents=True, exist_ok=True)

        compiled: list[str] = []
        failed: list[str] = []
        errors: dict[str, str] = {}

        # 1. Apply restate_dynamics to each instrument's music content
        restated_vars: dict[str, str] = {}
        for var_name, content in music_vars.items():
            restated_vars[var_name] = restate_dynamics(content)

        # 2. Generate music-definitions.ly
        defs_content = generate_music_definitions(restated_vars, global_music, chord_symbols)
        defs_path = work_dir / "music-definitions.ly"
        defs_path.write_text(defs_content)

        # 3. Generate conductor score
        has_chords = chord_symbols is not None
        var_names = list(restated_vars.keys())
        score_content = generate_conductor_score(
            preset=self.preset,
            music_var_names=var_names,
            has_chords=has_chords,
            title=song_title or "",
        )
        score_path = work_dir / "score.ly"
        score_path.write_text(score_content)

        # 4. Generate individual parts
        part_paths: list[Path] = []
        for instrument in self.preset.instruments:
            slug = instrument.name.lower().replace(" ", "-")
            part_content = generate_part(
                instrument=instrument,
                preset_name=self.preset.name,
                has_chords=instrument.has_chord_symbols and has_chords,
                title=song_title or "",
            )
            part_path = work_dir / f"part-{slug}.ly"
            part_path.write_text(part_content)
            part_paths.append(part_path)

        # 5. Compile score with score_timeout
        self.compiler.timeout = self.score_timeout
        score_result = self.compiler.compile(score_content, output_dir=work_dir)
        if score_result.success:
            compiled.append("score.ly")
            logger.info("Score compiled successfully")
        else:
            failed.append("score.ly")
            errors["score.ly"] = score_result.stderr
            logger.error("Score compilation failed: %s", score_result.stderr)

        # 6. Compile each part with part_timeout
        self.compiler.timeout = self.part_timeout
        for part_path in part_paths:
            part_ly_name = part_path.name
            part_source = part_path.read_text()
            part_result = self.compiler.compile(part_source, output_dir=work_dir)
            if part_result.success:
                compiled.append(part_ly_name)
                logger.info("Compiled %s", part_ly_name)
            else:
                failed.append(part_ly_name)
                errors[part_ly_name] = part_result.stderr
                logger.error("Failed to compile %s: %s", part_ly_name, part_result.stderr)

        # 6.5. Generate MusicXML (optional)
        if self.include_musicxml and json_sections is not None:
            has_data = any(s is not None for s in json_sections)
            if has_data:
                try:
                    from engrave.generation.json_assembler import assemble_musicxml

                    musicxml_path = work_dir / "score.musicxml"
                    names = instrument_names or list(music_vars.keys())
                    success_mxml, _mxml_path = assemble_musicxml(
                        json_sections=json_sections,
                        instrument_names=names,
                        key_sig=key_sig,
                        time_sig=time_sig,
                        tempo_bpm=tempo_bpm,
                        output_path=musicxml_path,
                    )
                    if success_mxml:
                        logger.info("MusicXML generated: %s", musicxml_path)
                    else:
                        logger.warning("MusicXML generation failed; continuing without")
                except Exception as exc:
                    logger.warning("MusicXML generation error: %s", str(exc)[:200])

        # 7. Package ZIP
        title_slug = _slugify_title(song_title) if song_title else "untitled"
        zip_name = f"{title_slug}-{date.today().isoformat()}.zip"
        zip_path = output_dir / zip_name
        self._package_zip(work_dir, zip_path)

        success = len(failed) == 0
        return RenderResult(
            zip_path=zip_path,
            success=success,
            compiled=compiled,
            failed=failed,
            errors=errors,
        )

    def _package_zip(self, work_dir: Path, output_path: Path) -> Path:
        """Assemble all .pdf, .ly, .mid files from work_dir into a ZIP.

        Uses flat naming (just filenames, no directory structure).

        Parameters
        ----------
        work_dir:
            Directory containing compiled output files.
        output_path:
            Path for the output ZIP file.

        Returns
        -------
        Path
            The output ZIP path.
        """
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext in ("*.pdf", "*.ly", "*.mid", "*.musicxml"):
                for file_path in sorted(work_dir.glob(ext)):
                    zf.write(file_path, file_path.name)
        return output_path
