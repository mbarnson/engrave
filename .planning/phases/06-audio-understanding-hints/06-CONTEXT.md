# Phase 6: Audio Understanding & Hints - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

The system extracts musical meaning beyond pitch and rhythm from audio via audio LM, and accepts natural language user hints that guide and override generation. This phase delivers the `describe` pipeline stage (Stage 3) and the hint ingestion system. It does NOT cover audio ingestion, source separation, or MIDI transcription (Phase 5), nor joint section generation or articulation defaults (Phase 7).

Requirements: AUDP-03 (structured audio descriptions), AUDP-04 (user hints with authoritative override).

</domain>

<decisions>
## Implementation Decisions

### Audio Description Schema
- **Two-tier structure:** track-level metadata + per-section annotations
- **Track-level fields:** tempo (BPM, variable flag), time signature, key (root + mode), instrument presence list, style tags, overall energy arc
- **Per-section fields:** label (intro/verse-1/chorus-1/etc.), start/end time, key (if changes), active instruments list, texture descriptor (free text: "solo piano", "full ensemble block chords"), dynamics (mf/ff/etc.), notes (nullable free text escape valve for observations that don't fit other fields)
- **No confidence scores.** Audio LM outputs are treated as suggestions with no self-assessed confidence. When MIDI analysis and audio LM disagree, the disagreement itself is the signal -- two independent methods failing to converge. Don't decorate unreliable data with unreliable meta-data
- **Section boundaries come from MIDI** (Phase 3's `midi/sections.py`), NOT from audio LM timestamps. Audio LM receives bar-based section boundaries and labels each one. The audio LM's job is labeling (style, texture, dynamics), not boundary detection
- **Per-section `notes` field** is separate from `texture`. Texture describes musical texture ("walking bass under trumpet melody"). Notes is a catch-all for stray observations ("sounds like a Basie arrangement", "drummer on brushes"). Nullable -- usually empty

### Audio LM Output Mode
- **Model-dependent dual path:** local Qwen3-Omni-Instruct produces JSON via structured prompting with Pydantic validation on output. Cloud Gemini 3 Flash uses schema-enforced JSON via `response_mime_type="application/json"` + `response_schema`
- The `Describer` protocol abstracts the difference, same pattern as `Transcriber` in Phase 5
- Audio LM's purpose: structure and context, NOT note accuracy. High-value outputs are things like "this is a 12-bar blues in Bb" or "saxophone takes melody while piano comps" -- constraints that help the generation LLM interpret noisy MIDI

### Hint Language & Parsing
- **Free text, no DSL.** Sam is a musician, not a programmer. The LLM is the parser -- no structured markers, no regex extraction for v1
- **CLI input:** `--hints` flag accepts either inline text or a file path (auto-detect: if path exists, read file; otherwise treat as inline text). File path supports batch runs and benchmarking with different hint sets
- **Web UI input:** a textarea. "Tell us anything about this recording that would help." Sam types freeform
- **Conventions the LLM recognizes** (documented, not enforced): bar references ("bar 17", "m. 17"), section labels ("in the bridge", "chorus 2"), instrument directives ("piano is comping"), correction hints ("that's a Db, not D natural"), style/arrangement ("swing eighths", "shout chorus")
- **No hint routing to sections.** The full hint block goes into every section's generation prompt. Sam's hints are ~200 tokens; prompt budget is 32K. The generation LLM naturally ignores irrelevant hints per section
- **No echo/confirmation.** Hints flow silently into the prompt. Interpretation is logged for audit only (visible in verbose/debug mode). No iterative hint-editing loop
- **Fresh each run.** No application-level hint persistence. The `.hints` sidecar file is the user's persistence mechanism via the filesystem

### Conflict Resolution
- **Three-tier priority, hardcoded (not configurable):**
  1. User hints -- always authoritative ("if Sam says Db, it's Db")
  2. Audio description -- structural observations from audio LM
  3. MIDI transcription -- treated as noisy suggestion, lowest authority
- **Implementation is prompt construction, not a merge algorithm.** The generation prompt labels each source with its authority level: DEFINITIVE (user hints), CONTEXTUAL (audio analysis), RAW INPUT (MIDI). The generation LLM reconciles based on musical context
- **When MIDI and audio LM disagree (no user hint):** both go into the prompt with weighted framing. MIDI analysis is grounded in note data (Krumhansl-Kessler chroma correlation). Audio LM guessed from a spectrogram. The LLM is told which is more grounded. Most disagreements are enharmonic/modal ambiguities resolvable from musical context
- **Self-contradictory hints pass through verbatim.** "Key of Bb" and "key of C" in the same block probably means different sections. The generation LLM has section context to interpret correctly. Don't throw away information with "last one wins"
- **Audit log:** structured JSON, per-field override tracking only (not per-note). Fields: {field, midi_value, audio_value, hint_value, resolved_to, source}. Machine-readable, queryable via jq. Human-readable rendering is a future web UI concern, not a log format
- **Disagreement warnings:** when MIDI analysis and audio LM disagree, log it. Future web UI can surface "Audio says Bb, MIDI says B -- consider adding a key hint." This is a disagreement between two systems, not a threshold on one system's self-assessment

### Integration with Generation
- **Audio description injected as natural language summary**, not raw JSON. A template converts structured fields to readable sentences per section: "Full ensemble in Bb, swing feel at 142 BPM, trumpet has melody, dynamics forte." JSON stays in audit log and job artifacts
- **Prompt-only context.** Audio description is observed context (from input analysis). Coherence state tracks generated context (from LLM output). Don't mix them. Per-section audio labels are injected fresh; coherence state carries key/harmony/articulation consistency from generated output
- **Same three-tier template always**, even for pure MIDI input (no audio). When no audio exists, the CONTEXTUAL section is empty/absent. Consistent prompt structure regardless of input type
- **Prompt structure per section:** compact global header (tempo, key, style) + per-section block with audio description summary + user hints (full block) + current section MIDI data + coherence state summary from previous sections

### Claude's Discretion
- Exact Pydantic model field types and validation rules for AudioDescription
- Natural language template wording for prompt injection
- Describer protocol API design details
- Audit log storage format (file per run, append log, etc.)
- How to handle audio LM errors/timeouts (retry vs skip with warning)

</decisions>

<specifics>
## Specific Ideas

- "The audio LLM doesn't need to be right about notes -- that's the AMT's job. It needs to be right about musical structure and context."
- "This is a 12-bar blues in Bb" or "saxophone takes melody while piano comps" are the high-value outputs -- they constrain the downstream LLM's interpretation of noisy MIDI
- "Sounds like a Basie arrangement" is a legitimate texture observation the audio LM might produce that genuinely helps the generation LLM
- "Trumpet is muted in chorus 1. Piano has a fill in bar 24." -- example of natural language hints that Sam would actually write
- "The intro is rubato, piano only. Tempo locks in at bar 5 when bass enters. Horns are bucket-muted in verse 1. The sax solo over the bridge changes is Bb tenor, not alto." -- realistic hint paragraph showing the kind of free-text the system should handle
- For the web UI (Phase 10): a textarea labeled "Tell us anything about this recording that would help"

</specifics>

<deferred>
## Deferred Ideas

- **STACK.md update:** GPT-4/4o references in code gen section should update to GPT-5.2 Thinking/Pro
- **Per-note override tracking** in the audit log -- belongs in Phase 9 evaluation pipeline
- **Human-readable conflict reports** rendered from structured JSON -- future web UI feature (Phase 10)
- **Hint echo/interpretation confirmation** -- explicitly rejected for v1 (creates iterative editing UX trap), but could be a web UI enhancement if users request it
- **Hint routing to specific sections** via LLM pre-pass -- rejected for v1 (adds fragile routing step, typical hints are tiny), revisit only if hint documents become very long

</deferred>

---

*Phase: 06-audio-understanding-hints*
*Context gathered: 2026-02-24*
