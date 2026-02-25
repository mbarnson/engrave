"""Tests for LilyPond metadata extraction."""

from __future__ import annotations

from engrave.corpus.metadata import extract_metadata


class TestExtractMetadataKeySignature:
    """Tests for key signature extraction."""

    def test_finds_key_c_major(self):
        r"""extract_metadata finds key signature (\key c \major -> "C major")."""
        fragment = r"\key c \major c'4 d' e' f' | g'2 g'2 |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=2)
        assert meta["key_signature"] == "C major"

    def test_finds_key_fis_minor(self):
        r"""extract_metadata finds sharped key (\key fis \minor -> "F# minor")."""
        fragment = r"\key fis \minor fis'4 gis' a' b' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["key_signature"] == "F# minor"

    def test_finds_key_bes_major(self):
        r"""extract_metadata finds flatted key (\key bes \major -> "Bb major")."""
        fragment = r"\key bes \major bes'4 c'' d'' ees'' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["key_signature"] == "Bb major"


class TestExtractMetadataTimeSignature:
    """Tests for time signature extraction."""

    def test_finds_time_4_4(self):
        r"""extract_metadata finds time signature (\time 4/4 -> "4/4")."""
        fragment = r"\time 4/4 c'4 d' e' f' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["time_signature"] == "4/4"

    def test_finds_time_3_4(self):
        r"""extract_metadata finds 3/4 time."""
        fragment = r"\time 3/4 c'4 d' e' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["time_signature"] == "3/4"

    def test_finds_time_6_8(self):
        r"""extract_metadata finds 6/8 time."""
        fragment = r"\time 6/8 c'8 d' e' f' g' a' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["time_signature"] == "6/8"


class TestExtractMetadataTempo:
    """Tests for tempo marking extraction."""

    def test_finds_tempo_with_string_and_metronome(self):
        r"""extract_metadata finds tempo (\tempo "Allegro" 4 = 120 -> "Allegro")."""
        fragment = r'\tempo "Allegro" 4 = 120 c\'4 d\' e\' f\' |'
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["tempo"] == "Allegro"

    def test_finds_tempo_string_only(self):
        r"""extract_metadata finds tempo with string only."""
        fragment = r'\tempo "Andante" c\'4 d\' e\' f\' |'
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["tempo"] == "Andante"

    def test_finds_tempo_metronome_only(self):
        r"""extract_metadata finds tempo with metronome mark only."""
        fragment = r"\tempo 4 = 96 c'4 d' e' f' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["tempo"] is not None
        assert "96" in meta["tempo"]


class TestExtractMetadataInstrument:
    """Tests for instrument name extraction."""

    def test_finds_instrument_from_header(self):
        """extract_metadata finds instrument from header_metadata."""
        fragment = "c'4 d' e' f' |"
        meta = extract_metadata(
            fragment,
            bar_start=1,
            bar_end=1,
            header_metadata={"mutopiainstrument": "Piano"},
        )
        assert meta["instrument"] == "Piano"

    def test_finds_instrument_from_set_command(self):
        r"""extract_metadata finds instrument from \set Staff.instrumentName."""
        fragment = r"""
\set Staff.instrumentName = "Violin"
c'4 d' e' f' |"""
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["instrument"] == "Violin"

    def test_finds_instrument_from_instrument_name_equals(self):
        """extract_metadata finds instrument from instrumentName = in header."""
        fragment = r"""
instrumentName = "Trumpet"
c'4 d' e' f' |"""
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["instrument"] == "Trumpet"


class TestExtractMetadataClef:
    """Tests for clef extraction."""

    def test_finds_clef_treble(self):
        r"""extract_metadata finds clef (\clef treble -> "treble")."""
        fragment = r"\clef treble c'4 d' e' f' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["clef"] == "treble"

    def test_finds_clef_bass(self):
        r"""extract_metadata finds clef (\clef bass -> "bass")."""
        fragment = r"\clef bass c4 d e f |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["clef"] == "bass"


class TestExtractMetadataNoteDensity:
    """Tests for note density calculation."""

    def test_counts_notes_per_bar(self):
        """extract_metadata counts notes per bar (note density)."""
        # 2 bars, 8 notes total -> 4 notes/bar
        fragment = "c'4 d' e' f' | g'4 a' b' c'' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=2)
        assert meta["note_density"] is not None
        assert 3.0 <= meta["note_density"] <= 5.0  # ~4 notes/bar


class TestExtractMetadataArticulations:
    """Tests for articulation count extraction."""

    def test_counts_articulation_marks(self):
        """extract_metadata counts articulation marks (accents, staccato, tenuto, marcato)."""
        fragment = r"c'4-> d'-. e'-- f'-^ | g'4\accent a'\staccato b'\tenuto c''\marcato |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=2)
        assert meta["articulation_count"] >= 8


class TestExtractMetadataChordSymbols:
    """Tests for chord symbol detection."""

    def test_detects_chordmode(self):
        r"""extract_metadata detects chord symbols with \chordmode."""
        fragment = r"\chordmode { c1 f g c }"
        meta = extract_metadata(fragment, bar_start=1, bar_end=4)
        assert meta["has_chord_symbols"] is True

    def test_detects_chords(self):
        r"""extract_metadata detects chord symbols with \chords."""
        fragment = r"\chords { c1 f g c }"
        meta = extract_metadata(fragment, bar_start=1, bar_end=4)
        assert meta["has_chord_symbols"] is True

    def test_no_chord_symbols(self):
        """extract_metadata returns False when no chord symbols present."""
        fragment = "c'4 d' e' f' | g'2 g'2 |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=2)
        assert meta["has_chord_symbols"] is False


class TestExtractMetadataDynamicRange:
    """Tests for dynamic range extraction."""

    def test_determines_dynamic_range(self):
        """extract_metadata determines dynamic range from dynamic markings (pp, p, mf, f, ff)."""
        fragment = r"c'4\pp d' e' f' | g'4\ff a' b' c'' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=2)
        assert meta["dynamic_range"] is not None
        assert "pp" in meta["dynamic_range"]
        assert "ff" in meta["dynamic_range"]

    def test_single_dynamic(self):
        """extract_metadata with a single dynamic shows it as both min and max."""
        fragment = r"c'4\mf d' e' f' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["dynamic_range"] == "mf"


class TestExtractMetadataMissingFields:
    """Tests for graceful handling of missing metadata."""

    def test_handles_missing_fields(self):
        """extract_metadata handles missing fields gracefully (returns None for absent values)."""
        fragment = "c'4 d' e' f' |"
        meta = extract_metadata(fragment, bar_start=1, bar_end=1)
        assert meta["key_signature"] is None
        assert meta["time_signature"] is None
        assert meta["tempo"] is None
        assert meta["instrument"] is None
        assert meta["clef"] is None
        assert meta["dynamic_range"] is None

    def test_bar_range_always_present(self):
        """extract_metadata always includes bar_start and bar_end."""
        fragment = "c'4 d' e' f' |"
        meta = extract_metadata(fragment, bar_start=5, bar_end=8)
        assert meta["bar_start"] == 5
        assert meta["bar_end"] == 8
