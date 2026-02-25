# Phase 4: Rendering & Output Packaging - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform compiled LilyPond source (concert pitch) into professional output: a full conductor score PDF, individual transposed part PDFs for all instruments, and a ZIP package containing PDFs, LilyPond source files, and MIDI. This phase implements the big band ensemble preset (ENSM-01), part transposition at render time (LILY-03 → ENGR-02), rehearsal infrastructure (ENGR-03, ENGR-04), chord symbols on rhythm section parts (ENSM-04), and output packaging (FNDN-06, ENGR-09).

Phase 4 does NOT include: cue notes (Phase 8), page turn optimization (Phase 8), repeat/coda navigation marks (Phase 8), style-aware beaming (Phase 7), joint section generation (Phase 7), or the web UI (Phase 10).

</domain>

<decisions>
## Implementation Decisions

### Conductor Score Layout
- Paper: tabloid (11x17") landscape as default, configurable via engrave.toml
- Bracketing: section-level brackets per SCORING_GUIDE.md — Saxophones bracket, Trumpets bracket, Trombones bracket, Rhythm Section brace (with curly brace on piano grand staff)
- Empty staves: hide empty staves on all systems except the first (which always shows all instruments)
- Pitch: concert pitch only — never generate a transposed conductor score
- Chord symbols: display above the top staff (Alto Sax 1 line) on the conductor score, in addition to rhythm section parts

### Part Extraction & Transposition
- Transposition mechanism: LilyPond's `\transpose` command applied at render time — concert-pitch music is the single source of truth
- File architecture: shared music-definitions.ly containing all concert-pitch content, with separate part-{instrument}.ly files that `\include` the shared music and apply `\transpose`
- Paper: letter (8.5x11") portrait as default, configurable (A4 option) via engrave.toml
- Transposition verification: round-trip check — transpose to reading key, transpose back to concert, diff against original to catch any bugs
- Transposition table: use the exact table from docs/SCORING_GUIDE.md (Alto/Bari = Eb, Tenor/Trumpet = Bb, Trombone/Bass Trombone = C in bass clef, Rhythm = C)

### Rehearsal Marks & Multi-bar Rests
- Rehearsal marks: sequential letters (A, B, C...) at structural landmarks, with A always anchored at the start of the head
- Section names: optional secondary text below the letter mark (e.g., "Swing" or "Shout Chorus" below [B])
- Studio mode: when flagged (via user hint or config), switch to bar numbers on every measure with no rehearsal letters — for recording session use
- Multi-bar rests: traditional H-bar notation (LilyPond's `\compressFullBarRests`), number above horizontal bar
- Multi-bar rest breaks: always break multi-bar rests at rehearsal marks — never show a monolithic rest spanning a structural boundary
- Dynamic restatement: always restate the current dynamic at any entrance following 2+ bars of rest — this rule aligns with the multi-bar rest consolidation threshold (one unified rule)
- Measure numbers: display at the start of every system in parts; also display on multi-bar rest glyphs

### ZIP Packaging
- Structure: flat with prefixes — all files at ZIP root (score.pdf, part-trumpet-1.pdf, part-alto-sax-1.pdf, music-definitions.ly, part-trumpet-1.ly, output.mid, etc.)
- Naming: {song-title}-{YYYY-MM-DD}.zip (slugified song title + generation date)
- Contents: always include all outputs — conductor score PDF, all 17 instrument part PDFs, all .ly source files, MIDI file
- No user selection of parts in v1 — all parts always included

### Claude's Discretion
- Staff sizes and spacing for conductor score vs parts
- Exact LilyPond stylesheet/layout block parameters
- Font choices for rehearsal marks, measure numbers, and text annotations
- How to derive song title from input (MIDI metadata, filename, user hint)
- Error handling when LilyPond compilation fails during part extraction
- Tempo/style text formatting at top of parts

</decisions>

<specifics>
## Specific Ideas

- The scoring guide (docs/SCORING_GUIDE.md) is the authoritative reference for all engraving conventions — Phase 4 implementation should follow it exactly
- Conductor score should follow standard big band score order: Saxes (AATBT) → Trumpets (1-4) → Trombones (1-3, Bass) → Rhythm (Piano, Guitar, Bass, Drums)
- Tim Davies principle: mark only departures from default — this applies to dynamics (don't repeat ff every 4 bars) and articulations (section defaults handle common cases)
- The shared music-definitions.ly + per-part .ly architecture enables downstream editing in Frescobaldi or any text editor
- Round-trip transposition verification is a safety net — if LilyPond's `\transpose` ever produces unexpected results, the diff catches it before output

</specifics>

<deferred>
## Deferred Ideas

- Cue notes after 8+ bars rest — Phase 8 (ENGR-06)
- Page turn optimization (turns at rests only) — Phase 8 (ENGR-10)
- Repeat signs, D.S. al Coda, first/second endings — Phase 8 (ENGR-07)
- Chord chart / lead sheet output — Phase 8 (ENGR-08)
- Style-aware beaming (jazz vs straight) — Phase 7 (ENGR-05)
- Joint section generation for convergent sight-reading — Phase 7 (ENSM-02)
- Part selection/filtering (--parts flag) — could be added later if needed

</deferred>

---

*Phase: 04-rendering-output-packaging*
*Context gathered: 2026-02-24*
