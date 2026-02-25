# Phase 7: Convergent Sight-Reading & Ensemble Intelligence - Research

**Researched:** 2026-02-24
**Domain:** LilyPond post-processing (articulation defaults, cross-part comparison), generation pipeline restructuring (per-instrument to per-section-group), LilyPond beaming configuration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Implement the 4 ENSM-03 rules only for v1: unmarked quarter = short (staccato), unmarked eighth = long (no mark), swing assumed unless "Straight 8s," staccato+accent never paired
- **Post-processing only** -- deterministic transforms on generated LilyPond, no articulation rules in the LLM prompt. Clean separation: LLM generates musical intent, post-processor applies notational conventions
- **Purely syntactic** -- apply rules by note duration alone, no beat-position or phrase-boundary awareness. If a specific note needs different treatment (e.g., pickup note should be long), that's the LLM's job to mark explicitly
- **Staccato+accent resolution**: keep accent, strip staccato. Accent subsumes staccato in jazz brass. Log the resolution as telemetry (same structured audit log as Phase 6) for TUNE-02 feedback loop, not as user-facing warning
- Phonetic enunciation system (attack character notation) deferred to v1.1 -- requires validation against Sam's actual charts and subjective style-dependent mappings
- **Preset-defined section groups**: `InstrumentSpec` gets a `section_group` field. Big band preset defines: trumpets (4), trombones (4), saxes (5) as joint groups. Rhythm instruments (piano, guitar, bass, drums) are ungrouped (`section_group = None`) and keep per-instrument generation
- **Fan-out unit is the section group**: 3 section-group calls + 4 individual calls = 7 calls per section, each with (LilyPond, JSON) fan-out = 14 parallel requests. Down from 17 instruments x 2 = 34
- **Existing delimiter pattern unchanged**: `parse_instrument_blocks()` already handles multi-instrument delimited output. Joint calls scope the template variables and MIDI content to only the instruments in the group. Same parsing code, more focused generation unit
- **Per-call JSON for Phase 5.1 fan-out**: one JSON blob per section-group call containing all instruments' notation events (array of `{"instrument": "trumpet_1", "measures": [...]}` objects). Both LilyPond and JSON requests share the same prefix cache. Never split into per-instrument JSON requests -- that loses the cross-instrument context
- **Section-sequential coherence only**: each section group gets coherence state from its own previous temporal section. No cross-section-group sharing within the same bar range. Cross-section coordination comes from input data (MIDI velocities, audio description, user hints), not coherence state. This preserves parallelism: trumpets, trombones, and saxes for the same bar range generate concurrently
- **Prompt context scoped per group**: MIDI tokens, RAG examples, and coherence state scoped to the section group's instruments. Musically coherent context -- the LLM sees trumpet voicings when writing trumpets, not drum patterns
- **Strictly identical match**: all parts in a section must have the exact same articulation on the exact same beat position for omission to apply. If any part differs, all keep their markings
- **Rests are absent from comparison**: if trumpet 4 rests on beat 1 while trumpets 1-3 have staccato, trumpet 4 is excluded from the comparison (not treated as "different")
- **Dynamics always printed**: omission rule applies only to articulation marks (staccato, accent, tenuto, marcato). Dynamics, tempo markings, expression text, and rehearsal marks are always printed on every part. Explicit allowlist of mark types eligible for omission
- **No visual indicator of omission**: no "simile" or "sect." markings. Absence of marking IS the indicator -- that's the Tim Davies convention. Players know the defaults before they sit down
- **Processing pipeline order**: LLM output -> apply ENSM-03 defaults -> apply ENSM-05 omission rule -> final LilyPond. Each step operates on complete data from the previous step
- **Two distinct parsing levels -- not one post-processor, two**: Articulation defaults (ENSM-03) are a token-level transform -- scan LilyPond for duration tokens (`c4`, `d8`), match duration, add/strip articulation marks. No positional context needed. The omission rule (ENSM-05) is a cross-part comparison that requires lightweight rhythmic alignment -- accumulate beat position within each bar by summing durations (`4` = 1 beat, `8` = 0.5 beat, `r4` = 1 beat rest), then compare articulations across parts at the same (bar, beat) coordinate. LilyPond durations are explicit in the token stream so the alignment is arithmetic, not music theory. But these are two separate components: a token scanner for defaults and a rhythmic aligner for omission. The coding agent must build both
- **Template-level, not post-processing**: beaming is controlled by `\set Timing.beamExceptions`, `\set Timing.baseMoment`, `\set Timing.beatStructure` in the LilyPond score template. Not per-note beam brackets
- **Resolved `beam_style` enum**: `swing` or `straight` per section. Latin IS straight eighth beaming -- no separate category. Resolved from Phase 6 audio description + user hints before generation. Default to `swing` for big band if unspecified
- **Per-section, supports mid-chart changes**: each section's template emits the correct `\set Timing` commands. Swing heads, Latin bridge, swing out-head all work naturally with the existing section-by-section architecture
- **Section-group-uniform**: all instruments in a section group share the same `beam_style`. Beaming is a style convention, not a per-instrument choice. The `\set Timing` commands emit at the staff-group level
- **LilyPond version note**: Engrave targets LilyPond 2.24 which uses `baseMoment`. The 2.25+ branch renames to `beatBase`. If LilyPond 2.26 ships during Engrave's lifetime, the property name changes
- **Jazz swing 4/4 incantation**: `beamExceptions = #'()`, `baseMoment = #(ly:make-moment 1/4)`, `beatStructure = 1,1,1,1` -- clears the default half-bar grouping, beams eighths in pairs within beats

### Claude's Discretion
- Token scanner implementation details for ENSM-03 defaults (regex vs proper tokenizer)
- Rhythmic aligner implementation details for ENSM-05 omission (data structure for beat-position indexing)
- Exact Pydantic schema for the multi-instrument JSON blob in section-group fan-out
- Error handling when section-group generation fails for one group but succeeds for others
- How to handle the edge case where a section group has instruments with different note content (e.g., trumpet 1 solo while 2-4 have whole notes) -- still joint generation, but the comparison logic needs to handle sparse data

### Deferred Ideas (OUT OF SCOPE)
- **Phonetic enunciation system (v1.1)**: Tim Davies attack character notation (dah/tah/doo/bah). Requires mapping phonetic characters to LilyPond articulation combinations, which is subjective and style-dependent. Needs validation against Sam's actual charts. The LLM would need to make musical taste decisions per note -- not trustworthy until v1 produces real output for feedback
- **Cross-section coherence state**: sharing dynamic/articulation state between section groups within the same bar range. Rejected for v1 because it kills parallelism and the input data (MIDI velocities, audio descriptions) already provides cross-section coordination
- **Beat-aware articulation defaults**: quarter-note treatment varying by metric position (pickup notes, phrase-final notes). Rejected for v1 -- if a note needs non-default treatment, the LLM should mark it explicitly
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENSM-02 | System generates section parts jointly (e.g., all 4 trumpets in one LLM call) so articulations, dynamics, and beam groupings co-vary -- enabling convergent sight-reading | Section-group dispatch architecture (add `section_group` to `InstrumentSpec`, restructure `generate_from_midi` to group instruments, build per-group prompts scoped to section instruments) |
| ENSM-03 | System applies Tim Davies jazz articulation defaults: unmarked quarter notes are short, unmarked eighth notes are long, swing assumed unless marked "Straight 8s," staccato+accent not paired (redundant) | Token scanner post-processor using regex pattern matching on LilyPond note tokens; articulation shorthand syntax verified against LilyPond 2.24 docs |
| ENSM-05 | Section consistency rule: if all parts in a section have the same articulation, omit it (the default handles it) -- only mark departures from the section's collective default | Rhythmic aligner component that accumulates beat position via duration arithmetic, then cross-compares articulations at (bar, beat) coordinates across all parts in a section group |
| ENGR-05 | Parts include correct rhythmic notation and beaming per style conventions (jazz beaming for swing, straight beaming for Latin/rock) | LilyPond `\set Timing` properties (`beamExceptions`, `baseMoment`, `beatStructure`) emitted per section in score templates; `beam_style` enum resolves swing vs straight |
</phase_requirements>

## Summary

Phase 7 transforms Engrave's generation pipeline from per-instrument to per-section-group dispatch and adds two deterministic post-processing passes that enforce jazz articulation conventions. The phase spans three distinct technical domains: (1) restructuring the generation pipeline to group instruments into section groups (trumpets, trombones, saxes) that generate jointly while rhythm section instruments generate individually; (2) building a two-level post-processor -- a token scanner that applies ENSM-03 articulation defaults by note duration, followed by a rhythmic aligner that strips redundant articulations when all parts in a section group share the same mark at the same beat; and (3) configuring LilyPond beaming per musical style (swing vs straight) via template-level `\set Timing` commands.

The existing codebase provides strong foundations for all three. The `parse_instrument_blocks()` function already handles multi-instrument delimited LLM output. The `restate_dynamics()` function in `generator.py` demonstrates the exact regex token-walking pattern the ENSM-03 scanner will follow. The section-by-section architecture with per-section templates naturally accommodates per-section beaming style changes.

**Primary recommendation:** Build the token scanner (ENSM-03) first because it is purely local (no cross-part context needed) and the most independently testable. Then add section-group dispatch (ENSM-02) which restructures pipeline flow. Then build the rhythmic aligner (ENSM-05) which operates on section-group output. Finally, add beaming configuration (ENGR-05) as template-level changes.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-ly | 0.9.9 | LilyPond parsing/tokenization reference | Already a project dependency; used in Phase 2 for chunking. Provides `ly.lex` tokenizer as reference implementation, though CONTEXT.md leaves open whether to use regex or proper tokenizer |
| pydantic | 2.x (current) | Data models for section groups, articulation config | Already used throughout project for `CoherenceState`, `SectionNotation`, settings |
| pytest + pytest-asyncio | current | Test framework | Already configured in pyproject.toml with `asyncio_mode = "auto"` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | N/A | Regex-based token scanning for ENSM-03 | The token scanner pattern matches `restate_dynamics()` which already uses `re.compile` patterns for LilyPond token walking; proven pattern in the codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex token scanner | python-ly `ly.lex` tokenizer | `ly.lex` provides proper tokenization (handles strings, comments, Scheme blocks) but adds coupling to an external parser. Regex is simpler for the constrained problem of "find notes with specific durations and check/modify their articulations." Regex matches the existing `restate_dynamics()` pattern. Recommendation: **Use regex** -- the problem scope is narrow enough |
| Dict-based beat indexing | Named tuples / dataclasses | For the rhythmic aligner's (bar, beat) -> articulation mapping. Dict[tuple[int, float], str] is simple and sufficient. No library needed |

**No new dependencies required.** All functionality is implementable with existing project dependencies.

## Architecture Patterns

### Recommended Project Structure
```
src/engrave/
├── generation/
│   ├── pipeline.py          # Modified: section-group dispatch logic
│   ├── templates.py         # Modified: beaming commands in templates
│   ├── prompts.py           # Modified: scoped prompts for section groups
│   ├── coherence.py         # Modified: per-section-group coherence
│   └── section_groups.py    # NEW: section group resolution from preset
├── rendering/
│   ├── ensemble.py          # Modified: section_group field on InstrumentSpec
│   ├── generator.py         # Modified: beaming template output
│   └── articulation.py      # NEW: ENSM-03 token scanner + ENSM-05 rhythmic aligner
└── ...
```

### Pattern 1: Token Scanner (ENSM-03 Articulation Defaults)
**What:** Walk LilyPond tokens sequentially, match notes by duration, add/strip articulation marks.
**When to use:** Applying duration-based articulation defaults to generated LilyPond.
**Why this pattern:** Identical to the proven `restate_dynamics()` approach in `generator.py` (line 369-454) which already walks LilyPond token-by-token with regex matching for dynamic marks, multi-measure rests, and notes.

```python
# Source: Modeled on existing restate_dynamics() in src/engrave/rendering/generator.py
import re

# LilyPond note: pitch + optional accidentals + optional octave marks + duration
# In absolute mode: c, d, e, f, g, a, b + is/es variants + ' or , + digit(s) + dot
_NOTE_WITH_DURATION_RE = re.compile(
    r"([a-g](?:is|es|isis|eses)?[',]*)"  # pitch (group 1)
    r"(\d+\.?)"                           # duration (group 2): 4, 8, 2., etc.
    r"((?:-[.>^_-]|\\[a-z]+)*)"          # existing articulations (group 3)
)

# Articulation shorthand patterns (LilyPond 2.24 syntax)
_STACCATO = "-."
_ACCENT = "->"
_TENUTO = "--"
_MARCATO = "-^"

def apply_articulation_defaults(ly_source: str) -> str:
    """Apply ENSM-03 jazz articulation defaults to LilyPond source.

    Rules:
    1. Unmarked quarter notes get staccato (short default)
    2. Unmarked eighth notes keep no mark (long default)
    3. Staccato+accent -> keep accent only (accent subsumes)
    4. Swing assumed unless marked "Straight 8s" (handled by beaming)
    """
    # Implementation walks tokens similar to restate_dynamics()
    ...
```

### Pattern 2: Rhythmic Aligner (ENSM-05 Omission Rule)
**What:** For each section group, accumulate beat positions within bars by summing note durations, then compare articulations across parts at matching (bar, beat) coordinates.
**When to use:** After ENSM-03 defaults are applied, before final LilyPond output.

```python
from dataclasses import dataclass

@dataclass
class BeatEvent:
    """An articulation event at a specific rhythmic position."""
    bar: int
    beat: float  # 1.0, 1.5, 2.0, etc.
    articulations: list[str]  # ["-.", "->"] etc.
    is_rest: bool

def build_beat_map(ly_source: str) -> dict[tuple[int, float], BeatEvent]:
    """Parse LilyPond source into (bar, beat) -> BeatEvent mapping.

    Duration arithmetic:
    - 1 (whole) = 4 beats
    - 2 (half) = 2 beats
    - 4 (quarter) = 1 beat
    - 8 (eighth) = 0.5 beat
    - 16 (sixteenth) = 0.25 beat
    - Dotted: multiply by 1.5
    """
    ...

def apply_section_consistency(
    part_sources: dict[str, str],  # var_name -> ly content
) -> dict[str, str]:
    """Strip articulations where all sounding parts agree.

    Algorithm:
    1. Build beat map for each part
    2. For each (bar, beat) coordinate:
       a. Collect articulations from all sounding parts (skip rests)
       b. If all sounding parts have identical articulations -> strip from all
       c. If any differ -> keep all markings
    3. Return modified sources
    """
    ...
```

### Pattern 3: Section-Group Dispatch
**What:** Group `InstrumentSpec` objects by `section_group`, dispatch one LLM call per group (or individual instruments for ungrouped), fan out LilyPond + JSON per call.
**When to use:** Replacing the current per-instrument loop in `generate_from_midi()`.

```python
from engrave.rendering.ensemble import InstrumentSpec

def resolve_section_groups(
    instruments: tuple[InstrumentSpec, ...],
) -> list[list[InstrumentSpec]]:
    """Group instruments by section_group field.

    Returns list of groups where each group is either:
    - Multiple instruments sharing a section_group (e.g., 4 trumpets)
    - A single ungrouped instrument (e.g., piano)

    Order preserves score_order within groups and group order
    matches first instrument's score_order.
    """
    groups: dict[str | None, list[InstrumentSpec]] = {}
    for inst in instruments:
        key = inst.section_group  # None for ungrouped
        if key is None:
            # Each ungrouped instrument is its own "group"
            groups[f"_solo_{inst.variable_name}"] = [inst]
        else:
            groups.setdefault(key, []).append(inst)

    # Sort groups by first instrument's score_order
    return sorted(groups.values(), key=lambda g: g[0].score_order)
```

### Pattern 4: Beaming Template Commands
**What:** Emit `\set Timing.*` commands per section based on resolved `beam_style`.
**When to use:** In section template generation, before the music content.

```python
# LilyPond 2.24 verified syntax
SWING_BEAMING = """\
  \\set Timing.beamExceptions = #'()
  \\set Timing.baseMoment = #(ly:make-moment 1/4)
  \\set Timing.beatStructure = 1,1,1,1
"""

STRAIGHT_BEAMING = """\
  % Default LilyPond beaming (half-bar grouping in 4/4)
  \\unset Timing.beamExceptions
  \\unset Timing.baseMoment
  \\unset Timing.beatStructure
"""

def beaming_commands(beam_style: str) -> str:
    """Return LilyPond timing commands for the given style.

    Args:
        beam_style: "swing" or "straight"
    """
    if beam_style == "swing":
        return SWING_BEAMING
    return STRAIGHT_BEAMING
```

### Anti-Patterns to Avoid
- **Putting articulation rules in the LLM prompt:** The user decision is explicit -- LLM generates musical intent, post-processor applies notational conventions. Mixing them violates the clean separation principle and makes testing harder.
- **Using python-ly's full AST for the token scanner:** Overkill for the constrained problem. The token scanner only needs to find notes with durations and check/modify their articulations. Regex is simpler and matches the existing `restate_dynamics()` pattern.
- **Cross-section-group coherence sharing:** Rejected by user decision. Kills parallelism. Cross-section coordination comes from input data (MIDI, audio descriptions), not coherence state.
- **Over-engineering the beat position tracker:** LilyPond durations are explicit in the token stream. Duration-to-beats conversion is a simple lookup table, not music theory. Don't build a full rhythmic parser.
- **Generating separate JSON per instrument within a section group:** The user decision is explicit -- one JSON blob per section-group call containing all instruments. Splitting loses cross-instrument context that enables voicing coherence.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LilyPond note token regex | Custom grammar parser | Regex patterns modeled on `restate_dynamics()` | Proven pattern in the codebase; the problem is narrow enough for regex |
| Duration-to-beat conversion | Music theory library | Simple dict lookup: `{1: 4.0, 2: 2.0, 4: 1.0, 8: 0.5, 16: 0.25}` with dotted multiplier | Arithmetic, not music theory. LilyPond durations are always explicit in absolute mode |
| Section group resolution | Dynamic grouping logic | Preset-defined `section_group` field on `InstrumentSpec` | User decision: preset defines groups, not runtime analysis |
| Beaming configuration | Per-note beam brackets | LilyPond `\set Timing` properties | LilyPond's auto-beamer handles this natively; just configure it |
| Telemetry for staccato+accent resolution | Custom logging | Structured audit log from Phase 6 (same pattern as failure_log.py) | Reuse existing telemetry infrastructure |

**Key insight:** The post-processing pipeline operates on LilyPond text, not on an abstract music representation. This is intentional -- it keeps the LLM's output as the single source of truth and applies only narrow, well-defined, deterministic transforms. The coding agent must not build a full LilyPond-to-AST-to-LilyPond roundtrip.

## Common Pitfalls

### Pitfall 1: Articulation Shorthand Ambiguity
**What goes wrong:** LilyPond articulation shorthands use `-` as prefix (e.g., `-.` for staccato, `->` for accent, `--` for tenuto, `-^` for marcato). The `-` character also appears in ties (`~`), dynamics (`\f`), and other contexts.
**Why it happens:** Naive regex matching on `-` catches too many things.
**How to avoid:** The token scanner must anchor articulation matching to immediately follow a note-with-duration token. The regex should match `(pitch)(duration)(articulations*)` as a single group where articulations are the suffix `-[.>^_-]` or `\named` forms.
**Warning signs:** Tests pass but articulations appear in wrong places; ties get corrupted; dynamics get stripped.

### Pitfall 2: Dotted Duration Parsing
**What goes wrong:** A dotted quarter (`c4.`) adds 50% to duration (1.5 beats instead of 1). If the beat accumulator doesn't handle dots, the rhythmic aligner drifts out of alignment after the first dotted note.
**Why it happens:** The dot character `.` is also the staccato shorthand (`-.`). Context matters: `c4.` is a dotted quarter, `c4-.` is a staccato quarter.
**How to avoid:** The note regex must distinguish `c4.` (dot attached to duration = dotted) from `c4-.` (staccato articulation). The duration group captures the dot: `(\d+\.?)`. The articulation group is separate: `((?:-[.>^_-]|\\[a-z]+)*)`.
**Warning signs:** Beat positions drift; notes at the end of bars don't align; staccato marks disappear from dotted notes.

### Pitfall 3: Rest Handling in Section Consistency
**What goes wrong:** If one part has a rest while others have notes, treating the rest as "different articulation" means the omission rule never triggers.
**Why it happens:** Naive comparison includes rests as "no articulation" which differs from "has staccato."
**How to avoid:** User decision is explicit: rests are excluded from comparison. The aligner must check `is_rest` and skip that part's contribution at that beat position. Only compare articulations of sounding parts.
**Warning signs:** Articulations never get omitted even when all sounding parts agree; over-marked output.

### Pitfall 4: Bar Number Tracking
**What goes wrong:** LilyPond doesn't always have explicit bar markers. The rhythmic aligner must detect bar boundaries from duration accumulation (when total beats reach the bar length, increment bar number).
**Why it happens:** LilyPond uses `|` as an optional bar check, not a mandatory delimiter. Not all generated LilyPond includes them.
**How to avoid:** Track beat position as a running float. When `accumulated_beats >= beats_per_bar`, increment bar number and subtract `beats_per_bar` from accumulator. Use the time signature from coherence state to determine `beats_per_bar`.
**Warning signs:** Parts misalign after the first bar; articulation comparisons match wrong notes.

### Pitfall 5: Section Group Generation Failure Handling
**What goes wrong:** If one section group (e.g., trombones) fails generation while others succeed, the pipeline has partial output for that temporal section.
**Why it happens:** Network/LLM errors are independent per call. In per-instrument mode, one instrument failing is less impactful. In per-group mode, losing 4 trombones at once is more significant.
**How to avoid:** User decision area (Claude's discretion). Recommended: fail the entire temporal section if any group fails (matching existing pipeline behavior where section failure halts generation). Log which group failed for debugging.
**Warning signs:** ZIP output has some instruments missing in middle sections; misaligned section joins.

### Pitfall 6: LilyPond 2.24 vs 2.25+ Property Names
**What goes wrong:** `baseMoment` is renamed to `beatBase` in LilyPond 2.25+. Templates using the wrong name silently produce incorrect beaming.
**Why it happens:** Engrave targets LilyPond 2.24 but the user noted the rename for future-proofing.
**How to avoid:** Use `baseMoment` (correct for 2.24). Add a comment in the template noting the rename. If version detection is needed later, the `LILYPOND_VERSION` constant in `stylesheet.py` tracks the target version.
**Warning signs:** Beaming looks default (half-bar groups in 4/4) even when swing is set; no compilation error because LilyPond silently ignores unknown context properties.

### Pitfall 7: Multi-instrument Delimiter Parsing with Fewer Instruments
**What goes wrong:** `parse_instrument_blocks()` expects `% varName` markers. If the LLM generates a section group call with 4 trumpets but only returns 3 blocks (omitting trumpet 4), the pipeline must handle the missing instrument.
**Why it happens:** LLMs sometimes skip instruments, especially when one has only rests.
**How to avoid:** Already handled by the existing fallback in `pipeline.py` line 263: `blocks.get(var_name, "R1")` defaults missing instruments to a whole rest. The same pattern works for section-group calls.
**Warning signs:** Missing parts in output; silent failures.

## Code Examples

Verified patterns from the existing codebase and official LilyPond documentation:

### LilyPond Note Token Structure (Absolute Mode)
```
Pitch: [a-g] (required)
Accidentals: (is|es|isis|eses)? (optional)
Octave: [',]* (optional, required in absolute mode for unambiguous pitch)
Duration: \d+\.? (optional -- sticky from previous note)
Articulations: (-[.>^_-]|\\staccato|\\accent|\\tenuto|\\marcato)* (optional)
Dynamics: (\\ppp|\\pp|\\p|\\mp|\\mf|\\f|\\ff|\\fff)? (optional)

Examples:
  c'4-.     = middle C, quarter note, staccato
  bes''8->  = Bb two octaves up, eighth note, accent
  fis,2     = F#, octave below, half note, no articulation
  d4-.-^    = D, quarter, staccato + marcato (unusual combo)
  r4        = quarter rest (pitch is 'r', no articulations meaningful)
```
Source: [LilyPond 2.24 Notation Reference - Writing Pitches](https://lilypond.org/doc/v2.24/Documentation/notation/writing-pitches) and [List of Articulations](https://lilypond.org/doc/v2.24/Documentation/notation/list-of-articulations)

### Existing Token-Walking Pattern (from restate_dynamics)
```python
# Source: src/engrave/rendering/generator.py lines 369-454
# This is the EXACT pattern the ENSM-03 token scanner should follow.
# Key technique: pos-based scanning with re.match(pattern, source, pos)

pos = 0
while pos < len(source):
    # Try to match pattern at current position
    match = _PATTERN.match(source, pos)
    if match:
        # Process match, append to result
        result_parts.append(...)
        pos = match.end()
        continue

    # No pattern matched -- copy character as-is
    result_parts.append(source[pos])
    pos += 1

return "".join(result_parts)
```

### Jazz Swing Beaming (Verified LilyPond 2.24)
```lilypond
% Source: https://lilypond.org/doc/v2.24/Documentation/notation/beams
% Clears default half-bar grouping; beams eighths in pairs within beats
\set Timing.beamExceptions = #'()
\set Timing.baseMoment = #(ly:make-moment 1/4)
\set Timing.beatStructure = 1,1,1,1
```

### Straight Eighth Beaming (Default LilyPond Behavior)
```lilypond
% Source: LilyPond 2.24 default behavior
% Default 4/4 beaming groups eighths in half-bar pairs (4 eighths per group)
% To revert from swing: unset the overrides
\unset Timing.beamExceptions
\unset Timing.baseMoment
\unset Timing.beatStructure
```

### Duration-to-Beats Lookup Table
```python
# LilyPond duration number -> beat count in 4/4 time
DURATION_BEATS: dict[int, float] = {
    1: 4.0,    # whole note
    2: 2.0,    # half note
    4: 1.0,    # quarter note
    8: 0.5,    # eighth note
    16: 0.25,  # sixteenth note
    32: 0.125, # thirty-second note
}

def duration_to_beats(dur_num: int, dotted: bool) -> float:
    """Convert LilyPond duration number to beat count."""
    beats = DURATION_BEATS.get(dur_num, 1.0)
    if dotted:
        beats *= 1.5
    return beats
```

### Articulation Mark Shorthand Reference
```python
# Source: https://lilypond.org/doc/v2.24/Documentation/notation/list-of-articulations
# LilyPond 2.24 articulation shorthands (attached to notes with -)
ARTICULATION_SHORTHANDS = {
    "-.": "staccato",
    "->": "accent",
    "--": "tenuto",
    "-^": "marcato",
    "-!": "staccatissimo",
    "-_": "portato",  # tenuto + staccato combined
}

# Articulation marks eligible for ENSM-05 omission
# (Explicit allowlist per user decision -- dynamics are NEVER omitted)
OMISSION_ELIGIBLE = {"staccato", "accent", "tenuto", "marcato"}

# The shorthand patterns for regex matching:
# -. (staccato), -> (accent), -- (tenuto), -^ (marcato)
_ARTICULATION_RE = re.compile(r"-[.>^_!-]")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-instrument generation (17 calls) | Per-section-group generation (7 calls) | Phase 7 (this phase) | 59% fewer LLM calls; instruments in a section see each other's voicings during generation |
| No articulation post-processing | Deterministic ENSM-03 defaults + ENSM-05 omission | Phase 7 (this phase) | Professional jazz notation conventions applied consistently |
| Default LilyPond beaming only | Style-aware beaming (swing vs straight) | Phase 7 (this phase) | Correct rhythmic grouping per musical style |
| LilyPond 2.24 `baseMoment` | LilyPond 2.25+ `beatBase` | LilyPond 2.25 (development branch) | Property rename; Engrave uses 2.24 names, needs migration plan for 2.26 |

**Deprecated/outdated:**
- `baseMoment`: Still correct for LilyPond 2.24 (Engrave's target). Will be renamed to `beatBase` in stable LilyPond 2.26.

## Open Questions

1. **Phase 6 integration point for `beam_style` resolution**
   - What we know: `beam_style` is resolved from Phase 6 audio description + user hints before generation. The value is `swing` or `straight` per section.
   - What's unclear: Phase 6 is not yet implemented. How will the audio LM output indicate style (swing vs Latin vs rock)?
   - Recommendation: For now, default `beam_style = "swing"` for big band. Add a `beam_style` field to section metadata (or the coherence state) that Phase 6 will populate later. Make the beaming template commands driven by this field so they work correctly once Phase 6 provides real values.

2. **Sticky durations in LilyPond**
   - What we know: In LilyPond, a note without an explicit duration inherits the previous note's duration (e.g., `c'4 d' e'` means all three are quarter notes).
   - What's unclear: Does generated LilyPond always include explicit durations, or does the LLM use sticky durations?
   - Recommendation: The token scanner must track "current duration" state and apply it when a note lacks explicit duration. This is a small addition to the regex walker. The prompt already asks for absolute pitch mode but doesn't mandate explicit durations on every note. The token scanner should handle both cases defensively.

3. **Section-group-scoped coherence state**
   - What we know: Per user decision, each section group gets coherence from its own previous temporal section. No cross-group sharing.
   - What's unclear: How should the existing `CoherenceState` model be extended? One state per group? Or filter the existing per-section state to group-relevant instruments?
   - Recommendation: Maintain a `dict[str, CoherenceState]` keyed by section group name. Initialize each from the analysis (same as now). Update each from its own group's output. This keeps the existing `CoherenceState` model unchanged and only changes how many instances are maintained.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/unit/test_articulation.py tests/unit/test_section_groups.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |
| Estimated runtime | ~3 seconds (unit), ~10 seconds (full) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENSM-02 | Section parts generated jointly per section group | integration | `pytest tests/integration/test_section_group_generation.py -x` | No -- Wave 0 gap |
| ENSM-03 (rule 1) | Unmarked quarter notes get staccato | unit | `pytest tests/unit/test_articulation.py::test_quarter_note_default_staccato -x` | No -- Wave 0 gap |
| ENSM-03 (rule 2) | Unmarked eighth notes stay unmarked (long) | unit | `pytest tests/unit/test_articulation.py::test_eighth_note_no_mark -x` | No -- Wave 0 gap |
| ENSM-03 (rule 3) | Staccato+accent resolves to accent only | unit | `pytest tests/unit/test_articulation.py::test_staccato_accent_resolution -x` | No -- Wave 0 gap |
| ENSM-03 (rule 4) | Swing assumed (beaming default) | unit | `pytest tests/unit/test_beaming.py::test_default_swing_beaming -x` | No -- Wave 0 gap |
| ENSM-05 | Section consistency omission when all parts agree | unit | `pytest tests/unit/test_articulation.py::test_section_consistency_omission -x` | No -- Wave 0 gap |
| ENSM-05 (rests) | Rests excluded from comparison | unit | `pytest tests/unit/test_articulation.py::test_rests_excluded_from_comparison -x` | No -- Wave 0 gap |
| ENSM-05 (dynamics) | Dynamics never omitted | unit | `pytest tests/unit/test_articulation.py::test_dynamics_never_omitted -x` | No -- Wave 0 gap |
| ENGR-05 (swing) | Jazz swing beaming emitted in template | unit | `pytest tests/unit/test_beaming.py::test_swing_beaming_commands -x` | No -- Wave 0 gap |
| ENGR-05 (straight) | Straight beaming for Latin/rock sections | unit | `pytest tests/unit/test_beaming.py::test_straight_beaming_commands -x` | No -- Wave 0 gap |
| ENGR-05 (mid-chart) | Beaming changes per section | integration | `pytest tests/integration/test_section_group_generation.py::test_beaming_changes_per_section -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `pytest tests/unit/test_articulation.py tests/unit/test_section_groups.py tests/unit/test_beaming.py -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~3 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_articulation.py` -- covers ENSM-03 (all 4 rules) and ENSM-05 (omission, rest exclusion, dynamics protection)
- [ ] `tests/unit/test_section_groups.py` -- covers section group resolution from preset, InstrumentSpec.section_group field
- [ ] `tests/unit/test_beaming.py` -- covers ENGR-05 (swing/straight beaming commands, template emission)
- [ ] `tests/integration/test_section_group_generation.py` -- covers ENSM-02 (joint generation dispatch, fan-out, coherence per group)

*(No new framework install needed -- pytest and pytest-asyncio already configured)*

## Sources

### Primary (HIGH confidence)
- [LilyPond 2.24 Notation Reference - Beams](https://lilypond.org/doc/v2.24/Documentation/notation/beams) - Verified `baseMoment`, `beatStructure`, `beamExceptions` syntax
- [LilyPond 2.24 - List of Articulations](https://lilypond.org/doc/v2.24/Documentation/notation/list-of-articulations) - Verified shorthand articulation syntax (`-.`, `->`, `--`, `-^`)
- [LilyPond 2.24 - Expressive Marks](https://lilypond.org/doc/v2.24/Documentation/notation/expressive-marks-attached-to-notes) - Verified articulation attachment to notes
- Existing codebase: `src/engrave/rendering/generator.py` `restate_dynamics()` - Token-walking regex pattern reference
- Existing codebase: `src/engrave/generation/pipeline.py` - Current per-instrument dispatch architecture
- Existing codebase: `src/engrave/generation/templates.py` `parse_instrument_blocks()` - Multi-instrument parsing already works
- Existing codebase: `src/engrave/rendering/ensemble.py` `InstrumentSpec` - Data model for instruments

### Secondary (MEDIUM confidence)
- [LilyPond Changes v2.25](https://lilypond.org/doc/v2.25/Documentation/changes-big-page.html) - `baseMoment` -> `beatBase` rename confirmed in development branch
- [python-ly GitHub](https://github.com/frescobaldi/python-ly) - Tokenization capabilities available if regex proves insufficient

### Tertiary (LOW confidence)
- None -- all findings verified against official documentation or existing codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; all patterns exist in codebase
- Architecture: HIGH - Direct extension of existing pipeline with well-defined insertion points; user decisions are exceptionally detailed
- Pitfalls: HIGH - Articulation/duration parsing pitfalls identified from LilyPond syntax analysis and existing `restate_dynamics()` experience

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain -- LilyPond 2.24 syntax is frozen)
