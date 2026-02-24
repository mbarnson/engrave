"""Tests for LilyPond error output parser."""

from __future__ import annotations

from pathlib import Path

from engrave.lilypond.parser import parse_lilypond_errors

FIXTURES = Path(__file__).parent.parent / "fixtures" / "error_outputs"


class TestParseSingleError:
    def test_parse_single_error(self) -> None:
        stderr = "/tmp/input.ly:3:5: error: unexpected end of input\n  c4 d e f\n"
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 1
        err = errors[0]
        assert err.file == "/tmp/input.ly"
        assert err.line == 3
        assert err.column == 5
        assert err.severity == "error"
        assert err.message == "unexpected end of input"

    def test_parse_captures_offending_line(self) -> None:
        stderr = "/tmp/input.ly:3:5: error: unexpected end of input\n  c4 d e f\n"
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 1
        assert errors[0].offending_line == "c4 d e f"


class TestParseMultipleErrors:
    def test_parse_multiple_errors(self) -> None:
        stderr = (
            "/tmp/input.ly:3:1: error: unmatched '{'\n"
            "{\n"
            "/tmp/input.ly:5:10: error: syntax error\n"
            "  bad line\n"
        )
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 2
        assert errors[0].line == 3
        assert errors[1].line == 5


class TestParseWarningsAndErrors:
    def test_parse_warnings_and_errors(self) -> None:
        stderr = (
            "/tmp/input.ly:2:1: warning: bar check failed\n"
            "  | c4 d e\n"
            "/tmp/input.ly:4:1: error: unmatched '{'\n"
            "{\n"
        )
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 2
        assert errors[0].severity == "warning"
        assert errors[1].severity == "error"


class TestParseFatalError:
    def test_parse_fatal_error(self) -> None:
        stderr = "/tmp/input.ly:1:1: fatal error: cannot read file\n"
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 1
        assert errors[0].severity == "fatal error"
        assert errors[0].message == "cannot read file"


class TestParseNoErrors:
    def test_parse_no_errors(self) -> None:
        stderr = "Processing `/tmp/input.ly'\nConverting to PDF...\n"
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 0


class TestParseFromFixtures:
    def test_parse_missing_brace_fixture(self) -> None:
        stderr = FIXTURES.joinpath("missing_brace.txt").read_text()
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 1
        assert errors[0].message == "unmatched '{'"
        assert errors[0].severity == "error"

    def test_parse_unknown_command_fixture(self) -> None:
        stderr = FIXTURES.joinpath("unknown_command.txt").read_text()
        errors = parse_lilypond_errors(stderr)
        assert len(errors) == 1
        assert "unknown escaped string" in errors[0].message
