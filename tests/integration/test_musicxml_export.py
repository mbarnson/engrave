"""Integration test: end-to-end MusicXML export from programmatic JSON input.

Validates that ``assemble_musicxml()`` produces valid MusicXML from
realistic, programmatically-constructed JSON notation events covering
two big-band instruments across two sections with four measures each.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar

from engrave.generation.json_assembler import assemble_musicxml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_json_sections(
    instruments: list[str],
    sections: int = 2,
    measures_per_section: int = 4,
) -> list[list[dict]]:
    """Build programmatic JSON notation events for integration testing.

    Creates realistic musical content: pitched notes, rests, dynamics,
    articulations, and expressions across multiple instruments and sections.

    Returns a list of sections, each containing a list of instrument dicts.
    """
    all_sections: list[list[dict]] = []

    # Pitches and dynamics per instrument
    instrument_data = {
        "trumpet_1": {
            "pitches": ["bf4", "d5", "f5", "bf5"],
            "dynamics": ["f", None, None, "ff"],
            "articulations": [["accent"], None, ["staccato"], None],
        },
        "alto_sax": {
            "pitches": ["c4", "ef4", "g4", "c5"],
            "dynamics": ["mf", None, None, "f"],
            "articulations": [None, ["tenuto"], None, ["accent", "staccato"]],
        },
    }

    for sec_idx in range(sections):
        section_instruments: list[dict] = []

        for inst_ident in instruments:
            data = instrument_data.get(inst_ident, instrument_data["trumpet_1"])
            measures = []
            for m_idx in range(measures_per_section):
                measure_num = sec_idx * measures_per_section + m_idx + 1
                pitches = data["pitches"]
                notes = []

                for beat_idx in range(4):
                    pitch = pitches[beat_idx % len(pitches)]
                    note: dict = {
                        "pitch": pitch,
                        "beat": float(beat_idx + 1),
                        "duration": 1.0,
                    }
                    dyn = data["dynamics"][beat_idx % len(data["dynamics"])]
                    if dyn and m_idx == 0:
                        note["dynamic"] = dyn
                    arts = data["articulations"][beat_idx % len(data["articulations"])]
                    if arts:
                        note["articulations"] = arts
                    notes.append(note)

                # Add a rest in even-numbered measures (third beat)
                if measure_num % 2 == 0:
                    notes[2] = {
                        "type": "rest",
                        "beat": 3.0,
                        "duration": 1.0,
                    }

                measures.append({"number": measure_num, "notes": notes})

            section_instruments.append(
                {
                    "instrument": inst_ident,
                    "key": "bf_major",
                    "time_signature": "4/4",
                    "measures": measures,
                }
            )

        all_sections.append(section_instruments)

    return all_sections


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMusicXMLExport:
    """End-to-end MusicXML export from programmatic JSON."""

    INSTRUMENTS: ClassVar[list[str]] = ["trumpet_1", "alto_sax"]

    def test_export_produces_valid_xml(self, tmp_path: Path) -> None:
        """assemble_musicxml writes a valid XML file from programmatic JSON."""
        json_sections = _build_json_sections(self.INSTRUMENTS)
        output_path = tmp_path / "score.musicxml"

        success, result_path = assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=140,
            output_path=output_path,
        )

        assert success is True
        assert result_path is not None
        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # Parse as XML to verify well-formedness
        tree = ET.parse(str(result_path))
        root = tree.getroot()
        assert root is not None

    def test_export_correct_part_count(self, tmp_path: Path) -> None:
        """Output MusicXML contains one <part> per instrument."""
        json_sections = _build_json_sections(self.INSTRUMENTS)
        output_path = tmp_path / "score.musicxml"

        assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=140,
            output_path=output_path,
        )

        tree = ET.parse(str(output_path))
        root = tree.getroot()
        # MusicXML uses a namespace; find parts with or without namespace
        ns = {"": root.tag.split("}")[0].strip("{") if "}" in root.tag else ""}
        parts = root.findall(f".//{{{ns['']}}}part" if ns[""] else ".//part")
        assert len(parts) == 2

    def test_export_with_big_band_instruments(self, tmp_path: Path) -> None:
        """Export works with big band instrument names (Engrave's primary use case)."""
        instruments = ["trumpet_1", "alto_sax"]
        json_sections = _build_json_sections(instruments, sections=1, measures_per_section=2)
        output_path = tmp_path / "score.musicxml"

        success, result_path = assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=output_path,
        )

        assert success is True
        # Read the file and verify instrument names appear in part-list
        content = result_path.read_text()
        assert "Trumpet 1" in content or "trumpet" in content.lower()
        assert "Alto Sax" in content or "alto" in content.lower()

    def test_export_creates_parent_directory(self, tmp_path: Path) -> None:
        """assemble_musicxml creates parent directories as needed."""
        json_sections = _build_json_sections(self.INSTRUMENTS, sections=1, measures_per_section=2)
        output_path = tmp_path / "nested" / "deep" / "score.musicxml"

        success, result_path = assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=120,
            output_path=output_path,
        )

        assert success is True
        assert result_path.exists()

    def test_export_multiple_sections_all_measures_present(self, tmp_path: Path) -> None:
        """Two sections with 4 measures each produces 8 measures per part in output."""
        json_sections = _build_json_sections(self.INSTRUMENTS, sections=2, measures_per_section=4)
        output_path = tmp_path / "score.musicxml"

        assemble_musicxml(
            json_sections=json_sections,
            instrument_names=["Trumpet 1", "Alto Sax"],
            key_sig="bf_major",
            time_sig="4/4",
            tempo_bpm=140,
            output_path=output_path,
        )

        tree = ET.parse(str(output_path))
        root = tree.getroot()
        ns = {"": root.tag.split("}")[0].strip("{") if "}" in root.tag else ""}
        tag_prefix = f"{{{ns['']}}}" if ns[""] else ""

        parts = root.findall(f".//{tag_prefix}part")
        for part in parts:
            measures = part.findall(f"{tag_prefix}measure")
            assert len(measures) >= 8, f"Expected at least 8 measures, got {len(measures)}"
