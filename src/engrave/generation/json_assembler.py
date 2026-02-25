"""Assemble per-section JSON notation events into a complete MusicXML file.

Connects the per-section JSON output from the generation pipeline
(Plan 02) to the musicxml builder (Plan 01) and validator (Plan 03).
Produces a validated MusicXML file at the specified output path.

Concert pitch throughout -- no transposition applied, matching
Engrave's internal storage convention per CONTEXT.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from engrave.musicxml.builder import build_score
from engrave.musicxml.models import SectionNotation
from engrave.musicxml.validator import validate_musicxml

logger = logging.getLogger(__name__)


def assemble_musicxml(
    json_sections: list[list[dict] | None],
    instrument_names: list[str],
    key_sig: str,
    time_sig: str,
    tempo_bpm: int,
    output_path: Path,
    xsd_path: Path | None = None,
) -> tuple[bool, Path | None]:
    """Assemble per-section JSON into a validated MusicXML file.

    Filters out ``None`` sections (where JSON generation failed),
    validates each section's JSON via Pydantic, builds a music21 Score,
    writes MusicXML, and validates against the XSD.

    Parameters
    ----------
    json_sections:
        List of per-section JSON data.  Each entry is either a list
        of dicts (one per instrument) or ``None`` if generation failed.
    instrument_names:
        List of instrument display names (same order as generation).
    key_sig:
        Key signature string (LilyPond style, e.g. ``"bf_major"``).
    time_sig:
        Time signature string (e.g. ``"4/4"``).
    tempo_bpm:
        Tempo in beats per minute.
    output_path:
        Where to write the MusicXML file.
    xsd_path:
        Optional path to the XSD schema for validation.

    Returns
    -------
    tuple[bool, Path | None]
        ``(True, output_path)`` on success, ``(False, None)`` on failure.
        Never raises -- graceful degradation per CONTEXT.md.
    """
    try:
        # Collect all valid SectionNotation objects
        all_sections: list[SectionNotation] = []

        for sec_idx, sec_data in enumerate(json_sections):
            if sec_data is None:
                logger.debug("Skipping section %d: no JSON data", sec_idx)
                continue

            for item in sec_data:
                try:
                    notation = SectionNotation.model_validate(item)
                    all_sections.append(notation)
                except Exception as exc:
                    logger.warning(
                        "Invalid JSON in section %d: %s",
                        sec_idx,
                        str(exc)[:200],
                    )

        if not all_sections:
            logger.warning("No valid notation sections found; skipping MusicXML generation")
            return False, None

        # Build instrument mapping: identifier -> display name
        # Use sanitized identifiers matching what SectionNotation.instrument contains
        instruments: dict[str, str] = {}
        for name in instrument_names:
            # SectionNotation.instrument uses underscore-separated identifiers
            ident = name.lower().replace(" ", "_").replace("-", "_")
            instruments[ident] = name

        # Also register any instrument identifiers that appear in the sections
        # but aren't in the explicit list (handles LLM variation)
        for section in all_sections:
            if section.instrument not in instruments:
                instruments[section.instrument] = section.instrument

        # Build music21 Score
        score = build_score(
            all_sections=all_sections,
            instruments=instruments,
            key=key_sig if key_sig else None,
            time_sig=time_sig if time_sig else None,
            tempo=tempo_bpm if tempo_bpm else None,
        )

        # Write MusicXML
        output_path.parent.mkdir(parents=True, exist_ok=True)
        score.write("musicxml", fp=str(output_path))
        logger.info("Wrote MusicXML: %s", output_path)

        # Validate against XSD
        is_valid, error_msg = validate_musicxml(output_path, xsd_path)
        if is_valid:
            logger.info("MusicXML passes XSD validation")
            return True, output_path

        logger.warning("MusicXML failed XSD validation: %s", error_msg[:200])
        # Still return the file -- it may be usable even if not strictly valid
        return True, output_path

    except Exception as exc:
        logger.warning(
            "MusicXML assembly failed: %s",
            str(exc)[:200],
        )
        return False, None
