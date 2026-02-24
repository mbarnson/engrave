"""Tests for LilyPond subprocess compiler wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.lilypond.compiler import LilyPondCompiler, RawCompileResult


class TestCompileSuccess:
    def test_compile_success(self, tmp_path: Path) -> None:
        """Mock subprocess.run returning returncode=0 and a PDF file."""
        with (
            patch.object(LilyPondCompiler, "_find_binary", return_value="/usr/bin/lilypond"),
            patch("engrave.lilypond.compiler.subprocess.run") as mock_run,
            patch("engrave.lilypond.compiler.Path.exists", return_value=True),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            compiler = LilyPondCompiler(timeout=30)
            result = compiler.compile(
                '\\version "2.24.4"\n\\relative c\' { c4 }', output_dir=tmp_path
            )
            assert isinstance(result, RawCompileResult)
            assert result.success is True
            assert result.returncode == 0


class TestCompileFailure:
    def test_compile_failure(self, tmp_path: Path) -> None:
        """Mock subprocess.run returning returncode=1."""
        with (
            patch.object(LilyPondCompiler, "_find_binary", return_value="/usr/bin/lilypond"),
            patch("engrave.lilypond.compiler.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="/tmp/test.ly:2:1: error: unmatched '{'",
            )
            compiler = LilyPondCompiler(timeout=30)
            result = compiler.compile("broken source", output_dir=tmp_path)
            assert result.success is False
            assert result.stderr == "/tmp/test.ly:2:1: error: unmatched '{'"


class TestFindBinary:
    def test_find_binary_uses_shutil_which(self) -> None:
        """Mock shutil.which to return a path."""
        with patch(
            "engrave.lilypond.compiler.shutil.which", return_value="/usr/local/bin/lilypond"
        ):
            compiler = LilyPondCompiler.__new__(LilyPondCompiler)
            binary = compiler._find_binary()
            assert binary == "/usr/local/bin/lilypond"

    def test_find_binary_fallback_paths(self) -> None:
        """Mock shutil.which returning None, mock Path.exists for /opt/homebrew/bin/lilypond."""
        with (
            patch("engrave.lilypond.compiler.shutil.which", return_value=None),
            patch("engrave.lilypond.compiler.Path.exists") as mock_exists,
        ):
            # First candidate (/opt/homebrew/bin/lilypond) exists
            mock_exists.return_value = True
            compiler = LilyPondCompiler.__new__(LilyPondCompiler)
            binary = compiler._find_binary()
            assert binary == "/opt/homebrew/bin/lilypond"

    def test_find_binary_not_found(self) -> None:
        """Mock everything returning None/False."""
        with (
            patch("engrave.lilypond.compiler.shutil.which", return_value=None),
            patch("engrave.lilypond.compiler.Path.exists", return_value=False),
        ):
            compiler = LilyPondCompiler.__new__(LilyPondCompiler)
            with pytest.raises(FileNotFoundError, match="LilyPond not found"):
                compiler._find_binary()


class TestCompileTimeout:
    def test_compile_timeout(self, tmp_path: Path) -> None:
        """Mock subprocess.run raising TimeoutExpired."""
        with (
            patch.object(LilyPondCompiler, "_find_binary", return_value="/usr/bin/lilypond"),
            patch("engrave.lilypond.compiler.subprocess.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["lilypond"], timeout=30)
            compiler = LilyPondCompiler(timeout=30)
            result = compiler.compile('\\version "2.24.4"\n{ c4 }', output_dir=tmp_path)
            assert result.success is False
            assert "timed out" in result.stderr.lower()
