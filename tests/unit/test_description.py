"""Tests for structured text description templating."""

from __future__ import annotations

from engrave.corpus.description import generate_description


class TestGenerateDescription:
    """Tests for generate_description function."""

    def test_produces_structured_text_from_full_metadata(self):
        """generate_description produces structured text from full metadata."""
        metadata = {
            "key_signature": "C major",
            "time_signature": "4/4",
            "tempo": "Allegro",
            "instrument": "Piano",
            "clef": "treble",
            "bar_start": 1,
            "bar_end": 8,
            "note_density": 12.5,
            "dynamic_range": "mf-f",
            "articulation_count": 3,
            "has_chord_symbols": False,
            "composer": "J.S. Bach",
            "era": "Baroque",
            "ensemble_type": "solo",
            "source_collection": "Mutopia",
        }
        desc = generate_description(metadata)
        assert isinstance(desc, str)
        assert len(desc) > 0
        # Should contain all the metadata fields
        assert "C major" in desc
        assert "4/4" in desc
        assert "Allegro" in desc
        assert "Piano" in desc
        assert "treble" in desc
        assert "1-8" in desc or "1" in desc
        assert "12.5" in desc
        assert "mf-f" in desc
        assert "3" in desc
        assert "Bach" in desc
        assert "Baroque" in desc
        assert "solo" in desc
        assert "Mutopia" in desc

    def test_omits_none_fields(self):
        """generate_description omits fields that are None or empty."""
        metadata = {
            "key_signature": "C major",
            "time_signature": None,
            "tempo": None,
            "instrument": None,
            "clef": None,
            "bar_start": 1,
            "bar_end": 4,
            "note_density": None,
            "dynamic_range": None,
            "articulation_count": 0,
            "has_chord_symbols": False,
            "composer": None,
            "era": None,
            "ensemble_type": None,
            "source_collection": "test",
        }
        desc = generate_description(metadata)
        assert "C major" in desc
        assert "Tempo" not in desc
        assert "Instrument" not in desc
        # Bar range should always be present
        assert "1" in desc

    def test_includes_all_required_fields_when_present(self):
        """generate_description includes all required fields per user decision."""
        metadata = {
            "key_signature": "F# minor",
            "time_signature": "3/4",
            "tempo": "Moderato",
            "instrument": "Violin",
            "clef": "treble",
            "bar_start": 9,
            "bar_end": 16,
            "note_density": 8.3,
            "dynamic_range": "p-f",
            "articulation_count": 5,
            "has_chord_symbols": True,
            "composer": "Mozart",
            "era": "Classical",
            "ensemble_type": "chamber",
            "source_collection": "PDMX",
        }
        desc = generate_description(metadata)
        # Check all required fields are represented
        assert "F# minor" in desc
        assert "3/4" in desc
        assert "Moderato" in desc
        assert "Violin" in desc
        assert "treble" in desc
        assert "9" in desc and "16" in desc
        assert "8.3" in desc
        assert "p-f" in desc
        assert "5" in desc
        assert "yes" in desc.lower() or "chord" in desc.lower()
        assert "Mozart" in desc
        assert "Classical" in desc
        assert "chamber" in desc
        assert "PDMX" in desc

    def test_output_is_natural_language(self):
        """generate_description output is natural language suitable for embedding."""
        metadata = {
            "key_signature": "G major",
            "time_signature": "4/4",
            "tempo": "Allegro",
            "instrument": "Flute",
            "clef": "treble",
            "bar_start": 1,
            "bar_end": 8,
            "note_density": 10.0,
            "dynamic_range": "mp-ff",
            "articulation_count": 2,
            "has_chord_symbols": False,
            "composer": "Haydn",
            "era": "Classical",
            "ensemble_type": "orchestra",
            "source_collection": "Mutopia",
        }
        desc = generate_description(metadata)
        # Should be readable sentences, not JSON or code
        assert "{" not in desc
        assert "[" not in desc
        # Should use periods as sentence separators
        assert "." in desc

    def test_chord_symbols_none_when_absent(self):
        """generate_description shows 'none' for chord symbols when absent."""
        metadata = {
            "key_signature": "C major",
            "time_signature": "4/4",
            "tempo": None,
            "instrument": None,
            "clef": None,
            "bar_start": 1,
            "bar_end": 4,
            "note_density": None,
            "dynamic_range": None,
            "articulation_count": 0,
            "has_chord_symbols": False,
            "composer": None,
            "era": None,
            "ensemble_type": None,
            "source_collection": "test",
        }
        desc = generate_description(metadata)
        assert "none" in desc.lower()
