"""MusicXML 4.0 XSD validation.

Validates MusicXML files against the vendored MusicXML 4.0 XSD schema
using ``xmlschema``.  Returns (is_valid, error_message) tuples for
graceful handling -- invalid MusicXML is excluded from ZIP but never
crashes the pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path

import xmlschema

logger = logging.getLogger(__name__)

# Default vendored XSD path (MusicXML 4.0)
_DEFAULT_XSD = Path(__file__).parent / "schema" / "musicxml.xsd"


def validate_musicxml(
    musicxml_path: Path,
    xsd_path: Path | None = None,
) -> tuple[bool, str]:
    """Validate a MusicXML file against the MusicXML 4.0 XSD.

    Parameters
    ----------
    musicxml_path:
        Path to the MusicXML file to validate.
    xsd_path:
        Path to the XSD schema file.  Defaults to the vendored
        ``schema/musicxml.xsd``.

    Returns
    -------
    tuple[bool, str]
        ``(True, "")`` when valid, ``(False, error_message)`` when
        invalid or when an error occurs (e.g. missing file).
    """
    xsd = xsd_path or _DEFAULT_XSD

    if not musicxml_path.exists():
        msg = f"MusicXML file not found: {musicxml_path}"
        logger.warning(msg)
        return False, msg

    if not xsd.exists():
        msg = f"XSD schema not found: {xsd}"
        logger.warning(msg)
        return False, msg

    try:
        schema = xmlschema.XMLSchema(str(xsd))
        schema.validate(str(musicxml_path))
        return True, ""
    except xmlschema.XMLSchemaValidationError as exc:
        msg = str(exc)
        logger.warning("MusicXML validation failed: %s", msg[:200])
        return False, msg
    except Exception as exc:
        msg = f"Unexpected validation error: {exc}"
        logger.warning(msg)
        return False, msg
