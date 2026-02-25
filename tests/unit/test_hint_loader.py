"""Tests for hint loading with inline text vs file path auto-detection."""

from __future__ import annotations

from pathlib import Path

from engrave.hints.loader import load_hints


class TestLoadHints:
    """Tests for the load_hints function."""

    def test_load_hints_none_returns_empty(self):
        """load_hints(None) returns empty string."""
        assert load_hints(None) == ""

    def test_load_hints_inline_text(self):
        """Inline text is returned stripped."""
        result = load_hints("swing feel, shout chorus at bar 33")
        assert result == "swing feel, shout chorus at bar 33"

    def test_load_hints_file_path(self, tmp_path: Path):
        """A path to an existing file reads and returns file content."""
        hint_file = tmp_path / "hints.txt"
        hint_file.write_text("swing feel\nshout chorus at bar 33\n", encoding="utf-8")
        result = load_hints(str(hint_file))
        assert result == "swing feel\nshout chorus at bar 33"

    def test_load_hints_nonexistent_path_treated_as_inline(self):
        """A string that looks like a path but doesn't exist is treated as inline text."""
        result = load_hints("/nonexistent/path.txt")
        assert result == "/nonexistent/path.txt"

    def test_load_hints_strips_whitespace(self):
        """Inline text with surrounding whitespace is stripped."""
        result = load_hints("  hints with spaces  ")
        assert result == "hints with spaces"

    def test_load_hints_file_strips_whitespace(self, tmp_path: Path):
        """File content with trailing newlines is stripped."""
        hint_file = tmp_path / "hints_ws.txt"
        hint_file.write_text("  hints from file  \n\n", encoding="utf-8")
        result = load_hints(str(hint_file))
        assert result == "hints from file"
