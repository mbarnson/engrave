"""LilyPond stylesheet constants for conductor scores and individual parts.

All constants are raw LilyPond text fragments.  The generator modules
interpolate instrument-specific content around these blocks.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

LILYPOND_VERSION: str = "2.24.0"
"""Target LilyPond stable release (minimum supported)."""

VERSION_HEADER: str = '\\version "2.24.0"\n'
"""Version declaration placed at the top of every generated ``.ly`` file."""

# ---------------------------------------------------------------------------
# Conductor score constants
# ---------------------------------------------------------------------------

CONDUCTOR_SCORE_PAPER: str = """\
\\paper {
  paper-width = 431.8\\mm
  paper-height = 279.4\\mm
  top-margin = 12\\mm
  bottom-margin = 12\\mm
  left-margin = 15\\mm
  right-margin = 10\\mm
  system-system-spacing.basic-distance = #14
  score-system-spacing.basic-distance = #16
}
"""
"""Tabloid landscape paper block for the conductor score.

Uses explicit dimensions (17in x 11in) instead of ``'landscape`` flag
to avoid PDF viewer rotation issues.
"""

CONDUCTOR_SCORE_LAYOUT: str = """\
\\layout {
  #(layout-set-staff-size 14)
  \\context {
    \\Staff
    \\RemoveEmptyStaves
    \\override VerticalAxisGroup.remove-first = ##f
  }
  \\context {
    \\StaffGroup
    \\consists Keep_alive_together_engraver
  }
  \\context {
    \\Score
    \\override BarNumber.break-visibility = ##(#f #f #t)
    barNumberVisibility = #first-bar-number-invisible
  }
}
"""
"""Layout block for the conductor score.

Includes:
- Staff size 14 (compact for 17+ staves).
- ``\\RemoveEmptyStaves`` with first-system exception.
- ``Keep_alive_together_engraver`` so staff groups hide/show as a unit.
- Bar numbers at the start of each system.
"""

CONDUCTOR_SCORE_HEADER: str = """\
\\header {{
  title = "{title}"
  composer = "{composer}"
  arranger = "{arranger}"
  tagline = ##f
}}
"""
"""Header template for the conductor score.

Placeholders: ``{title}``, ``{composer}``, ``{arranger}``.
"""

# ---------------------------------------------------------------------------
# Part constants
# ---------------------------------------------------------------------------

PART_PAPER: str = """\
\\paper {
  #(set-paper-size "letter")
  top-margin = 12\\mm
  bottom-margin = 12\\mm
  left-margin = 15\\mm
  right-margin = 12\\mm
}
"""
"""Letter portrait paper block for individual instrument parts."""

PART_LAYOUT: str = """\
\\layout {
  \\context {
    \\Score
    \\override BarNumber.break-visibility = ##(#f #f #t)
    barNumberVisibility = #first-bar-number-invisible
  }
}
"""
"""Layout block for individual parts.

Bar numbers at the start of each system; first bar number hidden.
"""

PART_HEADER: str = """\
\\header {{
  title = "{title}"
  instrument = "{instrument}"
  tagline = ##f
}}
"""
"""Header template for individual parts.

Placeholders: ``{title}``, ``{instrument}``.
"""

# ---------------------------------------------------------------------------
# Studio mode variant
# ---------------------------------------------------------------------------

STUDIO_LAYOUT: str = """\
\\layout {
  \\context {
    \\Score
    barNumberVisibility = #all-bar-numbers-visible
    \\override BarNumber.break-visibility = ##(#t #t #t)
  }
}
"""
"""Studio-mode layout: bar numbers on every measure.

Used for recording sessions where sequential bar counting replaces
rehearsal-letter navigation.
"""

# ---------------------------------------------------------------------------
# Global staff size presets
# ---------------------------------------------------------------------------

CONDUCTOR_STAFF_SIZE: int = 14
"""Staff size for the conductor score (default LilyPond is 20)."""

PART_STAFF_SIZE: int = 20
"""Staff size for individual parts (LilyPond default)."""
