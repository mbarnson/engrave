"""LLM-based key signature detection from tokenized MIDI note data.

Uses a rigorous music theory prompt to determine the key signature from
note content.  Provides both a one-shot detection function (for initial
key estimation) and a reusable prompt builder (for sliding-window key
change detection in future work, see en-8iy).

Fallback: when no LLM is available, callers should use
``engrave.midi.analyzer.estimate_key_krumhansl`` (Krumhansl-Kessler
statistical correlation).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from engrave.midi.tokenizer import tokenize_section_for_prompt

if TYPE_CHECKING:
    from engrave.llm.router import InferenceRouter
    from engrave.midi.loader import MidiTrackInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# Mapping from common pitch names (English, LilyPond) to LilyPond format.
_KEY_ROOT_MAP: dict[str, str] = {
    # Natural notes
    "c": "c", "d": "d", "e": "e", "f": "f", "g": "g", "a": "a", "b": "b",
    # English sharps/flats -> LilyPond
    "c#": "cis", "d#": "dis", "f#": "fis", "g#": "gis", "a#": "ais",
    "db": "des", "eb": "ees", "gb": "ges", "ab": "aes", "bb": "bes",
    "cb": "ces", "fb": "fes",
    # LilyPond names pass through
    "cis": "cis", "dis": "dis", "fis": "fis", "gis": "gis", "ais": "ais",
    "des": "des", "ees": "ees", "ges": "ges", "aes": "aes", "bes": "bes",
    "ces": "ces", "fes": "fes",
}

_KEY_RESPONSE_PATTERN = re.compile(
    r"(?:key(?:\s+(?:signature|is))?\s*[:=]?\s*)?"
    r"([a-gA-G][b#]?(?:es|is)?)\s*"
    r"(?:\\)?(major|minor|\\major|\\minor)",
    re.IGNORECASE,
)


def parse_llm_key_response(response: str) -> str | None:
    """Parse an LLM key detection response into LilyPond format.

    Accepts various formats the LLM might produce:

    - ``"bes \\major"`` (LilyPond native)
    - ``"Bb major"`` (English notation)
    - ``"key: F# minor"`` (prefixed)
    - ``"The key is Eb minor."`` (sentence)

    Returns:
        LilyPond key string like ``"bes \\major"`` or ``None`` on failure.
    """
    match = _KEY_RESPONSE_PATTERN.search(response)
    if not match:
        return None

    raw_root = match.group(1).lower()
    raw_mode = match.group(2).lower().lstrip("\\")

    ly_root = _KEY_ROOT_MAP.get(raw_root)
    if ly_root is None:
        return None

    ly_mode = "\\major" if raw_mode == "major" else "\\minor"
    return f"{ly_root} {ly_mode}"


# ---------------------------------------------------------------------------
# Prompt template — shared by initial detection and sliding-window detection
# ---------------------------------------------------------------------------

KEY_DETECTION_SYSTEM_PROMPT = """\
You are a music theory expert analyzing MIDI note data to determine the key \
signature.  The notes use LilyPond absolute pitch names: c d e f g a b with \
sharps (cis, dis, fis, gis, ais) and flats (ces, des, ees, fes, ges, aes, bes).  \
Octave marks: ' raises, , lowers (c' = middle C).

Apply these rules IN ORDER to determine the key:

1. ACCIDENTAL ANALYSIS
   Count sharps and flats across all notes.  The key signature that minimizes \
accidentals is usually correct.  Every key signature maps to a specific set of \
sharps or flats on the circle of fifths:
   - 0 accidentals: C major / A minor
   - 1 sharp (fis): G major / E minor
   - 2 sharps (fis, cis): D major / B minor
   - 1 flat (bes): F major / D minor
   - 2 flats (bes, ees): Bb major / G minor
   - 3 flats (bes, ees, aes): Eb major / C minor
   If you see consistent bes across measures with no other accidentals, the key \
is F major or D minor.

2. TONAL CENTER
   Which note functions as 'home'?  Look for:
   - Phrases ending on that note (melodic resolution)
   - Bass notes gravitating to it (harmonic foundation)
   - The note the melody keeps returning to
   C major and A minor share the same accidentals but have different tonal centers.

3. SCALE DEGREE FIT
   Map all notes to scale degrees against the top candidate keys.  The key where \
the most notes are diatonic (within the scale) wins.  A few chromatic passing \
tones or neighbor notes do NOT change the key — only consistent out-of-key notes \
matter.

4. CADENTIAL PATTERNS
   V-I motion is the strongest key indicator:
   - G-B-D resolving to C-E-G → C major
   - E-G#-B resolving to A-C-E → A minor
   - D-F#-A resolving to G-B-D → G major
   Look for dominant-to-tonic motion especially at phrase boundaries.

5. LEADING TONES
   A raised 7th scale degree strongly indicates the key:
   - B natural in C major/minor
   - F# in G major/minor
   - G# in A minor (harmonic/melodic minor)
   The presence of a leading tone narrows candidates immediately.

6. RELATIVE MAJOR/MINOR
   Relative keys share the same key signature but differ in tonal center.  \
If accidentals point to one key signature, ask: is the center the 1st degree \
(major) or the 6th degree (minor)?  Use rules 2 and 4 to distinguish.

7. PARALLEL MAJOR/MINOR
   Same tonic, different mode.  Look for the distinguishing intervals:
   - Flat 3rd: E vs Eb over a C center → C minor vs C major
   - Flat 6th: A vs Ab over a C center
   - Flat 7th: B vs Bb over a C center

8. OUTPUT FORMAT
   Respond with ONLY the key using LilyPond pitch names.  Use LilyPond \
accidental suffixes (bes NOT Bb, fis NOT F#, ees NOT Eb).  Format:
   <root> <mode>
   where <root> is a LilyPond pitch name and <mode> is 'major' or 'minor'.

Examples of correct responses:
   bes \\major
   fis \\minor
   c \\major
   ees \\minor
   g \\major
   d \\minor

Do NOT explain your reasoning.  Output ONLY the key."""


def build_key_detection_user_prompt(
    midi_text: str,
    time_sig: tuple[int, int],
    bar_range: tuple[int, int],
    total_bars: int,
) -> str:
    """Build the user message for key detection.

    Reusable by both initial (full-piece) detection and sliding-window
    detection.  The caller is responsible for tokenizing and formatting
    the MIDI text.

    Args:
        midi_text: Tokenized note data (multi-track, bar-grouped).
        time_sig: Time signature as (numerator, denominator).
        bar_range: (start_bar, end_bar) inclusive.
        total_bars: Total bars in the piece (for context).

    Returns:
        Formatted user prompt string.
    """
    start, end = bar_range
    return (
        f"Time signature: {time_sig[0]}/{time_sig[1]}\n"
        f"Bars {start}-{end} of {total_bars}:\n\n"
        f"{midi_text}\n\n"
        "What is the key signature?"
    )


# ---------------------------------------------------------------------------
# Tokenization helper
# ---------------------------------------------------------------------------


def tokenize_tracks_for_key_detection(
    tracks: list[MidiTrackInfo],
    ticks_per_beat: int,
    time_sig: tuple[int, int],
    bar_range: tuple[int, int],
) -> str:
    """Tokenize multiple tracks into a combined text block for key analysis.

    Args:
        tracks: MIDI tracks with note data.
        ticks_per_beat: MIDI resolution.
        time_sig: Time signature as (numerator, denominator).
        bar_range: (start_bar, end_bar) inclusive.

    Returns:
        Combined tokenized text with track headers, or empty string if
        no notes in range.
    """
    parts: list[str] = []
    for track in tracks:
        tokens = tokenize_section_for_prompt(
            notes=track.notes,
            time_sig=time_sig,
            key="c \\major",  # Placeholder — not used for tokenization
            bars=bar_range,
            ticks_per_beat=ticks_per_beat,
        )
        if tokens.strip():
            label = track.instrument_name or f"Track {track.track_index}"
            parts.append(f"## {label}\n{tokens}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# High-level detection function
# ---------------------------------------------------------------------------


async def detect_key_via_llm(
    router: InferenceRouter,
    tracks: list[MidiTrackInfo],
    ticks_per_beat: int,
    time_sig: tuple[int, int],
    total_bars: int,
    sample_bars: int = 16,
) -> str | None:
    """Ask the LLM to determine the key signature from tokenized note data.

    Tokenizes the first ``sample_bars`` bars across all tracks and sends
    the rigorous music theory prompt for key identification.

    Args:
        router: LLM inference router.
        tracks: Loaded MIDI tracks with note data.
        ticks_per_beat: MIDI resolution.
        time_sig: Time signature as (numerator, denominator).
        total_bars: Total number of bars in the piece.
        sample_bars: Number of bars to sample (default 16).

    Returns:
        LilyPond key string (e.g. ``"bes \\major"``) or ``None`` on failure.
    """
    sample_end = min(sample_bars, total_bars)
    bar_range = (1, sample_end)

    midi_text = tokenize_tracks_for_key_detection(
        tracks, ticks_per_beat, time_sig, bar_range
    )
    if not midi_text:
        return None

    messages = [
        {"role": "system", "content": KEY_DETECTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_key_detection_user_prompt(
                midi_text, time_sig, bar_range, total_bars
            ),
        },
    ]

    try:
        response = await router.complete(
            role="generator",
            messages=messages,
            temperature=0.0,
            max_tokens=32,
        )
        key = parse_llm_key_response(response.strip())
        if key:
            logger.info("LLM key detection: %s (raw: %r)", key, response.strip())
        else:
            logger.warning(
                "LLM key detection: unparseable response %r", response.strip()
            )
        return key
    except Exception as exc:
        logger.warning(
            "LLM key detection failed, falling back to Krumhansl-Kessler: %s", exc
        )
        return None
