# Phase 7: Convergent Sight-Reading & Ensemble Intelligence - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Section parts are generated jointly so musicians within a section independently arrive at the same musical interpretation on first read. This phase restructures the generation pipeline from per-instrument to per-section-group calls, adds a deterministic articulation post-processor implementing Tim Davies jazz defaults and the section consistency omission rule, and applies style-aware beaming via LilyPond template settings. The phonetic enunciation system (dah/tah/doo attack character) is deferred to v1.1.

</domain>

<decisions>
## Implementation Decisions

### Articulation Defaults (ENSM-03)
- Implement the 4 ENSM-03 rules only for v1: unmarked quarter = short (staccato), unmarked eighth = long (no mark), swing assumed unless "Straight 8s," staccato+accent never paired
- **Post-processing only** — deterministic transforms on generated LilyPond, no articulation rules in the LLM prompt. Clean separation: LLM generates musical intent, post-processor applies notational conventions
- **Purely syntactic** — apply rules by note duration alone, no beat-position or phrase-boundary awareness. If a specific note needs different treatment (e.g., pickup note should be long), that's the LLM's job to mark explicitly
- **Staccato+accent resolution**: keep accent, strip staccato. Accent subsumes staccato in jazz brass. Log the resolution as telemetry (same structured audit log as Phase 6) for TUNE-02 feedback loop, not as user-facing warning
- Phonetic enunciation system (attack character notation) deferred to v1.1 — requires validation against Sam's actual charts and subjective style-dependent mappings

### Joint Generation (ENSM-02)
- **Preset-defined section groups**: `InstrumentSpec` gets a `section_group` field. Big band preset defines: trumpets (4), trombones (4), saxes (5) as joint groups. Rhythm instruments (piano, guitar, bass, drums) are ungrouped (`section_group = None`) and keep per-instrument generation
- **Fan-out unit is the section group**: 3 section-group calls + 4 individual calls = 7 calls per section, each with (LilyPond, JSON) fan-out = 14 parallel requests. Down from 17 instruments x 2 = 34
- **Existing delimiter pattern unchanged**: `parse_instrument_blocks()` already handles multi-instrument delimited output. Joint calls scope the template variables and MIDI content to only the instruments in the group. Same parsing code, more focused generation unit
- **Per-call JSON for Phase 5.1 fan-out**: one JSON blob per section-group call containing all instruments' notation events (array of `{"instrument": "trumpet_1", "measures": [...]}` objects). Both LilyPond and JSON requests share the same prefix cache. Never split into per-instrument JSON requests — that loses the cross-instrument context
- **Section-sequential coherence only**: each section group gets coherence state from its own previous temporal section. No cross-section-group sharing within the same bar range. Cross-section coordination comes from input data (MIDI velocities, audio description, user hints), not coherence state. This preserves parallelism: trumpets, trombones, and saxes for the same bar range generate concurrently
- **Prompt context scoped per group**: MIDI tokens, RAG examples, and coherence state scoped to the section group's instruments. Musically coherent context — the LLM sees trumpet voicings when writing trumpets, not drum patterns

### Section Consistency Rule (ENSM-05)
- **Strictly identical match**: all parts in a section must have the exact same articulation on the exact same beat position for omission to apply. If any part differs, all keep their markings
- **Rests are absent from comparison**: if trumpet 4 rests on beat 1 while trumpets 1-3 have staccato, trumpet 4 is excluded from the comparison (not treated as "different")
- **Dynamics always printed**: omission rule applies only to articulation marks (staccato, accent, tenuto, marcato). Dynamics, tempo markings, expression text, and rehearsal marks are always printed on every part. Explicit allowlist of mark types eligible for omission
- **No visual indicator of omission**: no "simile" or "sect." markings. Absence of marking IS the indicator — that's the Tim Davies convention. Players know the defaults before they sit down
- **Processing pipeline order**: LLM output -> apply ENSM-03 defaults -> apply ENSM-05 omission rule -> final LilyPond. Each step operates on complete data from the previous step

### Style-Aware Beaming (ENGR-05)
- **Template-level, not post-processing**: beaming is controlled by `\set Timing.beamExceptions`, `\set Timing.baseMoment`, `\set Timing.beatStructure` in the LilyPond score template. Not per-note beam brackets
- **Resolved `beam_style` enum**: `swing` or `straight` per section. Latin IS straight eighth beaming — no separate category. Resolved from Phase 6 audio description + user hints before generation. Default to `swing` for big band if unspecified
- **Per-section, supports mid-chart changes**: each section's template emits the correct `\set Timing` commands. Swing heads, Latin bridge, swing out-head all work naturally with the existing section-by-section architecture
- **Section-group-uniform**: all instruments in a section group share the same `beam_style`. Beaming is a style convention, not a per-instrument choice. The `\set Timing` commands emit at the staff-group level
- **LilyPond version note**: Engrave targets LilyPond 2.24 which uses `baseMoment`. The 2.25+ branch renames to `beatBase`. If LilyPond 2.26 ships during Engrave's lifetime, the property name changes
- **Jazz swing 4/4 incantation**: `beamExceptions = #'()`, `baseMoment = #(ly:make-moment 1/4)`, `beatStructure = 1,1,1,1` — clears the default half-bar grouping, beams eighths in pairs within beats

### Claude's Discretion
- Post-processor implementation: AST vs regex vs token scanner approach for articulation scanning
- Exact Pydantic schema for the multi-instrument JSON blob in section-group fan-out
- Error handling when section-group generation fails for one group but succeeds for others
- How to handle the edge case where a section group has instruments with different note content (e.g., trumpet 1 solo while 2-4 have whole notes) — still joint generation, but the comparison logic needs to handle sparse data

</decisions>

<specifics>
## Specific Ideas

- "The LLM's job is 'generate musical intent' and a deterministic layer's job is 'apply notational conventions'" — clean separation principle throughout
- "If even one part differs, all parts keep their markings" — sight-reading safety over notation elegance
- "The whole reason you generate four trumpets together is so the LLM can write correct voicings" — joint generation is about musical coherence, not just efficiency
- The fan-out restructuring from Phase 5.1 is a natural fit: same prefix-cache pattern, same delimiter parsing, just scoped to section groups instead of individual instruments
- Sam can validate ENSM-03 rules at the piano in five minutes: "Do your players read short quarters and long eighths as default?" — ship the four rules, collect feedback, build the phonetic layer when you know what's actually missing
- Professional big band publishers (Sierra, Kendor, UNC Jazz Press) always print dynamics on every part — omission rule is articulation-only

</specifics>

<deferred>
## Deferred Ideas

- **Phonetic enunciation system (v1.1)**: Tim Davies attack character notation (dah/tah/doo/bah). Requires mapping phonetic characters to LilyPond articulation combinations, which is subjective and style-dependent. Needs validation against Sam's actual charts. The LLM would need to make musical taste decisions per note — not trustworthy until v1 produces real output for feedback
- **Cross-section coherence state**: sharing dynamic/articulation state between section groups within the same bar range. Rejected for v1 because it kills parallelism and the input data (MIDI velocities, audio descriptions) already provides cross-section coordination
- **Beat-aware articulation defaults**: quarter-note treatment varying by metric position (pickup notes, phrase-final notes). Rejected for v1 — if a note needs non-default treatment, the LLM should mark it explicitly

</deferred>

---

*Phase: 07-convergent-sight-reading-ensemble-intelligence*
*Context gathered: 2026-02-24*
