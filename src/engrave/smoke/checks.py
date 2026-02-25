"""9 structural check functions for smoke test output validation.

Each function returns a ``CheckResult`` and is independently testable.
Checks operate on the output ZIP file produced by the render pipeline.

Checks:
  1. No exceptions -- pipeline completed without crashing
  2. Compilable LilyPond -- .ly files have corresponding .pdf files
  3. Valid PDFs -- PDF files exist and are non-empty
  4. Valid MusicXML -- XSD validation + music21 re-read (SKIPPED if absent)
  5. All parts present -- expected number of PDFs in ZIP
  6. Correct transpositions -- <transpose> elements match expected intervals
  7. Note count > 0 -- every non-drum part has notes
  8. PDF file size > threshold -- catches "valid but empty" PDFs
  9. ZIP file count -- total files within expected range
"""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from engrave.smoke.runner import CheckResult

logger = logging.getLogger(__name__)


def check_no_exceptions(error: str | None) -> CheckResult:
    """Check 1: Pipeline completed without exceptions."""
    if error is None:
        return CheckResult(name="no_exceptions", passed=True)
    return CheckResult(name="no_exceptions", passed=False, message=error)


def check_compilable_ly(zip_path: Path) -> CheckResult:
    """Check 2: All .ly files in ZIP have corresponding .pdf files.

    The pipeline already compiled the .ly files. We verify compilation
    success by checking that for each .ly file (except music-definitions.ly),
    a .pdf with matching stem exists in the ZIP.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            ly_files = [n for n in names if n.endswith(".ly")]
            pdf_files = {Path(n).stem for n in names if n.endswith(".pdf")}

            missing: list[str] = []
            for ly_name in ly_files:
                stem = Path(ly_name).stem
                # music-definitions.ly has no corresponding PDF
                if stem == "music-definitions":
                    continue
                if stem not in pdf_files:
                    missing.append(ly_name)

            if missing:
                return CheckResult(
                    name="compilable_ly",
                    passed=False,
                    message=f"Missing PDFs for: {', '.join(missing)}",
                    details={"missing_pdfs": missing},
                )
            return CheckResult(
                name="compilable_ly",
                passed=True,
                details={"ly_count": len(ly_files)},
            )
    except Exception as exc:
        return CheckResult(
            name="compilable_ly",
            passed=False,
            message=f"Error reading ZIP: {exc}",
        )


def check_valid_pdfs(zip_path: Path) -> CheckResult:
    """Check 3: PDF files exist and are non-empty."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            pdf_names = [n for n in zf.namelist() if n.endswith(".pdf")]
            if not pdf_names:
                return CheckResult(
                    name="valid_pdfs",
                    passed=False,
                    message="No PDFs in ZIP",
                )
            for name in pdf_names:
                info = zf.getinfo(name)
                if info.file_size == 0:
                    return CheckResult(
                        name="valid_pdfs",
                        passed=False,
                        message=f"Empty PDF: {name}",
                    )
            return CheckResult(
                name="valid_pdfs",
                passed=True,
                details={"pdf_count": len(pdf_names)},
            )
    except Exception as exc:
        return CheckResult(
            name="valid_pdfs",
            passed=False,
            message=f"Error reading ZIP: {exc}",
        )


def check_valid_musicxml(zip_path: Path) -> CheckResult:
    """Check 4: MusicXML passes XSD 4.0 validation and music21 can parse it.

    If no .musicxml file exists in the ZIP, returns SKIPPED (not FAILED).
    MusicXML generation is optional in the pipeline.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            mxml_names = [n for n in zf.namelist() if n.endswith(".musicxml")]
            if not mxml_names:
                return CheckResult(
                    name="valid_musicxml",
                    passed=True,
                    message="SKIPPED (MusicXML not generated)",
                )

            # Extract to temp directory for validation
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                for mxml_name in mxml_names:
                    zf.extract(mxml_name, tmp_path)
                    extracted = tmp_path / mxml_name

                    # XSD validation
                    from engrave.musicxml.validator import validate_musicxml

                    is_valid, err_msg = validate_musicxml(extracted)
                    if not is_valid:
                        return CheckResult(
                            name="valid_musicxml",
                            passed=False,
                            message=f"XSD validation failed: {err_msg[:200]}",
                        )

                    # music21 re-read
                    try:
                        import music21

                        music21.converter.parse(str(extracted))
                    except Exception as exc:
                        return CheckResult(
                            name="valid_musicxml",
                            passed=False,
                            message=f"music21 parse failed: {exc}",
                        )

            return CheckResult(
                name="valid_musicxml",
                passed=True,
                details={"musicxml_count": len(mxml_names)},
            )
    except Exception as exc:
        return CheckResult(
            name="valid_musicxml",
            passed=False,
            message=f"Error checking MusicXML: {exc}",
        )


def check_all_parts_present(zip_path: Path, expected_instrument_count: int) -> CheckResult:
    """Check 5: ZIP contains expected number of part PDFs + score PDF.

    Expects 1 score + N parts = N+1 PDFs total.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            pdf_count = sum(1 for n in zf.namelist() if n.endswith(".pdf"))
            expected = expected_instrument_count + 1  # score + N parts
            if pdf_count == expected:
                return CheckResult(
                    name="all_parts_present",
                    passed=True,
                    details={"expected": expected, "actual": pdf_count},
                )
            return CheckResult(
                name="all_parts_present",
                passed=False,
                message=f"Expected {expected} PDFs, found {pdf_count}",
                details={"expected": expected, "actual": pdf_count},
            )
    except Exception as exc:
        return CheckResult(
            name="all_parts_present",
            passed=False,
            message=f"Error reading ZIP: {exc}",
        )


def check_correct_transpositions(zip_path: Path) -> CheckResult:
    """Check 6: Transposing instrument parts have correct <transpose> elements.

    Inspects MusicXML for <transpose> elements and verifies chromatic/diatonic
    values match expected intervals for known transposing instruments.

    If no MusicXML is present, returns passed=True with a "manual verification
    recommended" message (not a failure, per RESEARCH.md Open Question 1).
    """
    # Expected transposition intervals (chromatic, diatonic)
    # These are the intervals written in the <transpose> element
    expected_transpositions: dict[str, dict[str, int]] = {
        "alto": {"diatonic": -5, "chromatic": -9},
        "tenor": {"diatonic": -1, "chromatic": -2},
        "baritone": {"diatonic": -5, "chromatic": -9},
        "trumpet": {"diatonic": -1, "chromatic": -2},
    }

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            mxml_names = [n for n in zf.namelist() if n.endswith(".musicxml")]
            if not mxml_names:
                return CheckResult(
                    name="correct_transpositions",
                    passed=True,
                    message="SKIPPED (no MusicXML -- manual verification recommended)",
                )

            import xml.etree.ElementTree as ET

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                for mxml_name in mxml_names:
                    zf.extract(mxml_name, tmp_path)
                    extracted = tmp_path / mxml_name

                    tree = ET.parse(str(extracted))
                    root = tree.getroot()

                    # Handle MusicXML namespace
                    ns = ""
                    if root.tag.startswith("{"):
                        ns = root.tag.split("}")[0] + "}"

                    # Find score-part elements with part names
                    part_list = root.find(f"{ns}part-list")
                    if part_list is None:
                        return CheckResult(
                            name="correct_transpositions",
                            passed=True,
                            message="No part-list found -- manual verification recommended",
                        )

                    found_transpose = False
                    mismatches: list[str] = []
                    details: dict[str, Any] = {}

                    for score_part in part_list.findall(f"{ns}score-part"):
                        part_name_el = score_part.find(f"{ns}part-name")
                        if part_name_el is None or part_name_el.text is None:
                            continue
                        part_name = part_name_el.text.lower()
                        part_id = score_part.get("id", "")

                        # Find this part's data
                        for part_el in root.findall(f"{ns}part"):
                            if part_el.get("id") != part_id:
                                continue
                            # Look for <transpose> in first measure's <attributes>
                            for measure in part_el.findall(f"{ns}measure"):
                                attrs = measure.find(f"{ns}attributes")
                                if attrs is None:
                                    continue
                                transpose = attrs.find(f"{ns}transpose")
                                if transpose is not None:
                                    found_transpose = True
                                    chrom_el = transpose.find(f"{ns}chromatic")
                                    diat_el = transpose.find(f"{ns}diatonic")
                                    chrom = (
                                        int(chrom_el.text)
                                        if chrom_el is not None and chrom_el.text
                                        else 0
                                    )
                                    diat = (
                                        int(diat_el.text)
                                        if diat_el is not None and diat_el.text
                                        else 0
                                    )

                                    # Match against expected
                                    for key, expected in expected_transpositions.items():
                                        if key in part_name:
                                            if (
                                                chrom != expected["chromatic"]
                                                or diat != expected["diatonic"]
                                            ):
                                                mismatches.append(
                                                    f"{part_name}: expected chromatic={expected['chromatic']}, "
                                                    f"diatonic={expected['diatonic']}, "
                                                    f"got chromatic={chrom}, diatonic={diat}"
                                                )
                                            details[part_name] = {
                                                "chromatic": chrom,
                                                "diatonic": diat,
                                            }
                                break  # Only check first measure

                    if not found_transpose:
                        return CheckResult(
                            name="correct_transpositions",
                            passed=True,
                            message="Transposition metadata absent -- manual verification recommended",
                        )

                    if mismatches:
                        return CheckResult(
                            name="correct_transpositions",
                            passed=False,
                            message=f"Transposition mismatches: {'; '.join(mismatches)}",
                            details=details,
                        )

                    return CheckResult(
                        name="correct_transpositions",
                        passed=True,
                        details=details,
                    )

    except Exception as exc:
        return CheckResult(
            name="correct_transpositions",
            passed=False,
            message=f"Error checking transpositions: {exc}",
        )


def check_note_count(zip_path: Path) -> CheckResult:
    """Check 7: Each non-drum part has > 0 notes.

    Parses MusicXML with music21 and counts notes per part.
    If no MusicXML is present, returns SKIPPED.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            mxml_names = [n for n in zf.namelist() if n.endswith(".musicxml")]
            if not mxml_names:
                return CheckResult(
                    name="note_count",
                    passed=True,
                    message="SKIPPED (no MusicXML for note counting)",
                )

            import music21

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                zf.extract(mxml_names[0], tmp_path)
                extracted = tmp_path / mxml_names[0]

                score = music21.converter.parse(str(extracted))
                part_counts: dict[str, int] = {}
                empty_parts: list[str] = []

                for part in score.parts:
                    name = part.partName or f"Part {part.id}"
                    # Skip drum parts
                    if "drum" in name.lower() or "percussion" in name.lower():
                        continue
                    notes = list(part.recurse().getElementsByClass("Note"))
                    count = len(notes)
                    part_counts[name] = count
                    if count == 0:
                        empty_parts.append(name)

                if empty_parts:
                    return CheckResult(
                        name="note_count",
                        passed=False,
                        message=f"Empty parts (0 notes): {', '.join(empty_parts)}",
                        details={"per_part": part_counts},
                    )

                return CheckResult(
                    name="note_count",
                    passed=True,
                    details={"per_part": part_counts},
                )

    except Exception as exc:
        return CheckResult(
            name="note_count",
            passed=False,
            message=f"Error counting notes: {exc}",
        )


def check_pdf_file_size(zip_path: Path, min_size_bytes: int = 50_000) -> CheckResult:
    """Check 8: Every PDF in ZIP exceeds minimum size threshold.

    Catches "valid but empty" PDFs where compilation succeeded but
    the LLM produced no useful content (~20KB for an empty part).
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            pdf_names = [n for n in zf.namelist() if n.endswith(".pdf")]
            if not pdf_names:
                return CheckResult(
                    name="pdf_file_size",
                    passed=False,
                    message="No PDFs in ZIP",
                )

            undersized: list[str] = []
            sizes: dict[str, int] = {}
            for name in pdf_names:
                info = zf.getinfo(name)
                sizes[name] = info.file_size
                if info.file_size < min_size_bytes:
                    undersized.append(f"{name} ({info.file_size} bytes)")

            if undersized:
                return CheckResult(
                    name="pdf_file_size",
                    passed=False,
                    message=f"PDFs below {min_size_bytes} bytes: {', '.join(undersized)}",
                    details={"min_threshold": min_size_bytes, "sizes": sizes},
                )

            return CheckResult(
                name="pdf_file_size",
                passed=True,
                details={"min_threshold": min_size_bytes, "min_size": min(sizes.values())},
            )
    except Exception as exc:
        return CheckResult(
            name="pdf_file_size",
            passed=False,
            message=f"Error checking PDF sizes: {exc}",
        )


def check_zip_file_count(zip_path: Path, expected_min: int, expected_max: int) -> CheckResult:
    """Check 9: Total files in ZIP within expected range.

    For big band: 38 without MusicXML, 39 with MusicXML.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            count = len(zf.namelist())
            if expected_min <= count <= expected_max:
                return CheckResult(
                    name="zip_file_count",
                    passed=True,
                    details={
                        "expected_min": expected_min,
                        "expected_max": expected_max,
                        "actual": count,
                    },
                )
            return CheckResult(
                name="zip_file_count",
                passed=False,
                message=f"Expected {expected_min}-{expected_max} files, found {count}",
                details={
                    "expected_min": expected_min,
                    "expected_max": expected_max,
                    "actual": count,
                },
            )
    except Exception as exc:
        return CheckResult(
            name="zip_file_count",
            passed=False,
            message=f"Error reading ZIP: {exc}",
        )
