"""LilyPond subprocess wrapper with binary resolution."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawCompileResult:
    """Raw result from lilypond subprocess."""

    success: bool
    returncode: int
    stdout: str
    stderr: str
    output_path: Path | None


class LilyPondCompiler:
    """Thin wrapper around the lilypond CLI.

    Resolves the LilyPond binary at init time (shutil.which first,
    then common fallback paths per Pitfall 6). Compiles LilyPond source
    to PDF via subprocess, capturing stdout/stderr for error parsing.
    """

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout
        self.binary = self._find_binary()

    def _find_binary(self) -> str:
        """Resolve lilypond binary path.

        Checks shutil.which first, then common Homebrew/system locations.

        Returns:
            Absolute path to the lilypond binary.

        Raises:
            FileNotFoundError: If lilypond is not found anywhere.
        """
        path = shutil.which("lilypond")
        if path:
            return path

        # Common fallback locations
        home = Path.home()
        for candidate in [
            str(home / "bin" / "lilypond"),
            "/opt/homebrew/bin/lilypond",
            "/usr/local/bin/lilypond",
            "/usr/bin/lilypond",
        ]:
            if Path(candidate).exists():
                return candidate

        raise FileNotFoundError("LilyPond not found. Install with: brew install lilypond")

    def compile(self, source: str, output_dir: Path | None = None) -> RawCompileResult:
        """Compile LilyPond source to PDF.

        Writes source to a temporary file, invokes lilypond with
        --loglevel=ERROR --pdf, and captures output. The temp file
        is cleaned up regardless of outcome.

        Args:
            source: LilyPond source code string.
            output_dir: Optional directory for output files. Defaults to
                the temp file's directory.

        Returns:
            RawCompileResult with success status, return code, and captured output.
        """
        # Write temp file in output_dir (when provided) so \include directives
        # resolve relative to the same directory as music-definitions.ly.
        tmp_kwargs: dict = {"suffix": ".ly", "mode": "w", "delete": False}
        if output_dir is not None:
            tmp_kwargs["dir"] = str(output_dir)
        with tempfile.NamedTemporaryFile(**tmp_kwargs) as f:
            f.write(source)
            input_path = Path(f.name)

        try:
            out_dir = output_dir or input_path.parent
            out_stem = input_path.stem
            cmd = [
                self.binary,
                "--loglevel=ERROR",
                "--pdf",
                "-o",
                str(out_dir / out_stem),
                str(input_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output_pdf = out_dir / f"{out_stem}.pdf"

            return RawCompileResult(
                success=result.returncode == 0 and output_pdf.exists(),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                output_path=output_pdf if output_pdf.exists() else None,
            )
        except subprocess.TimeoutExpired:
            return RawCompileResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"Compilation timed out after {self.timeout} seconds",
                output_path=None,
            )
        finally:
            input_path.unlink(missing_ok=True)
