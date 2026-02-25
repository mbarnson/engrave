"""Tests for LilyPond structural boundary detection."""

from __future__ import annotations

from engrave.corpus.chunker import find_phrase_boundaries


class TestFindPhraseBoundaries:
    """Tests for find_phrase_boundaries function."""

    def test_detects_rehearsal_mark_default(self):
        """find_phrase_boundaries detects \\mark \\default rehearsal marks."""
        source = r"""c'4 d' e' f' | g'2 g'2 |
\mark \default
a'4 b' c'' d'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        # The boundary should be at the position of \mark
        mark_pos = source.index(r"\mark \default")
        assert mark_pos in boundaries

    def test_detects_numbered_rehearsal_mark(self):
        """find_phrase_boundaries detects \\mark N numbered rehearsal marks."""
        source = r"""c'4 d' e' f' | g'2 g'2 |
\mark 3
a'4 b' c'' d'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        mark_pos = source.index(r"\mark 3")
        assert mark_pos in boundaries

    def test_detects_double_barlines(self):
        r"""find_phrase_boundaries detects double barlines (\bar "||")."""
        source = r"""c'4 d' e' f' |
\bar "||"
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        bar_pos = source.index(r'\bar "||"')
        assert bar_pos in boundaries

    def test_detects_key_changes(self):
        r"""find_phrase_boundaries detects key changes (\key X \major/\minor)."""
        source = r"""c'4 d' e' f' | g'2 g'2 |
\key g \major
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        key_pos = source.index(r"\key g \major")
        assert key_pos in boundaries

    def test_detects_key_change_minor(self):
        r"""find_phrase_boundaries detects minor key changes."""
        source = r"""c'4 d' e' f' |
\key a \minor
a'4 b' c'' d'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        key_pos = source.index(r"\key a \minor")
        assert key_pos in boundaries

    def test_detects_time_signature_changes(self):
        r"""find_phrase_boundaries detects time signature changes (\time N/N)."""
        source = r"""c'4 d' e' f' | g'2 g'2 |
\time 3/4
c'4 d' e' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        time_pos = source.index(r"\time 3/4")
        assert time_pos in boundaries

    def test_detects_repeat_volta(self):
        r"""find_phrase_boundaries detects \\repeat volta structures."""
        source = r"""c'4 d' e' f' |
\repeat volta 2 {
  g'4 a' b' c'' |
}"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        repeat_pos = source.index(r"\repeat volta")
        assert repeat_pos in boundaries

    def test_detects_repeat_segno(self):
        r"""find_phrase_boundaries detects \\repeat segno structures."""
        source = r"""c'4 d' e' f' |
\repeat segno 2 {
  g'4 a' b' c'' |
}"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        repeat_pos = source.index(r"\repeat segno")
        assert repeat_pos in boundaries

    def test_detects_section_division(self):
        r"""find_phrase_boundaries detects \\section markers."""
        source = r"""c'4 d' e' f' |
\section
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        section_pos = source.index(r"\section")
        assert section_pos in boundaries

    def test_detects_fine(self):
        r"""find_phrase_boundaries detects \\fine markers."""
        source = r"""c'4 d' e' f' |
\fine
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        fine_pos = source.index(r"\fine")
        assert fine_pos in boundaries

    def test_detects_segno_mark(self):
        r"""find_phrase_boundaries detects \\segnoMark markers."""
        source = r"""c'4 d' e' f' |
\segnoMark
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        segno_pos = source.index(r"\segnoMark")
        assert segno_pos in boundaries

    def test_detects_coda_mark(self):
        r"""find_phrase_boundaries detects \\codaMark markers."""
        source = r"""c'4 d' e' f' |
\codaMark
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) >= 1
        coda_pos = source.index(r"\codaMark")
        assert coda_pos in boundaries

    def test_returns_sorted_positions(self):
        """find_phrase_boundaries returns sorted positions."""
        source = r"""\key g \major
c'4 d' e' f' |
\mark \default
g'4 a' b' c'' |
\time 3/4
c'4 d' e' |"""
        boundaries = find_phrase_boundaries(source)
        assert boundaries == sorted(boundaries)

    def test_returns_deduplicated_positions(self):
        """find_phrase_boundaries returns deduplicated positions (no duplicates)."""
        source = r"""c'4 d' e' f' |
\mark \default
g'4 a' b' c'' |"""
        boundaries = find_phrase_boundaries(source)
        assert len(boundaries) == len(set(boundaries))

    def test_empty_source_returns_empty(self):
        """find_phrase_boundaries on empty source returns empty list."""
        boundaries = find_phrase_boundaries("")
        assert boundaries == []

    def test_no_boundaries_returns_empty(self):
        """find_phrase_boundaries returns empty when no structural cues exist."""
        source = "c'4 d' e' f' | g'2 g'2 | a'4 b' c'' d'' | e''2. r4 |"
        boundaries = find_phrase_boundaries(source)
        assert boundaries == []
