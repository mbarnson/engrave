"""Section-by-section MIDI-to-LilyPond generation orchestration.

Loads a MIDI file, analyzes its musical properties, detects section
boundaries, generates LilyPond per section via LLM, compiles through
the fix loop, and assembles the complete output.  Generation halts on
first unrecoverable compilation failure.

Parallel fan-out: each section dispatches two concurrent LLM requests --
one for LilyPond (existing), one for structured JSON notation events
(new).  JSON generation is optional; failure does not affect LilyPond.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from engrave.generation.assembler import assemble_sections
from engrave.generation.coherence import CoherenceState
from engrave.generation.failure_log import FailureRecord, log_failure
from engrave.generation.prompts import (
    build_json_generation_suffix,
    build_section_prompt,
    extract_json_from_response,
)
from engrave.generation.templates import (
    build_instrument_variable,
    build_score_template,
    parse_instrument_blocks,
    sanitize_var_name,
)
from engrave.lilypond.fixer import compile_with_fix_loop, extract_lilypond_from_response
from engrave.midi.analyzer import MidiAnalysis, analyze_midi
from engrave.midi.loader import MidiTrackInfo, load_midi
from engrave.midi.sections import detect_sections
from engrave.midi.tokenizer import tokenize_section_for_prompt

if TYPE_CHECKING:
    from engrave.lilypond.compiler import LilyPondCompiler
    from engrave.llm.router import InferenceRouter

logger = logging.getLogger(__name__)


class GenerationHaltError(Exception):
    """Raised when a section fails compilation after all retries.

    Attributes:
        section_index: The zero-based index of the section that failed.
        final_errors: List of error strings from the last compilation attempt.
        attempt_count: Total number of fix attempts made.
    """

    def __init__(
        self,
        section_index: int,
        final_errors: list[str],
        attempt_count: int,
    ) -> None:
        self.section_index = section_index
        self.final_errors = final_errors
        self.attempt_count = attempt_count
        super().__init__(
            f"Generation halted at section {section_index}: "
            f"{len(final_errors)} errors after {attempt_count} attempts"
        )


@dataclass
class GenerationResult:
    """Result of a complete MIDI-to-LilyPond generation run."""

    success: bool
    ly_source: str = ""  # Complete assembled .ly file or empty on failure
    sections_completed: int = 0
    total_sections: int = 0
    failure_record: FailureRecord | None = None
    instrument_names: list[str] = field(default_factory=list)
    json_sections: list[list[dict] | None] = field(default_factory=list)


def _build_instrument_names(
    tracks: list[MidiTrackInfo],
    user_labels: dict[int, str] | None = None,
) -> list[str]:
    """Build instrument name list from tracks, with optional user overrides.

    Args:
        tracks: Loaded MIDI tracks.
        user_labels: Optional mapping of track_index -> instrument name.

    Returns:
        List of instrument names, one per track.
    """
    names: list[str] = []
    has_ambiguous = False

    for track in tracks:
        if user_labels and track.track_index in user_labels:
            names.append(user_labels[track.track_index])
        elif track.instrument_name:
            names.append(track.instrument_name)
        else:
            has_ambiguous = True
            names.append(f"Part {track.track_index + 1}")

    if has_ambiguous and not user_labels:
        logger.warning(
            "Some tracks lack instrument metadata. Using generic names. "
            "Provide user_labels for better results."
        )

    return names


def _extract_analysis_properties(analysis: MidiAnalysis) -> tuple[str, str, int]:
    """Extract key_signature, time_signature, and tempo_bpm from analysis.

    MidiAnalysis stores these as lists; we extract the first/primary values.

    Returns:
        (key_signature, time_signature_str, tempo_bpm)
    """
    key_sig = analysis.key_signature

    # Time signature: first entry as "N/D" string
    if analysis.time_signatures:
        num, denom, _tick = analysis.time_signatures[0]
        time_sig = f"{num}/{denom}"
    else:
        num, denom = 4, 4
        time_sig = "4/4"

    # Tempo: first entry's BPM
    tempo_bpm = int(analysis.tempo_changes[0][0]) if analysis.tempo_changes else 120

    return key_sig, time_sig, tempo_bpm


def _filter_notes_for_section(
    track: MidiTrackInfo,
    start_bar: int,
    end_bar: int,
    ticks_per_beat: int,
    beats_per_bar: float,
) -> list:
    """Filter a track's notes to those within a section's bar range."""
    ticks_per_bar = int(ticks_per_beat * beats_per_bar)
    start_tick = (start_bar - 1) * ticks_per_bar
    end_tick = end_bar * ticks_per_bar

    return [n for n in track.notes if n.start_tick >= start_tick and n.start_tick < end_tick]


async def _request_json_notation(
    prompt: str,
    instrument_names: list[str],
    router: InferenceRouter,
) -> list[dict] | None:
    """Dispatch the JSON notation generation request.

    Isolated so that any failure is caught without affecting LilyPond.

    Returns:
        Parsed JSON notation events, or None on any failure.
    """
    json_suffix = build_json_generation_suffix(instrument_names)
    json_prompt = prompt + "\n\n" + json_suffix
    try:
        json_response = await router.complete(
            role="generator",
            messages=[{"role": "user", "content": json_prompt}],
            temperature=0.1,
        )
        result = extract_json_from_response(json_response)
        return result if result else None
    except Exception:
        logger.warning("JSON notation generation failed; continuing with LilyPond only")
        return None


async def generate_section(
    section_midi: dict[str, str],
    coherence: CoherenceState,
    rag_examples: list[str],
    template: str,
    instrument_names: list[str],
    router: InferenceRouter,
    compiler: LilyPondCompiler,
) -> tuple[str, list[dict] | None, CoherenceState]:
    """Generate LilyPond (and optionally JSON) for a single section.

    Fans out two concurrent LLM requests via asyncio.gather:
      1. LilyPond generation (temperature 0.3, existing behaviour)
      2. JSON notation events (temperature 0.1, new)

    JSON failure does **not** affect the LilyPond path.

    Args:
        section_midi: Dict mapping track name to tokenized MIDI text.
        coherence: Current musical context state.
        rag_examples: Retrieved LilyPond examples from corpus.
        template: LilyPond structural template for this section.
        instrument_names: List of instrument names.
        router: LLM inference router.
        compiler: LilyPond compiler for fix loop.

    Returns:
        Tuple of (section_ly_source, json_notation_or_none, updated_coherence).

    Raises:
        GenerationHaltError: If compilation fails after all retries.
    """
    # Build shared prompt prefix (identical context for both requests)
    prompt = build_section_prompt(section_midi, coherence, rag_examples, template)

    # Fan out LilyPond + JSON requests concurrently
    ly_coro = router.complete(
        role="generator",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    json_coro = _request_json_notation(prompt, instrument_names, router)

    try:
        ly_response, json_data = await asyncio.gather(ly_coro, json_coro)
    except NotImplementedError:
        # Router doesn't support async -- fall back to sequential
        logger.info("Router does not support concurrent dispatch; falling back to sequential")
        ly_response = await router.complete(
            role="generator",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        json_data = await _request_json_notation(prompt, instrument_names, router)

    # -- LilyPond processing (unchanged) ----------------------------------

    # Extract LilyPond from response (handles code blocks etc.)
    extracted = extract_lilypond_from_response(ly_response)

    # Parse instrument blocks from LLM response
    try:
        blocks = parse_instrument_blocks(extracted)
    except ValueError:
        # If parsing fails, try the raw response
        try:
            blocks = parse_instrument_blocks(ly_response)
        except ValueError:
            # Fall back to using the extracted content as a single block
            var_names = [sanitize_var_name(name) for name in instrument_names]
            blocks = {var_names[0]: extracted} if var_names else {}

    # Fill template variables with extracted music content
    var_declarations = []
    for name in instrument_names:
        var_name = sanitize_var_name(name)
        content = blocks.get(var_name, "R1")  # Rest if LLM didn't provide
        var_declarations.append(build_instrument_variable(var_name, content))

    # Build section source from template with filled variables
    section_source = _build_section_source(instrument_names, var_declarations, coherence)

    # Compile through fix loop
    compile_result = await compile_with_fix_loop(
        source=section_source,
        router=router,
        compiler=compiler,
    )

    if not compile_result.success:
        return section_source, json_data, coherence

    # Update coherence with compiled source
    midi_text = "\n".join(section_midi.values())
    updated_coherence = coherence.update_from_section(compile_result.source, midi_text)

    return compile_result.source, json_data, updated_coherence


def _build_section_source(
    instrument_names: list[str],
    var_declarations: list[str],
    coherence: CoherenceState,
) -> str:
    """Build a compilable section source from variable declarations.

    Args:
        instrument_names: List of instrument names.
        var_declarations: List of formatted variable declaration strings.
        coherence: Current coherence state for tempo/key info.

    Returns:
        Complete LilyPond source string for this section.
    """
    var_names = [sanitize_var_name(name) for name in instrument_names]

    # Build staff references
    staff_lines = []
    for var_name, inst_name in zip(var_names, instrument_names, strict=True):
        staff_lines.append(
            f'    \\new Staff \\with {{ instrumentName = "{inst_name}" }} \\{var_name}'
        )

    staves_block = "\n".join(staff_lines)
    variables_block = "\n\n".join(var_declarations)

    return (
        f'\\version "2.24.4"\n'
        f"\n"
        f"% Generated by Engrave - concert pitch\n"
        f"\n"
        f"{variables_block}\n"
        f"\n"
        f"\\score {{\n"
        f"  <<\n"
        f"{staves_block}\n"
        f"  >>\n"
        f"  \\layout {{ }}\n"
        f"}}\n"
    )


def _save_training_pair(
    ly_source: str,
    json_data: list[dict],
    section_index: int,
    output_dir: str,
) -> None:
    """Save an aligned (LilyPond, JSON) training pair to the job directory.

    The pair is written as a single JSON file containing both the LilyPond
    source and the structured notation events for future fine-tuning data.

    Args:
        ly_source: LilyPond source string for this section.
        json_data: Parsed JSON notation events for this section.
        section_index: Zero-based section index (used in filename).
        output_dir: Root output/job directory path.
    """
    pairs_dir = Path(output_dir) / "training_pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)
    pair_path = pairs_dir / f"section_{section_index}.json"
    pair = {
        "ly_source": ly_source,
        "json_notation": json_data,
    }
    pair_path.write_text(json.dumps(pair, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("Saved training pair: %s", pair_path)


async def generate_from_midi(
    midi_path: str,
    router: InferenceRouter,
    compiler: LilyPondCompiler,
    rag_retriever=None,
    user_labels: dict[int, str] | None = None,
    output_dir: str | None = None,
) -> GenerationResult:
    """Orchestrate end-to-end MIDI-to-LilyPond generation.

    1. Load and normalize MIDI
    2. Analyze musical properties
    3. Detect section boundaries
    4. For each section: tokenize, query RAG, build prompt, generate, compile
    5. Assemble all sections into complete .ly file

    Args:
        midi_path: Path to the input MIDI file.
        router: LLM inference router.
        compiler: LilyPond compiler.
        rag_retriever: Optional RAG retriever callable (query, limit) -> list[str].
        user_labels: Optional track_index -> instrument_name overrides.
        output_dir: Optional job output directory.  When provided, aligned
            (LilyPond, JSON) training pairs are saved under
            ``output_dir/training_pairs/``.

    Returns:
        GenerationResult with success status and output.
    """
    # 1. Load MIDI
    tracks, _metadata = load_midi(midi_path)
    if not tracks:
        logger.error("No tracks found in MIDI file: %s", midi_path)
        return GenerationResult(success=False, total_sections=0)

    # 2. Analyze musical properties
    analysis = analyze_midi(midi_path)

    # 3. Build instrument names
    instrument_names = _build_instrument_names(tracks, user_labels)

    # 4. Extract analysis properties
    key_sig, time_sig_str, tempo_bpm = _extract_analysis_properties(analysis)

    # Parse time signature for tokenizer
    ts_parts = time_sig_str.split("/")
    time_sig_tuple = (int(ts_parts[0]), int(ts_parts[1]))
    beats_per_bar = time_sig_tuple[0] * (4.0 / time_sig_tuple[1])

    # 5. Detect sections
    sections = detect_sections(midi_path)
    total_sections = len(sections)

    # 6. Initialize coherence state
    # Build a temporary object with the attributes CoherenceState expects
    class _AnalysisProxy:
        pass

    proxy = _AnalysisProxy()
    proxy.key_signature = key_sig  # type: ignore[attr-defined]
    proxy.time_signature = time_sig_str  # type: ignore[attr-defined]
    proxy.tempo_bpm = tempo_bpm  # type: ignore[attr-defined]
    proxy.total_sections = total_sections  # type: ignore[attr-defined]

    coherence = CoherenceState.initial_from_analysis(proxy)

    # 7. Generate per section
    section_sources: list[str] = []
    json_sections: list[list[dict] | None] = []
    ticks_per_beat = analysis.ticks_per_beat

    for sec_idx, boundary in enumerate(sections):
        start_bar = boundary.bar_number
        # End bar is either the next boundary's bar - 1, or total_bars
        if sec_idx + 1 < len(sections):
            end_bar = sections[sec_idx + 1].bar_number - 1
        else:
            end_bar = analysis.total_bars

        # Skip empty sections
        if end_bar < start_bar:
            json_sections.append(None)
            continue

        section_label = f"Section {sec_idx + 1}"

        # a. Filter and tokenize notes per track
        section_midi: dict[str, str] = {}
        for track, name in zip(tracks, instrument_names, strict=True):
            filtered_notes = _filter_notes_for_section(
                track, start_bar, end_bar, ticks_per_beat, beats_per_bar
            )
            tokens = tokenize_section_for_prompt(
                notes=filtered_notes,
                time_sig=time_sig_tuple,
                key=key_sig,
                bars=(start_bar, end_bar),
                ticks_per_beat=ticks_per_beat,
            )
            section_midi[name] = tokens

        # b. Query RAG for similar examples
        rag_examples: list[str] = []
        if rag_retriever is not None:
            query = f"{key_sig} {tempo_bpm}bpm {', '.join(instrument_names)}"
            try:
                rag_examples = rag_retriever(query, limit=3)
            except Exception:
                logger.warning("RAG retrieval failed, proceeding without examples")
                rag_examples = []

        # c. Build template
        template = build_score_template(instrument_names, section_label, start_bar, end_bar)

        # d. Generate section (LilyPond + JSON fan-out)
        section_source, json_data, coherence = await generate_section(
            section_midi=section_midi,
            coherence=coherence,
            rag_examples=rag_examples,
            template=template,
            instrument_names=instrument_names,
            router=router,
            compiler=compiler,
        )

        # e. Check if compilation succeeded
        # We check by looking at whether coherence advanced (section_index incremented)
        if coherence.section_index <= sec_idx:
            # Compilation failed - build failure record
            midi_text = "\n".join(section_midi.values())
            prompt = build_section_prompt(section_midi, coherence, rag_examples, template)
            record = FailureRecord(
                timestamp=datetime.now(tz=UTC).isoformat(),
                section_index=sec_idx,
                midi_token_text=midi_text,
                prompt_sent=prompt,
                lilypond_error="Compilation failed after fix loop",
                lilypond_source=section_source,
                retry_attempts=5,
                error_hashes=[],
                coherence_state=coherence.model_dump(),
            )
            log_failure(record)

            return GenerationResult(
                success=False,
                ly_source="",
                sections_completed=sec_idx,
                total_sections=total_sections,
                failure_record=record,
                instrument_names=instrument_names,
                json_sections=json_sections,
            )

        section_sources.append(section_source)
        json_sections.append(json_data)

        # f. Save training pair if output_dir is provided and JSON succeeded
        if output_dir is not None and json_data is not None:
            try:
                _save_training_pair(section_source, json_data, sec_idx, output_dir)
            except Exception:
                logger.warning("Failed to save training pair for section %d", sec_idx)

    # 8. Assemble all sections
    if not section_sources:
        return GenerationResult(
            success=False,
            total_sections=total_sections,
            instrument_names=instrument_names,
            json_sections=json_sections,
        )

    assembled = assemble_sections(section_sources, instrument_names, analysis)

    return GenerationResult(
        success=True,
        ly_source=assembled,
        sections_completed=len(section_sources),
        total_sections=total_sections,
        instrument_names=instrument_names,
        json_sections=json_sections,
    )
