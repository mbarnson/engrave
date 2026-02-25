"""Tests for individual part LilyPond generation.

Covers: generate_part from engrave.rendering.generator.
"""

from __future__ import annotations

from engrave.rendering.ensemble import BIG_BAND, InstrumentSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instrument(name: str) -> InstrumentSpec:
    """Look up an instrument by full name from BIG_BAND."""
    for inst in BIG_BAND.instruments:
        if inst.name == name:
            return inst
    raise ValueError(f"Instrument not found: {name}")


def _generate_part_for(name: str, **kwargs) -> str:
    """Generate a part .ly string for the named instrument."""
    from engrave.rendering.generator import generate_part

    inst = _instrument(name)
    # Default has_chords based on instrument spec unless overridden
    if "has_chords" not in kwargs:
        kwargs["has_chords"] = inst.has_chord_symbols
    return generate_part(instrument=inst, **kwargs)


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


class TestPartStructure:
    """Tests for the basic structure of generated part .ly files."""

    def test_part_includes_shared_definitions(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert '\\include "music-definitions.ly"' in output

    def test_part_uses_letter_portrait(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert 'set-paper-size "letter"' in output

    def test_part_has_book_output_name(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert '\\bookOutputName "part-trumpet-1"' in output

    def test_part_has_book_output_name_slug(self) -> None:
        output = _generate_part_for("Alto Sax 1")
        assert '\\bookOutputName "part-alto-sax-1"' in output

    def test_part_has_instrument_name(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert 'instrumentName = "Trumpet 1"' in output

    def test_part_has_short_instrument_name(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert 'shortInstrumentName = "Tpt. 1"' in output

    def test_part_has_compress_mm_rests(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert "\\compressMMRests" in output

    def test_part_global_music_parallel(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert "\\globalMusic" in output
        # globalMusic and instrument music should be in parallel << >>
        assert "<<" in output
        assert ">>" in output

    def test_part_has_rehearsal_infrastructure(self) -> None:
        output = _generate_part_for("Trumpet 1")
        # Measure number visibility at system start
        assert "BarNumber" in output


# ---------------------------------------------------------------------------
# Transposition tests
# ---------------------------------------------------------------------------


class TestPartTransposition:
    """Tests for correct transposition in parts."""

    def test_part_applies_transpose(self) -> None:
        output = _generate_part_for("Trumpet 1")
        assert "\\transpose c' d'" in output

    def test_part_alto_sax_transpose(self) -> None:
        output = _generate_part_for("Alto Sax 1")
        assert "\\transpose c' a'" in output

    def test_part_bari_sax_octave_transpose(self) -> None:
        output = _generate_part_for("Baritone Sax")
        # Bari sax: Eb, octave below alto -- transpose_to is 'a' (no tick)
        assert "\\transpose c' a" in output
        # Ensure it's 'a' without the octave tick (not a')
        # The string "\\transpose c' a " or "\\transpose c' a\n" must exist
        # but NOT "\\transpose c' a'" (which would be alto)
        import re

        match = re.search(r"\\transpose c' a(?!')", output)
        assert match is not None, "Bari sax should transpose to 'a' not 'a\\'' "

    def test_part_trombone_no_transpose(self) -> None:
        output = _generate_part_for("Trombone 1")
        # Trombone is C instrument: no transpose wrapper, or transpose c' c'
        # Either "no \\transpose" or "\\transpose c' c'"
        if "\\transpose" in output:
            assert "\\transpose c' c'" in output
        # But it MUST NOT have a different transpose
        assert "\\transpose c' d'" not in output

    def test_part_tenor_sax_transpose(self) -> None:
        output = _generate_part_for("Tenor Sax 1")
        assert "\\transpose c' d'" in output


# ---------------------------------------------------------------------------
# Chord symbols tests
# ---------------------------------------------------------------------------


class TestPartChordSymbols:
    """Tests for chord symbol inclusion on rhythm section parts."""

    def test_chord_symbols_on_guitar(self) -> None:
        output = _generate_part_for("Guitar", has_chords=True)
        assert "\\new ChordNames" in output

    def test_chord_symbols_on_piano(self) -> None:
        output = _generate_part_for("Piano", has_chords=True)
        assert "\\new ChordNames" in output

    def test_chord_symbols_on_bass(self) -> None:
        output = _generate_part_for("Bass", has_chords=True)
        assert "\\new ChordNames" in output

    def test_no_chord_symbols_on_trumpet(self) -> None:
        output = _generate_part_for("Trumpet 1", has_chords=False)
        assert "\\new ChordNames" not in output

    def test_no_chord_symbols_on_alto_sax(self) -> None:
        output = _generate_part_for("Alto Sax 1", has_chords=False)
        assert "\\new ChordNames" not in output

    def test_no_chord_symbols_when_has_chords_false(self) -> None:
        # Even for a rhythm instrument, if has_chords=False, no chords
        output = _generate_part_for("Guitar", has_chords=False)
        assert "\\new ChordNames" not in output


# ---------------------------------------------------------------------------
# Special instruments
# ---------------------------------------------------------------------------


class TestPartSpecialInstruments:
    """Tests for special instrument handling (piano, drums)."""

    def test_piano_part_has_grand_staff(self) -> None:
        output = _generate_part_for("Piano", has_chords=True)
        assert "PianoStaff" in output

    def test_drums_part_has_drum_staff(self) -> None:
        output = _generate_part_for("Drums")
        assert "DrumStaff" in output

    def test_drums_part_percussion_clef(self) -> None:
        output = _generate_part_for("Drums")
        # Drums use percussion clef -- no treble/bass clef override
        # DrumStaff implies percussion clef automatically
        assert "DrumStaff" in output


# ---------------------------------------------------------------------------
# Studio mode
# ---------------------------------------------------------------------------


class TestPartStudioMode:
    """Tests for studio mode layout variant."""

    def test_studio_mode_all_bar_numbers(self) -> None:
        output = _generate_part_for("Trumpet 1", studio_mode=True)
        assert "all-bar-numbers-visible" in output

    def test_normal_mode_no_all_bar_numbers(self) -> None:
        output = _generate_part_for("Trumpet 1", studio_mode=False)
        assert "all-bar-numbers-visible" not in output
