# Phase 3: MIDI-to-LilyPond Generation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Core code generation pipeline: user provides a MIDI file (type 0 or type 1), the system produces compilable LilyPond source code via RAG-augmented LLM. Generation is section-by-section (4-8 bars) with coherence state passing. All music is stored internally in concert pitch. This phase delivers FNDN-01, LILY-01, LILY-02, LILY-03, LILY-04.

Rendering, transposed parts, and output packaging belong to Phase 4. Audio input belongs to Phase 5.

</domain>

<decisions>
## Implementation Decisions

### MIDI Track Handling
- When MIDI tracks lack instrument metadata (common in type 0): warn user about ambiguity, offer option to label tracks with instrument assignments, but generate as generic treble/bass clef parts if user does not label
- Support both MIDI type 0 (single track, interleaved) and type 1 (multi-track) files
- User labeling is optional, not blocking -- generation proceeds either way

### Section-by-Section Generation
- Generate in 4-8 bar sections with full musical coherence state passing between sections
- Coherence state carries forward: key signature, time signature, tempo, dynamics, articulation style, voicing patterns, rhythmic density -- full musical context, not just structural facts
- Richer context means larger prompt overhead per section, but continuity between sections is critical for usable output

### Failure Handling
- If a section fails compilation even after the Phase 1 retry loop (5 attempts): halt the entire generation
- No partial output with gaps -- user gets a complete result or a failure report
- Structured failure log for every compilation failure: MIDI input pattern, prompt sent, LilyPond error, retry attempts. This feeds v2 fine-tuning (TUNE-02)

### Concert Pitch Storage
- All LilyPond source generated and stored in concert pitch
- No transposition logic in this phase -- transposition is deterministic and belongs to Phase 4 rendering

### Claude's Discretion
- MIDI parsing and tokenization approach (how MIDI events become prompt input)
- Prompt template design and context window budget allocation between MIDI tokens, RAG examples, and coherence state
- Section boundary detection strategy (structural cues vs fixed-length chunks)
- RAG query formulation (how MIDI content maps to retrieval queries)
- Coherence state schema design (exact fields and serialization)

</decisions>

<specifics>
## Specific Ideas

- User wants to get to demos quickly -- this phase should be practical and functional, not over-engineered. Best-guess engineering decisions are fine; iterate after seeing output
- The structured failure log is explicitly motivated by TUNE-02 (v2 fine-tuning on error patterns) -- make the log format machine-readable from the start
- Generic parts without instrument labeling should still be musically sensible (correct clef for pitch range, reasonable staff assignments)

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-midi-to-lilypond-generation*
*Context gathered: 2026-02-24*
