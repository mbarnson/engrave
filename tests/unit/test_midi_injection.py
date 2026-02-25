"""Unit tests for MIDI block injection into LilyPond source."""

from __future__ import annotations

import logging

from engrave.corpus.ingest.midi_injection import ensure_midi_block


class TestEnsureMidiBlock:
    """Tests for ensure_midi_block()."""

    def test_source_with_existing_midi_unchanged(self):
        """Source that already has \\midi { } is returned unchanged."""
        source = r"""
\score {
  \new Staff { c'4 d' e' f' | }
  \layout { }
  \midi { }
}
"""
        result = ensure_midi_block(source)
        assert result == source

    def test_midi_inserted_after_layout(self):
        r"""Source with \layout { } gets \midi { } inserted after it."""
        source = r"""
\score {
  \new Staff { c'4 d' e' f' | }
  \layout { }
}
"""
        result = ensure_midi_block(source)
        assert r"\midi { }" in result
        # \midi should appear after \layout
        layout_pos = result.index(r"\layout")
        midi_pos = result.index(r"\midi")
        assert midi_pos > layout_pos

    def test_midi_injected_into_score_without_layout(self):
        r"""Source with \score { } but no \layout gets \midi { } injected."""
        source = r"""
\score {
  \new Staff { c'4 d' e' f' | }
}
"""
        result = ensure_midi_block(source)
        assert r"\midi { }" in result
        # \midi should be inside \score
        assert r"\score" in result

    def test_source_without_score_unchanged_with_warning(self, caplog):
        r"""Source with no \score { } is returned unchanged with a warning."""
        source = r"""
\new Staff { c'4 d' e' f' | }
"""
        with caplog.at_level(logging.WARNING):
            result = ensure_midi_block(source)
        assert result == source
        assert "Could not inject" in caplog.text

    def test_layout_with_content_handled(self):
        r"""Source with non-empty \layout block gets \midi inserted after it."""
        source = r"""
\score {
  \new Staff { c'4 d' e' f' | }
  \layout {
    \context {
      \Score
      \override SpacingSpanner.base-shortest-duration = #(ly:make-moment 1/16)
    }
  }
}
"""
        result = ensure_midi_block(source)
        assert r"\midi { }" in result
        # Should still have the layout content intact
        assert "SpacingSpanner" in result

    def test_existing_midi_with_content_unchanged(self):
        """Source with \\midi { \\tempo 4 = 120 } is returned unchanged."""
        source = r"""
\score {
  \new Staff { c'4 d' e' f' | }
  \layout { }
  \midi { \tempo 4 = 120 }
}
"""
        result = ensure_midi_block(source)
        assert result == source
