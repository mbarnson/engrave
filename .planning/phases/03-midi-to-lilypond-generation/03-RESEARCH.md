# Phase 3: MIDI-to-LilyPond Generation - Research

**Researched:** 2026-02-24
**Domain:** MIDI parsing, tokenization, LLM-driven LilyPond code generation, section-by-section coherence
**Confidence:** MEDIUM-HIGH (MIDI parsing and LilyPond well-documented; LLM-for-LilyPond patterns novel but grounded in established code generation research)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- When MIDI tracks lack instrument metadata (common in type 0): warn user about ambiguity, offer option to label tracks with instrument assignments, but generate as generic treble/bass clef parts if user does not label
- Support both MIDI type 0 (single track, interleaved) and type 1 (multi-track) files
- User labeling is optional, not blocking -- generation proceeds either way
- Generate in 4-8 bar sections with full musical coherence state passing between sections
- Coherence state carries forward: key signature, time signature, tempo, dynamics, articulation style, voicing patterns, rhythmic density -- full musical context, not just structural facts
- Richer context means larger prompt overhead per section, but continuity between sections is critical for usable output
- If a section fails compilation even after the Phase 1 retry loop (5 attempts): halt the entire generation
- No partial output with gaps -- user gets a complete result or a failure report
- Structured failure log for every compilation failure: MIDI input pattern, prompt sent, LilyPond error, retry attempts. This feeds v2 fine-tuning (TUNE-02)
- All LilyPond source generated and stored in concert pitch
- No transposition logic in this phase -- transposition is deterministic and belongs to Phase 4 rendering

### Claude's Discretion
- MIDI parsing and tokenization approach (how MIDI events become prompt input)
- Prompt template design and context window budget allocation between MIDI tokens, RAG examples, and coherence state
- Section boundary detection strategy (structural cues vs fixed-length chunks)
- RAG query formulation (how MIDI content maps to retrieval queries)
- Coherence state schema design (exact fields and serialization)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Summary

Phase 3 is the core value delivery -- the first time a user provides MIDI and receives compilable LilyPond. The pipeline receives a MIDI file (type 0 or type 1), parses it into a structured representation, tokenizes it for LLM consumption, retrieves relevant LilyPond examples from the Phase 2 RAG corpus, and generates LilyPond code section-by-section via LLM with coherence state passing between sections. The generated code compiles through the Phase 1 compile-fix loop, and all music is stored in concert pitch.

The critical design decisions center on three areas: (1) how MIDI events are represented as text for LLM prompts (tokenization strategy), (2) how sections are detected and bounded, and (3) how coherence state is structured and serialized between section-generation calls. The MIDI parsing itself is well-served by existing Python libraries (mido for low-level access, pretty_midi for analysis). The generation prompt must carefully budget context window space between MIDI tokens, RAG examples, coherence state, and structural templates.

The LilyPond code should be generated in absolute pitch mode (not \relative), using a variable-per-instrument pattern where the LLM fills in music expressions within pre-validated structural templates. This reduces the LLM's burden from "generate a complete LilyPond file" to "generate the music content for these instruments in this section," dramatically improving compilation success rates.

**Primary recommendation:** Use mido for MIDI parsing, pretty_midi for musical analysis (key estimation, tempo, instrument detection), a custom text-based MIDI tokenization optimized for LLM consumption (not MidiTok), absolute-pitch LilyPond generation into pre-validated structural templates, and a JSON-serialized coherence state schema passed between section calls.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FNDN-01 | System accepts MIDI type 0 and type 1 files as input and routes them directly to the notation stage | mido handles both type 0 and type 1 natively; type 0 needs channel-based track splitting |
| LILY-01 | System generates compilable LilyPond source code from MIDI tokens + structured text description + user hints + ensemble preset + RAG examples | Prompt template architecture with absolute pitch mode, variable-per-instrument templates, Phase 1 compile-fix loop integration |
| LILY-02 | System generates scores section-by-section (4-8 bar chunks) with coherence state passing | Section boundary detection from MIDI meta events + fixed-length fallback; JSON coherence state schema |
| LILY-03 | All music is stored internally in concert pitch; transposition is applied deterministically at render time | LilyPond absolute pitch mode with no \transpose in generated code; MIDI is already concert pitch |
| LILY-04 | System achieves >90% LilyPond compilation success rate on first attempt | Structural templates + absolute pitch mode + RAG examples + brace-matching pre-validation |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mido | 1.3.2 | MIDI file parsing (type 0, type 1), track/message iteration, meta message access | De facto Python MIDI library. Stable, well-documented, lightweight. Reads type 0 and type 1 natively. |
| pretty_midi | 0.2.11 | MIDI musical analysis: key estimation, tempo detection, instrument programs, piano roll, note statistics | Higher-level analysis built on mido. Key estimation via chroma, tempo estimation, instrument detection from program_change events. |
| python-ly | 0.9.5 | LilyPond syntax validation, tokenization, structural parsing | Official Frescobaldi project. Parses LilyPond source into token trees. Use for pre-validation before compilation. |
| pydantic | 2.12.x | Coherence state schema, failure log models, section metadata | Already in project. Type-safe serialization of coherence state between section calls. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| music21 | latest | Key detection from MIDI when pretty_midi's chroma estimation is insufficient | Fallback for complex key analysis; heavier dependency but more accurate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mido + pretty_midi | MidiTok (v3.0.6) | MidiTok is designed for ML tokenization (REMI, TSD, etc.) -- excellent for training music generation models, but overkill for our use case where we need human-readable text tokens for LLM prompts, not integer token sequences for model training. MidiTok uses symusic internally, not mido. Adds unnecessary dependency complexity. |
| mido + pretty_midi | symusic | Faster C++ backend but less mature Python API. MidiTok uses it. For our scale (single files, not batches), mido's pure Python is fast enough and better documented. |
| Custom text tokenization | MidiTok REMI tokens | REMI produces integer token sequences optimized for transformer training. We need natural-language-like text descriptions of MIDI content that an LLM (Qwen3-Coder, Claude) can understand as part of a generation prompt. Custom text tokenization is the right approach. |
| python-ly | Abjad 3.31 | Abjad requires LilyPond 2.25.26+ (dev branch). python-ly works with stable 2.24.x. Abjad is heavier and designed for programmatic score construction, not validation. |

**Installation:**
```bash
uv add mido pretty_midi python-ly
```

## Architecture Patterns

### Recommended Module Structure
```
src/engrave/
├── midi/                    # NEW: MIDI handling for Phase 3
│   ├── __init__.py
│   ├── loader.py            # Load MIDI type 0/1, normalize to multi-track
│   ├── analyzer.py          # Musical analysis (key, tempo, time sig, instruments)
│   ├── tokenizer.py         # Convert MIDI events to text tokens for LLM prompts
│   └── sections.py          # Section boundary detection and splitting
├── generation/              # NEW: LilyPond generation pipeline
│   ├── __init__.py
│   ├── pipeline.py          # Orchestrate section-by-section generation
│   ├── coherence.py         # CoherenceState schema and update logic
│   ├── prompts.py           # Prompt template construction and budget management
│   ├── templates.py         # LilyPond structural templates (score skeleton, variables)
│   ├── assembler.py         # Assemble section outputs into complete .ly file
│   └── failure_log.py       # Structured failure logging (TUNE-02)
├── lilypond/                # EXISTING: Phase 1 compiler + fixer
│   ├── compiler.py
│   ├── parser.py
│   └── fixer.py
├── llm/                     # EXISTING: Phase 1 inference router
│   ├── router.py
│   └── exceptions.py
└── config/                  # EXISTING: Phase 1 config
    ├── settings.py
    └── roles.py
```

### Pattern 1: MIDI Normalization (Type 0 to Multi-Track)

**What:** Normalize all MIDI input to a consistent multi-track representation. Type 1 files already have separate tracks. Type 0 files have all channels interleaved in a single track and must be split by MIDI channel into separate logical tracks.

**When to use:** Always, as the first step after loading a MIDI file.

**Example:**
```python
# src/engrave/midi/loader.py
import mido
from dataclasses import dataclass

@dataclass
class MidiTrackInfo:
    """Normalized track with instrument metadata."""
    track_index: int
    channel: int | None
    program: int | None        # General MIDI program number
    instrument_name: str | None # From meta message or GM lookup
    messages: list              # Note events for this track
    is_drum: bool               # Channel 10 = drums

def load_and_normalize(path: str) -> list[MidiTrackInfo]:
    """Load MIDI file, normalize type 0 -> multi-track by channel."""
    mid = mido.MidiFile(path)

    if mid.type == 0:
        # Split single track by channel
        return _split_type0_by_channel(mid.tracks[0], mid.ticks_per_beat)
    elif mid.type == 1:
        # Already multi-track, extract instrument info per track
        return _parse_type1_tracks(mid.tracks, mid.ticks_per_beat)
    else:
        raise ValueError(f"MIDI type {mid.type} not supported (only type 0 and 1)")
```

### Pattern 2: Text-Based MIDI Tokenization for LLM Prompts

**What:** Convert MIDI events into a compact, human-readable text representation that an LLM can understand as part of a generation prompt. This is NOT the same as MidiTok-style integer tokenization for model training. The goal is a representation that a code-generation LLM reads as "instructions for what music to write."

**When to use:** When building the MIDI portion of each section's generation prompt.

**Why text, not REMI integers:** The LLM (Qwen3-Coder, Claude) understands natural language and code. A text representation like `bar 1: c4(q, mf) d4(q) e4(h) | bar 2: f4(w)` is far more useful to a code-gen LLM than `Bar_0 Position_0 Pitch_60 Velocity_80 Duration_480`. The LLM needs to map MIDI content to LilyPond syntax, and a readable intermediate makes that mapping explicit.

**Example:**
```python
# src/engrave/midi/tokenizer.py

def tokenize_section_for_prompt(
    notes: list[NoteEvent],
    time_sig: tuple[int, int],
    key: str,
    bars: tuple[int, int],  # (start_bar, end_bar)
) -> str:
    """Convert MIDI notes to LLM-readable text representation.

    Output format per bar:
      bar N: pitch(duration, velocity) pitch(duration) ...
    Where pitch is note name + octave (c4, fis5),
    duration is lilypond-like (1=whole, 2=half, 4=quarter, 8=eighth),
    velocity is pp/p/mp/mf/f/ff when it changes.
    """
    # Group notes by bar, quantize to grid, format as text
    ...
```

**Token format design principles:**
1. Use note names (c, d, e, fis) not MIDI numbers -- matches LilyPond input
2. Use standard duration values (4=quarter, 8=eighth) -- matches LilyPond durations
3. Include velocity only when it changes (reduces token count)
4. Include rests explicitly (r4, r2) -- LLM must know about silence
5. Group by bar with bar numbers -- aligns with section boundaries
6. Keep it compact -- every token costs context window budget

### Pattern 3: LilyPond Structural Templates (Variable-Per-Instrument)

**What:** Pre-define the LilyPond file skeleton (version header, score block, staff groups, staff declarations) as a template. The LLM fills in only the music expressions within named variables. This prevents the LLM from generating malformed score structure, which is the #1 cause of compilation failure.

**When to use:** Always. Never ask the LLM to generate the score skeleton.

**Why:** LilyPond compilation failures from LLM code cluster overwhelmingly around structural issues: unmatched braces, incorrect nesting of \score/\new Staff/\new Voice, wrong placement of \relative blocks. By providing the structure and asking the LLM to fill in only the music content, compilation success rates jump dramatically.

**Example:**
```python
# src/engrave/generation/templates.py

SCORE_TEMPLATE = r"""
\version "2.24.4"

% Generated by Engrave - concert pitch
% Section: {section_label} (bars {start_bar}-{end_bar})

{instrument_variables}

\score {{
  <<
{staff_declarations}
  >>
  \layout {{ }}
}}
"""

INSTRUMENT_VARIABLE = r"""
{var_name} = {{
{music_content}
}}
"""

# The LLM generates ONLY the {music_content} for each instrument variable.
# The template handles \version, \score, \new Staff, braces.
```

**Critical design detail: absolute pitch mode.** All generated music uses absolute pitch (no \relative). This is the LilyPond documentation's own recommendation for computer-generated files. Absolute pitch eliminates the entire class of octave-relativity bugs that plague \relative mode.

### Pattern 4: Section-by-Section Generation with Coherence State

**What:** Divide the MIDI input into sections (4-8 bars), generate LilyPond for each section in a separate LLM call, pass a coherence state object forward that carries full musical context. Each section's output compiles independently through the Phase 1 fix loop before the next section begins.

**When to use:** Any MIDI input longer than ~8 bars. Short inputs (<=8 bars) can be generated in a single pass.

**Why this order matters:** Compile each section before generating the next. If section 3 fails and halts generation (per user decision), sections 1-2 are already validated. The failure log captures the exact prompt and MIDI data that caused section 3 to fail.

**Example:**
```python
# src/engrave/generation/pipeline.py

async def generate_from_midi(
    midi_path: str,
    router: InferenceRouter,
    compiler: LilyPondCompiler,
    rag_retriever,  # Phase 2 RAG system
    user_labels: dict[int, str] | None = None,
) -> GenerationResult:
    """Full MIDI-to-LilyPond pipeline.

    1. Load and normalize MIDI
    2. Analyze musical properties
    3. Detect section boundaries
    4. For each section:
       a. Tokenize MIDI for this section
       b. Query RAG for similar examples
       c. Build prompt with tokens + RAG + coherence state + template
       d. Generate LilyPond via LLM
       e. Compile through fix loop
       f. Update coherence state
       g. If compilation fails after retries: halt with failure log
    5. Assemble all sections into complete .ly file
    """
```

### Pattern 5: Prompt Budget Management

**What:** The LLM prompt for each section must fit within the model's context window while including MIDI tokens, RAG examples, coherence state, structural template, and generation instructions. A prompt budget manager allocates tokens across these components with hard limits.

**When to use:** Every section generation call.

**Why:** Without explicit budgeting, it is trivially easy to exceed context windows. A 4-bar section of a 17-instrument big band chart can produce hundreds of lines of MIDI token text. Adding 3-5 RAG examples at ~200 tokens each, coherence state at ~300-500 tokens, and the structural template eats into the context rapidly. Explicit budgets prevent silent quality degradation from "lost in the middle" effects.

**Budget allocation (for ~32K effective context window):**
```
System prompt + instructions:       ~2,000 tokens (fixed)
LilyPond structural template:       ~500 tokens (fixed per section)
Coherence state (JSON):             ~500 tokens (grows slightly over time)
RAG examples (3-5):                 ~2,000-4,000 tokens (variable)
MIDI tokens for this section:       ~2,000-6,000 tokens (variable)
Generation output budget:           ~8,000-16,000 tokens (reserved)
Safety margin:                      ~4,000 tokens
```

### Anti-Patterns to Avoid

- **Generating complete .ly files in one LLM call:** Context overflow and coherence collapse on anything over ~16 bars. Always use section-by-section generation.
- **Using \relative pitch mode in generated code:** Octave relativity bugs are nearly impossible for an LLM to get right consistently. Use absolute pitch exclusively for computer-generated LilyPond.
- **Letting the LLM generate the score skeleton:** The LLM should fill in music expressions within templates, not generate \score, \new StaffGroup, or \new Staff blocks. Structural template errors are the #1 compilation failure cause.
- **Embedding raw LilyPond for RAG retrieval:** Embed musical descriptions, retrieve by musical similarity, return associated LilyPond code. (This is the Phase 2 design, repeated here for emphasis.)
- **Ignoring MIDI type 0 channel splitting:** Type 0 files have all instruments on one track, differentiated only by channel. Failing to split by channel produces a single staff with all notes piled together.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MIDI file parsing | Custom binary MIDI parser | mido 1.3.2 | MIDI binary format has edge cases (running status, sysex, meta messages). mido handles all of them. |
| Key signature detection from MIDI | Custom pitch class histogram analysis | pretty_midi.get_chroma() + key estimation | Key detection from note content is a solved problem in pretty_midi. Music21 as fallback for edge cases. |
| Tempo extraction | Custom tempo map builder | pretty_midi.get_tempo_changes() | MIDI tempo maps with multiple tempo changes are tricky. pretty_midi handles this correctly. |
| LilyPond syntax tokenization | Custom regex-based LilyPond parser | python-ly ly.lex module | LilyPond syntax is complex (nested modes, Scheme expressions, markup). python-ly's lexer handles all modes correctly. |
| Brace matching validation | Simple counter-based brace checker | python-ly ly.music tree parser | Counting braces misses context (braces inside strings, Scheme blocks). python-ly understands LilyPond's actual grammar. |
| MIDI note name conversion | Lookup table from MIDI number to note name | mido + standard pitch mapping | Enharmonic spelling matters (fis vs ges). Use a consistent mapping aligned with key context. |

**Key insight:** The MIDI parsing ecosystem is mature and stable. The novel work in this phase is the prompt engineering, section boundary detection, coherence state design, and assembly logic -- NOT the MIDI handling itself.

## Common Pitfalls

### Pitfall 1: MIDI Type 0 Files Appearing as Single-Instrument

**What goes wrong:** Type 0 MIDI files have all channels interleaved in one track. Naive parsing treats the entire file as one instrument, producing a single staff with all notes piled together. A 4-instrument piece becomes unreadable mush.
**Why it happens:** mido exposes type 0 as a single track in mid.tracks[0]. Without explicit channel splitting, all notes merge.
**How to avoid:** Always split type 0 by MIDI channel. Each channel becomes a separate logical track. Channel 10 is drums (General MIDI convention). Warn the user that track names are inferred from program_change messages (General MIDI instrument names) and may be incorrect.
**Warning signs:** Generated LilyPond has one enormous staff with notes spanning 5+ octaves, or notes colliding constantly.

### Pitfall 2: Missing Instrument Metadata in MIDI

**What goes wrong:** Many MIDI files lack track names, program_change messages, or instrument metadata. The system cannot determine what instrument each track represents, leading to generic "Track 1, Track 2" labels with wrong clefs and no meaningful differentiation.
**Why it happens:** MIDI files exported from DAWs without General MIDI compliance, or files where instrument assignment was channel-based without program_change messages.
**How to avoid:** Per user decision: warn about ambiguity, offer optional labeling, but proceed with best-guess assignment. Use pitch range analysis to guess clef (low range = bass clef, high range = treble clef). Use program_change when present. Accept that without user labeling, instrument names are generic.
**Warning signs:** All tracks assigned treble clef despite containing bass-range notes. No instrument names in generated score.

### Pitfall 3: Context Window Overflow on Dense Sections

**What goes wrong:** A 4-bar section with many instruments produces more MIDI token text than the budget allows. Adding RAG examples and coherence state pushes the prompt past the model's effective context window. The LLM either truncates output, degrades quality, or produces incomplete LilyPond.
**Why it happens:** Big band MIDI can have 17 simultaneous tracks. Even 4 bars of dense 17-instrument music generates thousands of tokens. Combined with RAG examples and coherence state, the total exceeds even large context windows.
**How to avoid:** Implement explicit prompt budget management (Pattern 5 above). If MIDI tokens exceed budget, reduce RAG examples first (from 5 to 3 to 1), then truncate coherence state to essentials only (key, time sig, tempo, dynamics). As a last resort, generate fewer instruments per call and merge.
**Warning signs:** LLM output cuts off mid-bar. Generated code is missing instruments that were in the MIDI. Quality degrades on later instruments in the output.

### Pitfall 4: Octave Errors in Absolute Pitch Mode

**What goes wrong:** The LLM generates notes in the wrong octave. A trumpet melody at c''4 (middle of treble clef) appears as c'4 (below the staff) or c'''4 (above the staff). The notes are "right" but the octave is wrong.
**Why it happens:** LilyPond's absolute pitch system requires explicit octave marks (', '', etc.) on every note. The LLM must track the intended octave for every note. Unlike \relative mode (where the LLM only needs to think about intervals), absolute mode requires exact octave specification.
**How to avoid:** The MIDI tokenizer should include explicit octave information in the token format (e.g., "c4" not "c" where 4 = octave). The prompt should include the LilyPond octave notation convention (c = C below staff, c' = middle C, c'' = C above staff). RAG examples in absolute pitch mode provide correct octave patterns for the LLM to follow.
**Warning signs:** Generated music plays back an octave too high or too low. Visual inspection shows notes with wrong octave marks. Comparison with MIDI input shows systematic octave displacement.

### Pitfall 5: Section Boundary Misalignment

**What goes wrong:** Section boundaries cut in the middle of a musical phrase. A tied note crosses a section boundary and gets dropped. A crescendo that spans bars 7-9 is split between section 1 (bars 1-8) and section 2 (bars 9-16), losing the dynamic arc.
**Why it happens:** Fixed-length section boundaries (every 8 bars) ignore musical structure. MIDI files may not have convenient structural markers.
**How to avoid:** Prefer section boundaries at: (1) rehearsal marks from MIDI meta events, (2) time signature changes, (3) key signature changes, (4) significant tempo changes. Fall back to fixed-length (8 bars) only when no structural cues exist. Handle ties across section boundaries explicitly: if the last note of section N has a duration extending into section N+1, include that tie information in section N+1's coherence state.
**Warning signs:** Tied notes disappear at section boundaries. Dynamic markings reset unexpectedly at every 8th bar. Style changes mid-phrase.

### Pitfall 6: Coherence Drift Across Sections

**What goes wrong:** By section 5 of a 20-section piece, the generated LilyPond has drifted from the musical style established in section 1. Dynamics reset to mf every section. Articulation patterns established in the opening are forgotten. The piece sounds like 20 unrelated 8-bar fragments.
**Why it happens:** The coherence state, if too sparse, loses important context. The LLM has no memory between calls beyond what the coherence state carries. Over many sections, small drifts compound.
**How to avoid:** Rich coherence state (per user decision: key, time sig, tempo, dynamics, articulation style, voicing patterns, rhythmic density). Include a brief text summary of "what has been generated so far" that grows with each section (but is periodically compressed to stay within budget). Validate coherence: check that dynamic markings in section N+1 are compatible with the ending dynamics of section N.
**Warning signs:** Every section starts at mf regardless of musical context. Articulation conventions change without musical justification. Generated summary becomes stale or contradictory.

## Code Examples

### MIDI Loading and Type 0 Normalization

```python
# src/engrave/midi/loader.py
# Source: mido docs (https://mido.readthedocs.io/en/stable/files/midi.html)

import mido
from dataclasses import dataclass, field

@dataclass
class NoteEvent:
    """Single note extracted from MIDI."""
    pitch: int          # MIDI pitch (0-127)
    start_tick: int     # Start time in ticks
    duration_ticks: int # Duration in ticks
    velocity: int       # Velocity (0-127)
    channel: int        # MIDI channel (0-15)

@dataclass
class MidiTrackInfo:
    """Normalized track with instrument metadata."""
    track_index: int
    channel: int | None
    program: int | None
    instrument_name: str | None
    notes: list[NoteEvent] = field(default_factory=list)
    is_drum: bool = False

def load_midi(path: str) -> tuple[list[MidiTrackInfo], dict]:
    """Load MIDI file and return normalized tracks + global metadata."""
    mid = mido.MidiFile(path)
    metadata = {
        "type": mid.type,
        "ticks_per_beat": mid.ticks_per_beat,
        "num_tracks": len(mid.tracks),
    }

    if mid.type == 0:
        tracks = _split_type0_by_channel(mid.tracks[0], mid.ticks_per_beat)
    elif mid.type == 1:
        tracks = _parse_type1_tracks(mid.tracks, mid.ticks_per_beat)
    else:
        raise ValueError(f"MIDI type {mid.type} not supported")

    return tracks, metadata


def _split_type0_by_channel(track: mido.MidiTrack, tpb: int) -> list[MidiTrackInfo]:
    """Split a type 0 single track into separate tracks by MIDI channel."""
    channel_notes: dict[int, list[NoteEvent]] = {}
    channel_programs: dict[int, int] = {}
    abs_time = 0
    pending: dict[tuple[int, int], int] = {}  # (channel, pitch) -> start_tick

    for msg in track:
        abs_time += msg.time
        if msg.type == "program_change":
            channel_programs[msg.channel] = msg.program
        elif msg.type == "note_on" and msg.velocity > 0:
            pending[(msg.channel, msg.note)] = abs_time
        elif msg.type in ("note_off", "note_on") and (
            msg.type == "note_off" or msg.velocity == 0
        ):
            key = (msg.channel, msg.note)
            if key in pending:
                start = pending.pop(key)
                channel_notes.setdefault(msg.channel, []).append(
                    NoteEvent(
                        pitch=msg.note,
                        start_tick=start,
                        duration_ticks=abs_time - start,
                        velocity=msg.velocity if msg.type == "note_on" else 64,
                        channel=msg.channel,
                    )
                )

    tracks = []
    for ch in sorted(channel_notes.keys()):
        program = channel_programs.get(ch)
        tracks.append(MidiTrackInfo(
            track_index=ch,
            channel=ch,
            program=program,
            instrument_name=_gm_instrument_name(program) if program is not None else None,
            notes=channel_notes[ch],
            is_drum=(ch == 9),  # GM drums on channel 10 (0-indexed: 9)
        ))

    return tracks
```

### Coherence State Schema

```python
# src/engrave/generation/coherence.py
from pydantic import BaseModel

class CoherenceState(BaseModel):
    """Musical state passed between section generation calls.

    Carries full musical context (per user decision): key, time sig,
    tempo, dynamics, articulation style, voicing patterns, rhythmic density.
    """
    section_index: int = 0
    total_sections: int = 1

    # Structural
    key_signature: str = "c \\major"     # LilyPond key format
    time_signature: str = "4/4"
    tempo_bpm: int = 120

    # Musical character
    dynamic_levels: dict[str, str] = {}  # track_name -> current dynamic (pp, p, mp, mf, f, ff)
    articulation_style: str = ""         # e.g., "legato", "staccato", "marcato-heavy"
    rhythmic_density: str = "moderate"   # "sparse", "moderate", "dense"
    voicing_patterns: list[str] = []     # e.g., ["close voicing", "drop-2", "unison"]

    # Cross-section continuity
    open_ties: dict[str, list[str]] = {} # track_name -> list of tied pitches from prev section
    last_bar_summary: str = ""           # Brief text summary of final bar
    generated_summary: str = ""          # Running summary of all generated content

    def to_prompt_text(self) -> str:
        """Serialize to compact text for inclusion in LLM prompt."""
        parts = [
            f"Section {self.section_index + 1} of {self.total_sections}",
            f"Key: {self.key_signature}, Time: {self.time_signature}, Tempo: {self.tempo_bpm} BPM",
        ]
        if self.dynamic_levels:
            dynamics = ", ".join(f"{k}: {v}" for k, v in self.dynamic_levels.items())
            parts.append(f"Current dynamics: {dynamics}")
        if self.articulation_style:
            parts.append(f"Articulation style: {self.articulation_style}")
        if self.voicing_patterns:
            parts.append(f"Voicing: {', '.join(self.voicing_patterns)}")
        if self.open_ties:
            ties = ", ".join(f"{k}: {v}" for k, v in self.open_ties.items())
            parts.append(f"Open ties from previous section: {ties}")
        if self.generated_summary:
            parts.append(f"Previously generated: {self.generated_summary}")
        return "\n".join(parts)
```

### Section-by-Section Generation Pipeline

```python
# src/engrave/generation/pipeline.py

async def generate_section(
    section_midi: dict[str, str],  # track_name -> tokenized MIDI text
    coherence: CoherenceState,
    rag_examples: list[str],       # Retrieved LilyPond examples
    template: str,                 # Structural template for this section
    router: InferenceRouter,
    compiler: LilyPondCompiler,
) -> tuple[str, CoherenceState]:
    """Generate and compile LilyPond for one section.

    Returns (compiled_lilypond, updated_coherence).
    Raises GenerationHaltError if compilation fails after fix loop.
    """
    prompt = build_section_prompt(
        section_midi=section_midi,
        coherence=coherence,
        rag_examples=rag_examples,
        template=template,
    )

    ly_code = await router.complete(
        role="generator",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    # Extract LilyPond from response (handles markdown blocks)
    ly_source = extract_lilypond_from_response(ly_code)

    # Compile through Phase 1 fix loop
    compile_result = await compile_with_fix_loop(
        source=ly_source,
        router=router,
        compiler=compiler,
    )

    if not compile_result.success:
        # Log structured failure and halt (per user decision)
        log_failure(section_midi, prompt, compile_result)
        raise GenerationHaltError(
            section=coherence.section_index,
            errors=compile_result.final_errors,
            attempts=compile_result.attempts,
        )

    # Update coherence state from generated output
    updated_coherence = update_coherence(coherence, compile_result.source, section_midi)
    return compile_result.source, updated_coherence
```

### Prompt Template Construction

```python
# src/engrave/generation/prompts.py

def build_section_prompt(
    section_midi: dict[str, str],
    coherence: CoherenceState,
    rag_examples: list[str],
    template: str,
) -> str:
    """Build the complete generation prompt for one section.

    Budget: system instructions (~2000 tokens) + template (~500) +
    coherence (~500) + RAG (~3000) + MIDI (~4000) + output reserve (~8000)
    """
    rag_text = "\n\n---\n\n".join(rag_examples) if rag_examples else "No examples available."
    midi_text = "\n\n".join(
        f"## {track_name}\n{tokens}" for track_name, tokens in section_midi.items()
    )

    return f"""Generate LilyPond music content for the following section.

RULES:
1. Use ABSOLUTE pitch mode (no \\relative). Every note must have explicit octave marks.
2. Generate ONLY the music content for each instrument variable. Do not generate \\version, \\score, or \\new Staff.
3. All pitches must be in CONCERT PITCH. Do not transpose.
4. Preserve all musical content from the MIDI input: pitches, rhythms, dynamics.
5. Add appropriate articulations, dynamics, and expression marks based on the musical context.
6. Output each instrument's music as a separate block labeled with the variable name.

CURRENT MUSICAL STATE:
{coherence.to_prompt_text()}

LILYPOND TEMPLATE (fill in the instrument variables):
{template}

SIMILAR EXAMPLES FROM CORPUS:
{rag_text}

MIDI CONTENT FOR THIS SECTION:
{midi_text}

Generate the LilyPond music content for each instrument variable:"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MidiTok REMI integer tokens for music LLMs | Text-based MIDI tokenization for code-gen LLMs | 2025 (MIDI-LLM, NeurIPS) | Code-gen LLMs understand natural language better than integer token sequences; text tokenization outperforms for prompt-based generation |
| \relative pitch mode for LilyPond | Absolute pitch for computer-generated LilyPond | LilyPond docs (longstanding) | Official LilyPond documentation explicitly recommends absolute mode for computer-generated files |
| Full-score single-pass generation | Section-by-section with coherence state | 2024-2025 (hierarchical expansion) | Stanford/MIT research shows coherence drops after ~2000 words of generated text; section-based generation with state maintenance preserves coherence |
| NotaGen (ABC notation generation) | Direct LilyPond generation via code-gen LLM | 2025 | NotaGen uses ABC notation (simpler but less expressive). Direct LilyPond generation leverages richer notation capabilities (articulations, dynamics, layout) and LLMs' code generation strength |

**Deprecated/outdated:**
- Qwen2-Audio-7B-Instruct: OBSOLETE (Aug 2024, 2 generations behind). Use Qwen3-Omni-30B-A3B for any audio analysis
- MIDI integer tokenization for LLM prompts: Not appropriate for code-gen models; use text tokenization

## Open Questions

1. **Optimal number of RAG examples per section**
   - What we know: 3-5 examples is the general recommendation for few-shot prompting. More examples improve pattern matching but cost context window tokens.
   - What's unclear: How many LilyPond examples provide diminishing returns for compilation success rate? Is 3 enough, or does 5 meaningfully improve output?
   - Recommendation: Start with 3, benchmark compilation success rate, add up to 5 if budget allows and quality improves.

2. **Section boundary detection accuracy from MIDI meta events**
   - What we know: MIDI files may contain rehearsal marks, time signature changes, and key signature changes as meta events. These are ideal section boundaries.
   - What's unclear: What fraction of real-world MIDI files contain useful structural meta events? Many DAW exports strip meta events.
   - Recommendation: Implement a priority chain: meta event boundaries > tempo/key changes > fixed-length fallback (8 bars). Log which strategy was used to measure hit rate.

3. **Coherence state compression for long pieces**
   - What we know: The generated_summary field in coherence state grows with each section. For a 40-section piece, this could consume thousands of tokens.
   - What's unclear: How aggressively can the summary be compressed without losing important context? Can an LLM reliably compress its own prior summaries?
   - Recommendation: Cap generated_summary at ~300 tokens. When it exceeds the cap, use the LLM to compress it (separate, cheap call with small model). Track whether compression causes quality degradation.

4. **LLM model quality for LilyPond generation**
   - What we know: STATE.md flags "LilyPond LLM generation quality ceiling unknown -- benchmark models early in Phase 3" as a blocker/concern.
   - What's unclear: How well do Qwen3-Coder-Next, Claude, and GPT-4 actually generate compilable LilyPond? No public benchmarks exist.
   - Recommendation: Build a small benchmark (10 diverse MIDI inputs) and measure first-attempt compilation success rate for each model before committing to one. This is critical gating for the >90% target (LILY-04).

5. **Note quantization for MIDI-to-LilyPond mapping**
   - What we know: MIDI note events have exact tick timestamps. LilyPond requires quantized durations (quarter, eighth, etc.). The quantization grid depends on the time signature and tempo.
   - What's unclear: How to handle expressive timing (swing, rubato) where note onsets don't align to the grid. How to handle tuplets (triplets, quintuplets).
   - Recommendation: Implement a quantization step with configurable grid resolution. Start with straight quantization to the nearest standard duration. Handle swing by detecting swing patterns (long-short eighth note pairs) and converting to swing notation. Tuplet detection is a research problem -- defer to best-effort quantization for v1.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-bdd + pytest-asyncio |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x --timeout=30` |
| Full suite command | `uv run pytest tests/ --cov=engrave --cov-fail-under=80` |
| Estimated runtime | ~15-30 seconds (mocked LLM calls, no real compilation) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FNDN-01 | Accept MIDI type 0 and type 1, route to notation | unit + integration | `uv run pytest tests/unit/test_midi_loader.py -x` | No -- Wave 0 gap |
| LILY-01 | Generate compilable LilyPond from MIDI + RAG + coherence | integration | `uv run pytest tests/integration/test_generation_pipeline.py -x` | No -- Wave 0 gap |
| LILY-02 | Section-by-section generation with coherence state | unit + integration | `uv run pytest tests/unit/test_coherence.py tests/integration/test_section_generation.py -x` | No -- Wave 0 gap |
| LILY-03 | Concert pitch storage (no transposed pitches in output) | unit | `uv run pytest tests/unit/test_concert_pitch.py -x` | No -- Wave 0 gap |
| LILY-04 | >90% first-attempt compilation success | integration (benchmark) | `uv run pytest tests/integration/test_compilation_success_rate.py -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `uv run pytest tests/ -x --timeout=30`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15-30 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_midi_loader.py` -- covers FNDN-01: MIDI type 0/1 loading, channel splitting, instrument detection
- [ ] `tests/unit/test_midi_tokenizer.py` -- covers LILY-01: MIDI-to-text tokenization, note naming, duration formatting
- [ ] `tests/unit/test_midi_sections.py` -- covers LILY-02: section boundary detection, fixed-length fallback
- [ ] `tests/unit/test_coherence.py` -- covers LILY-02: CoherenceState serialization, update logic, prompt text generation
- [ ] `tests/unit/test_templates.py` -- covers LILY-01, LILY-04: LilyPond structural template generation, variable insertion
- [ ] `tests/unit/test_concert_pitch.py` -- covers LILY-03: verify no \transpose in generated output, absolute pitch mode
- [ ] `tests/unit/test_prompt_budget.py` -- covers context window budget allocation and truncation
- [ ] `tests/unit/test_failure_log.py` -- covers structured failure logging for TUNE-02
- [ ] `tests/integration/test_generation_pipeline.py` -- covers LILY-01: end-to-end MIDI-to-LilyPond with mocked LLM/RAG
- [ ] `tests/integration/test_section_generation.py` -- covers LILY-02: multi-section generation with coherence
- [ ] `tests/integration/test_compilation_success_rate.py` -- covers LILY-04: benchmark compilation success across test MIDI corpus
- [ ] `tests/integration/features/midi_generation.feature` -- Gherkin scenarios for MIDI-to-LilyPond generation
- [ ] `tests/conftest.py` updates -- add mock_rag_retriever, sample MIDI fixtures, generation pipeline fixtures
- [ ] `tests/fixtures/` -- sample MIDI files (type 0, type 1, with/without metadata) for test corpus

## Sources

### Primary (HIGH confidence)
- [Mido Documentation v1.3.2](https://mido.readthedocs.io/en/stable/) -- MIDI file handling, type 0/1 support, message iteration
- [Mido MIDI Files Reference](https://mido.readthedocs.io/en/stable/files/midi.html) -- Type 0/1 semantics, track handling
- [pretty_midi Documentation v0.2.11](https://craffel.github.io/pretty-midi/) -- Musical analysis, key estimation, instrument detection
- [LilyPond Notation Reference v2.24: Writing Pitches](https://lilypond.org/doc/v2.24/Documentation/notation/writing-pitches) -- Absolute vs relative pitch modes
- [LilyPond Notation Reference v2.24: Displaying Pitches](https://lilypond.org/doc/v2.24/Documentation/notation/displaying-pitches) -- Concert pitch, \transposition, \transpose
- [LilyPond Learning Manual: Scores and Parts](https://lilypond.org/doc/v2.23/Documentation/learning/scores-and-parts) -- Variable-based modular score organization
- [LilyPond Learning Manual: Absolute Note Names](https://lilypond.org/doc/v2.24/Documentation/learning/absolute-note-names) -- Absolute mode for computer-generated files
- [LilyPond Learning Manual: Organizing Pieces with Variables](https://lilypond.org/doc/v2.25/Documentation/learning/organizing-pieces-with-variables) -- Variable and include patterns
- [python-ly Documentation v0.9.5](https://python-ly.readthedocs.io/en/latest/) -- LilyPond parsing, tokenization, syntax validation

### Secondary (MEDIUM confidence)
- [MidiTok v3.0.6 Documentation](https://miditok.readthedocs.io/en/latest/tokenizations.html) -- REMI, TSD, Structured tokenization approaches (informed our custom tokenization design)
- [MIDI-LLM: Text-to-MIDI Music Generation (NeurIPS 2025)](https://arxiv.org/html/2511.03942v1) -- Arrival-time tokenization for LLM music generation
- [Long-Form Generation with LLMs: Coherence Study](https://brics-econ.org/long-form-generation-with-large-language-models-how-to-keep-structure-coherence-and-facts-accurate) -- Coherence drops after ~2000 words; section-based generation preserves quality
- [NotaGen: Symbolic Music Generation (IJCAI 2025)](https://arxiv.org/abs/2502.18008) -- LLM training paradigm for symbolic music; uses ABC not LilyPond
- [LilyPond + LLM Discussion (LilyPond User Mailing List)](http://www.mail-archive.com/lilypond-user@gnu.org/msg162834.html) -- Community experience with LLM-generated LilyPond
- [pretty_midi GitHub Repository](https://github.com/craffel/pretty-midi) -- Source code, tutorial, feature reference

### Tertiary (LOW confidence)
- [Claude and GPT LilyPond Generation Blog](https://beyondthepiano.jlmirall.es/2024/10/21/the-artificial-intelligence-of-large-language-models-llm-claude-and-gpt-and-their-ability-to-create-sheet-music-and-study-techniques-in-lilypond/) -- Single author assessment of LLM LilyPond capability; anecdotal but directionally useful
- [MidiTok GitHub Repository](https://github.com/Natooz/MidiTok) -- Alternative tokenization approach; evaluated and rejected for our use case

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- mido, pretty_midi, python-ly are mature, stable, well-documented libraries with clear version pins
- Architecture: MEDIUM-HIGH -- section-by-section generation with coherence state is well-grounded in long-form LLM generation research; specific prompt templates will need iteration
- Pitfalls: HIGH -- MIDI type 0 handling, context overflow, octave errors are well-documented across multiple sources; coherence drift is a known LLM limitation
- LilyPond generation patterns: MEDIUM -- absolute pitch mode and structural templates are best practices from LilyPond docs; actual LLM generation quality for LilyPond is novel and under-benchmarked

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain; mido/pretty_midi/python-ly change slowly; LLM capabilities evolve faster)
