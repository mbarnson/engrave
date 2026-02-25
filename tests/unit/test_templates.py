"""Unit tests for LilyPond structural templates."""

from __future__ import annotations

import pytest

from engrave.generation.templates import (
    build_instrument_variable,
    build_score_template,
    extract_variable_names,
    parse_instrument_blocks,
    sanitize_var_name,
    strip_variable_wrapper,
)


class TestBuildScoreTemplate:
    """Test score template generation."""

    def test_build_score_template_has_version(self):
        template = build_score_template(
            instrument_names=["Trumpet"],
            section_label="A",
            start_bar=1,
            end_bar=8,
        )
        assert '\\version "2.24.4"' in template

    def test_build_score_template_has_variables(self):
        template = build_score_template(
            instrument_names=["Trumpet", "Alto Sax"],
            section_label="A",
            start_bar=1,
            end_bar=8,
        )
        assert "trumpet" in template.lower()
        assert "altoSax" in template

    def test_build_score_template_has_score_block(self):
        template = build_score_template(
            instrument_names=["Trumpet"],
            section_label="A",
            start_bar=1,
            end_bar=8,
        )
        assert "\\score" in template
        assert "\\new Staff" in template

    def test_build_score_template_section_comment(self):
        template = build_score_template(
            instrument_names=["Trumpet"],
            section_label="Verse",
            start_bar=9,
            end_bar=16,
        )
        assert "Verse" in template
        assert "9" in template
        assert "16" in template


class TestSanitizeVarName:
    """Test instrument name to LilyPond variable name conversion."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("Trumpet", "trumpet"),
            ("Alto Sax 1", "altoSaxOne"),
            ("Trumpet in Bb", "trumpetInBb"),
            ("Piano", "piano"),
            ("Electric Bass", "electricBass"),
            ("Drum Set", "drumSet"),
            ("Drums", "drumsPart"),
        ],
    )
    def test_sanitize_var_name(self, input_name, expected):
        result = sanitize_var_name(input_name)
        assert result == expected


class TestExtractVariableNames:
    """Test parsing variable names from template."""

    def test_extract_variable_names(self):
        template = "trumpet = {\n  \n}\n\naltoSax = {\n  \n}\n\n\\score {\n  <<\n  >>\n}"
        names = extract_variable_names(template)
        assert "trumpet" in names
        assert "altoSax" in names


class TestBuildInstrumentVariable:
    """Test instrument variable formatting."""

    def test_build_instrument_variable(self):
        result = build_instrument_variable("trumpet", "c''4 d'' e'' f''")
        assert "trumpet" in result
        assert "c''4 d'' e'' f''" in result
        assert "{" in result
        assert "}" in result


class TestParseInstrumentBlocks:
    """Test parsing LLM response into instrument blocks."""

    def test_parse_instrument_blocks_extracts_labeled(self):
        llm_response = (
            "% trumpet\nc''4 d'' e'' f''\ng''4 a'' b'' c'''\n\n% altoSax\ne''4 f'' g'' a''\n"
        )
        blocks = parse_instrument_blocks(llm_response)
        assert "trumpet" in blocks
        assert "altoSax" in blocks
        assert "c''4" in blocks["trumpet"]
        assert "e''4" in blocks["altoSax"]

    def test_parse_instrument_blocks_raises_on_empty(self):
        with pytest.raises(ValueError):
            parse_instrument_blocks("")

        with pytest.raises(ValueError):
            parse_instrument_blocks("some random text without markers")

    def test_parse_instrument_blocks_handles_var_eq_brace_format(self):
        """LLM returns varName = { ... } instead of % varName markers."""
        llm_response = "trumpets = {\n  r4 a'8\\ff ais'16 b'8\n}\n"
        blocks = parse_instrument_blocks(llm_response)
        assert "trumpets" in blocks
        assert "r4 a'8" in blocks["trumpets"]


class TestStripVariableWrapper:
    """Test stripping redundant varName = { } wrappers from LLM content."""

    def test_strips_wrapper(self):
        content = "trumpets = {\n  r4 a'8\\ff ais'16 b'8\n}"
        result = strip_variable_wrapper("trumpets", content)
        assert result == "r4 a'8\\ff ais'16 b'8"

    def test_strips_comment_and_wrapper(self):
        content = "% varName: trumpets\n\ntrumpets = {\n  r4 a'8\n}"
        result = strip_variable_wrapper("trumpets", content)
        assert result == "r4 a'8"

    def test_preserves_clean_content(self):
        content = "r4 a'8\\ff ais'16 b'8"
        result = strip_variable_wrapper("trumpets", content)
        assert result == content

    def test_no_double_wrap_after_build(self):
        """Prove the full pipeline path doesn't double-wrap."""
        llm_content = "trumpets = {\n  \\time 4/4\n  r4 a'8\n}"
        stripped = strip_variable_wrapper("trumpets", llm_content)
        built = build_instrument_variable("trumpets", stripped)
        assert built.count("trumpets = {") == 1
