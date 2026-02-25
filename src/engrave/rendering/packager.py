"""Render pipeline: write .ly files, compile to PDF, package into ZIP.

Connects the generators (04-02) to the compiler (Phase 1) and produces
the deliverable ZIP archive containing score PDF, 17 part PDFs, all .ly
source files, and MIDI output.

Public API
----------
- ``RenderPipeline`` -- orchestrates the full render pipeline
- ``RenderResult`` -- dataclass capturing pipeline output
"""

from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

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

    Lowercase, replace spaces and special characters with hyphens,
    strip leading/trailing hyphens, collapse consecutive hyphens.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


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
    ) -> None:
        self.preset = preset
        self.compiler = compiler or LilyPondCompiler()
        self.score_timeout = score_timeout
        self.part_timeout = part_timeout

    def render(
        self,
        music_vars: dict[str, str],
        global_music: str,
        chord_symbols: str | None,
        song_title: str | None,
        output_dir: Path,
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
            for ext in ("*.pdf", "*.ly", "*.mid"):
                for file_path in sorted(work_dir.glob(ext)):
                    zf.write(file_path, file_path.name)
        return output_path
