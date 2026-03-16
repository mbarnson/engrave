"""Unit tests for concert pitch constraints in generated templates."""

from __future__ import annotations

from engrave.generation.templates import build_score_template


class TestConcertPitchConstraints:
    """Verify absolute pitch and concert pitch conventions."""

    def test_template_has_no_relative(self):
        template = build_score_template(
            instrument_names=["Trumpet", "Alto Sax", "Piano"],
            section_label="A",
            start_bar=1,
            end_bar=8,
        )
        assert "\\relative" not in template

    def test_template_has_no_transpose(self):
        template = build_score_template(
            instrument_names=["Trumpet in Bb", "Alto Sax", "Tenor Sax"],
            section_label="B",
            start_bar=9,
            end_bar=16,
        )
        assert "\\transpose" not in template

    def test_template_uses_absolute_pitch(self):
        """Verify that the template structure supports absolute pitch mode.

        In absolute pitch mode, there is no \\relative or \\transpose. Each
        note must have explicit octave marks. The template should contain
        variable declarations that the LLM fills with absolute pitch content.
        """
        template = build_score_template(
            instrument_names=["Trumpet"],
            section_label="A",
            start_bar=1,
            end_bar=8,
        )
        # No relative mode
        assert "\\relative" not in template
        # No transposition
        assert "\\transpose" not in template
        # Has version header (indicates complete template)
        assert '\\version "2.24.0"' in template
        # Has variable declaration pattern (name = { })
        assert "= {" in template
