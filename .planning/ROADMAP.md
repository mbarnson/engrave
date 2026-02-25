# Roadmap: Engrave

## Overview

Engrave transforms audio recordings, MIDI files, and YouTube URLs into publication-quality, transposed sheet music parts. The roadmap follows a MIDI-first strategy: prove the LilyPond code generation pipeline works with clean MIDI input before layering on audio complexity. The pipeline builds outward from the core code generation engine (Phase 1-3), adds audio input paths (Phase 4-5), tackles the hard differentiator of convergent sight-reading (Phase 6), polishes engraving output for real rehearsal use (Phase 7), adds automated quality evaluation (Phase 8), and delivers the web interface last once the pipeline is solid (Phase 9).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Project Scaffolding & Inference Router** - Python project structure, LLM multi-provider routing, LilyPond installation, compile-check-fix loop (completed 2026-02-24)
- [x] **Phase 2: RAG Corpus & Retrieval** - Ingest open-source LilyPond scores, build ChromaDB index, phrase-level chunking, metadata-filtered retrieval (completed 2026-02-25)
- [x] **Phase 3: MIDI-to-LilyPond Generation** - Core code generation from MIDI input via RAG-augmented LLM, section-by-section with coherence state, concert-pitch storage (completed 2026-02-25)
- [x] **Phase 4: Rendering & Output Packaging** - LilyPond-to-PDF rendering, conductor score, extracted transposed parts, ZIP packaging with LilyPond source (completed 2026-02-25)
- [x] **Phase 5: Audio Input Pipeline** - Audio file ingestion, YouTube URL extraction, Demucs source separation, Basic Pitch MIDI transcription (completed 2026-02-25)
- [ ] **Phase 6: Audio Understanding & Hints** - Audio LM structured descriptions, natural language hint processing, user intent as authoritative override
- [ ] **Phase 7: Convergent Sight-Reading & Ensemble Intelligence** - Joint section-part generation, Tim Davies articulation defaults, section consistency rules, big band preset
- [ ] **Phase 8: Engraving Polish** - Cue notes, page turns at rests, chord charts/lead sheets, repeat/coda navigation, style-aware beaming
- [ ] **Phase 9: Evaluation Pipeline** - Automated structural diff, audio envelope comparison, visual PDF comparison, end-to-end quality reports
- [ ] **Phase 10: Web UI** - Single-page FastAPI + HTML/JS interface with drag-and-drop upload, output options, and Engrave button

## Phase Details

### Phase 1: Project Scaffolding & Inference Router
**Goal**: Developer can invoke LLM completions through a unified multi-provider interface, and LilyPond source compiles to PDF with automatic error recovery
**Depends on**: Nothing (first phase)
**Requirements**: FNDN-04, FNDN-05
**Success Criteria** (what must be TRUE):
  1. Running a Python script can send a prompt to Anthropic API, OpenAI API, and LMStudio local endpoint via a single unified interface (LiteLLM) and receive completions from each
  2. A deliberately broken LilyPond file triggers the compile-check-fix retry loop, which feeds the error back to the LLM and produces a compilable result within 5 attempts
  3. LilyPond is installed and `lilypond --version` succeeds from the project environment
  4. Project runs with `uv`, linting passes with `ruff`, and a basic test suite executes
**Plans:** 2/2 plans complete

Plans:
- [ ] 01-01-PLAN.md -- Project scaffolding, config system, inference router, CLI entry point
- [ ] 01-02-PLAN.md -- LilyPond compiler wrapper, error parser, compile-fix retry loop, Gherkin tests

### Phase 2: RAG Corpus & Retrieval
**Goal**: The system can retrieve relevant LilyPond examples from a curated corpus to provide few-shot context for code generation
**Depends on**: Phase 1
**Requirements**: CORP-01, CORP-02, CORP-03, CORP-04
**Success Criteria** (what must be TRUE):
  1. Mutopia Project LilyPond scores are ingested and stored as (LilyPond source, MIDI, structured text description) triples in ChromaDB
  2. PDMX MusicXML scores are converted to LilyPond via musicxml2ly and indexed in the same corpus
  3. A retrieval query for "big band trumpet section, swing style" returns relevant LilyPond phrase examples ranked by similarity
  4. Corpus is chunked at phrase level (4-8 bars), expanding 2K+ source scores into 10K+ retrievable examples
  5. Retrieval filters by structured metadata (instrument family, ensemble type, style, musical context)
**Plans:** 4/4 plans complete

Plans:
- [ ] 02-01-PLAN.md -- Corpus foundation: data models, ChromaDB store, configurable embeddings, config extension
- [ ] 02-02-PLAN.md -- Parsing and chunking: boundary detection, music-aware chunker, metadata extraction, description templating
- [ ] 02-03-PLAN.md -- Ingestion pipeline: shared pipeline, Mutopia adapter, PDMX adapter, MIDI injection
- [ ] 02-04-PLAN.md -- Retrieval interface: hybrid scoring, public API, CLI corpus command

### Phase 3: MIDI-to-LilyPond Generation
**Goal**: User can provide a MIDI file and receive LilyPond source code that compiles successfully, with music stored in concert pitch and generated section-by-section
**Depends on**: Phase 1, Phase 2
**Requirements**: FNDN-01, LILY-01, LILY-02, LILY-03, LILY-04
**Success Criteria** (what must be TRUE):
  1. User provides a MIDI type 0 or type 1 file, and the system produces compilable LilyPond source code that represents the musical content
  2. Generation uses RAG-retrieved few-shot examples plus MIDI tokens plus structured description to produce LilyPond via LLM
  3. Scores are generated in 4-8 bar sections with coherence state passing (key, articulations, dynamics, voicing patterns) maintaining consistency across sections
  4. All music is stored internally in concert pitch -- no transposed pitch in the intermediate representation
  5. First-attempt LilyPond compilation success rate exceeds 90% across test corpus (before retry loop)
**Plans:** 3/3 plans complete

Plans:
- [x] 03-01-PLAN.md -- MIDI subsystem: loader, analyzer, tokenizer, section detection (TDD)
- [x] 03-02-PLAN.md -- Generation foundation: coherence state, templates, prompt budget, failure log (TDD)
- [x] 03-03-PLAN.md -- Pipeline orchestration, section assembly, CLI generate command, integration tests

### Phase 4: Rendering & Output Packaging
**Goal**: User receives professional-quality PDF output -- a full conductor score and individual transposed parts -- packaged in a ZIP with source files
**Depends on**: Phase 3
**Requirements**: FNDN-06, ENGR-01, ENGR-02, ENGR-03, ENGR-04, ENGR-09, ENSM-01, ENSM-04
**Success Criteria** (what must be TRUE):
  1. System renders a full conductor score PDF with standard big band instrument ordering (woodwinds, brass, percussion, rhythm), system brackets/braces, and landscape orientation
  2. System renders one extracted part PDF per instrument, correctly transposed to the instrument's reading key with proper clef and key signature
  3. Parts include rehearsal marks (every 8-16 bars and at structural landmarks), measure numbers at the start of each line, and consolidated multi-bar rests
  4. Parts include dynamic markings with restatement after multi-bar rests
  5. Output is packaged as a ZIP containing selected PDFs and LilyPond source files (.ly), with chord symbols on rhythm section parts (guitar, piano, bass)
**Plans:** 3/3 plans complete

Plans:
- [ ] 04-01-PLAN.md -- Ensemble preset data model (BigBandPreset, InstrumentSpec) and LilyPond stylesheet constants
- [ ] 04-02-PLAN.md -- LilyPond file generators (conductor score, parts, shared definitions) and dynamic restatement post-processor
- [ ] 04-03-PLAN.md -- Render pipeline, ZIP packager, CLI render command, integration tests

### Phase 5: Audio Input Pipeline
**Goal**: User can upload audio files or paste a YouTube URL and the system extracts MIDI data through source separation and transcription
**Depends on**: Phase 3
**Requirements**: FNDN-02, FNDN-03, AUDP-01, AUDP-02
**Success Criteria** (what must be TRUE):
  1. User uploads an MP3, WAV, AIFF, or FLAC file and the system routes it through the audio processing pipeline
  2. User provides a YouTube URL and the system extracts audio via yt-dlp, then routes through audio processing
  3. Demucs v4 separates uploaded audio into drums, bass, vocals, and other stems
  4. Basic Pitch (or MT3 for dense ensemble content) transcribes separated stems to MIDI with pitch, timing, and velocity per voice, with fallback when the primary model produces poor results
  5. The resulting MIDI feeds into the existing MIDI-to-LilyPond pipeline from Phase 3, producing sheet music output
**Plans:** 6/6 plans complete

Plans:
- [ ] 05-01-PLAN.md -- Audio config extension and format normalizer (pydub)
- [ ] 05-02-PLAN.md -- YouTube audio extraction (yt-dlp)
- [ ] 05-03-PLAN.md -- Source separation engine: hierarchical cascade with per-stem model routing (audio-separator)
- [ ] 05-04-PLAN.md -- Transcription (Basic Pitch, Transcriber protocol) and post-transcription quality annotation
- [ ] 05-05-PLAN.md -- Audio pipeline orchestration, job directory structure, CLI process-audio command, integration tests
- [ ] 05-06-PLAN.md -- Benchmark harness: FluidSynth renderer, mir_eval evaluator, closed-loop harness, CLI benchmark command

### Phase 05.1: Promote ADVN-01 into v1 scope for Dorico (INSERTED)

**Goal:** MusicXML export generated from internal representation (not converted from LilyPond) for reliable import into Dorico/Sibelius/MuseScore, via parallel LLM fan-out producing structured JSON notation events alongside LilyPond
**Depends on:** Phase 5
**Requirements:** ADVN-01
**Success Criteria** (what must be TRUE):
  1. Generation pipeline fans out two concurrent LLM requests per section: one for LilyPond (existing), one for structured JSON notation events (new), using the Chatterfart prefix-caching pattern
  2. JSON notation events are validated via Pydantic models and converted to music21 Score objects via a JSON-to-music21 builder
  3. music21 Score is written to MusicXML 4.0 and validated against XSD before packaging
  4. Output ZIP includes a single .musicxml file at top level alongside existing PDFs, .ly, and MIDI files
  5. Invalid JSON does not halt LilyPond generation -- MusicXML is skipped gracefully
  6. Aligned (LilyPond, JSON) pairs are saved as training data for future fine-tuning
**Plans:** 4/4 plans complete

Plans:
- [ ] 05.1-01-PLAN.md -- MusicXML core: pitch map, Pydantic models, JSON-to-music21 builder (TDD)
- [ ] 05.1-02-PLAN.md -- Generation pipeline fan-out: JSON prompt suffix, asyncio.gather, training pair storage
- [ ] 05.1-03-PLAN.md -- XSD validation, telemetry, JSON assembler, RenderPipeline integration, CLI --no-musicxml
- [ ] 05.1-04-PLAN.md -- Integration tests: MusicXML export, roundtrip, fan-out, graceful degradation

### Phase 6: Audio Understanding & Hints
**Goal**: The system understands musical character beyond pitch and rhythm, and the user can guide generation with natural language descriptions
**Depends on**: Phase 5
**Requirements**: AUDP-03, AUDP-04
**Success Criteria** (what must be TRUE):
  1. Audio LM (Qwen3-Omni-30B-A3B-Instruct locally, Gemini 3 Flash for long-form) produces structured descriptions from audio capturing key, tempo, style, dynamics, articulation intent, and structural form
  2. User can type natural language hints (e.g., "Soli at bar 17, brass shout chorus bar 33, swing feel") and the system encodes them as structural metadata for the generation stage
  3. When user hints conflict with audio inference, user hints are treated as authoritative
  4. Generated LilyPond output reflects audio understanding (tempo markings, style indications, dynamic contours) that were absent from raw MIDI transcription alone
**Plans:** 2 plans

Plans:
- [ ] 06-01-PLAN.md -- AudioDescription schema, Describer protocol (Gemini 3 Flash), NL templates, DescriberConfig
- [ ] 06-02-PLAN.md -- Hint loader, three-tier prompt restructuring, audit log, pipeline integration, CLI --hints flag

### Phase 7: Convergent Sight-Reading & Ensemble Intelligence
**Goal**: Section parts are generated jointly so musicians within a section independently arrive at the same musical interpretation on first read
**Depends on**: Phase 4, Phase 6
**Requirements**: ENSM-02, ENSM-03, ENSM-05, ENGR-05
**Success Criteria** (what must be TRUE):
  1. All parts within a section (e.g., all 4 trumpets) are generated in a single LLM call, not independently -- articulations, dynamics, and beam groupings co-vary across the section
  2. Tim Davies jazz articulation defaults are applied: unmarked quarter notes are short, unmarked eighth notes are long, swing assumed unless marked "Straight 8s," staccato+accent never paired
  3. Section consistency rule enforced: if all parts share the same articulation, it is omitted (default handles it) -- only departures from the section collective default are marked
  4. Beaming follows style conventions: jazz beaming for swing, straight beaming for Latin/rock sections
  5. A blind comparison test shows that jointly-generated section parts have measurably more consistent articulations and dynamics than independently-generated parts
**Plans:** 3 plans

Plans:
- [ ] 07-01-PLAN.md -- Articulation post-processor: ENSM-03 token scanner (jazz defaults) + ENSM-05 rhythmic aligner (section consistency) (TDD)
- [ ] 07-02-PLAN.md -- Section-group data model (InstrumentSpec.section_group, resolve_section_groups) + style-aware beaming commands
- [ ] 07-03-PLAN.md -- Pipeline restructuring (per-section-group dispatch, scoped prompts, post-processing chain) + integration tests

### Phase 07.1: Minimal UI for UAT needs (INSERTED)

**Goal:** [Urgent work - to be planned]
**Depends on:** Phase 7
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 07.1 to break down)

### Phase 8: Engraving Polish
**Goal**: Parts contain all the professional engraving details that enable a real rehearsal: cues, navigation marks, page turns at rests, and chord chart output
**Depends on**: Phase 7
**Requirements**: ENGR-06, ENGR-07, ENGR-08, ENGR-10
**Success Criteria** (what must be TRUE):
  1. Parts include cue notes from an audible instrument after 8+ bars of rest, transposed to the player's reading key
  2. Parts include repeat signs, first/second endings, D.S. al Coda, and other navigation marks as inferred from structural analysis or user hints
  3. Page turns in parts are placed at rests, never mid-phrase
  4. System generates chord chart / lead sheet output with Nashville number system or chord symbol notation, optional melody line, and lyric underlay if text is provided
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

### Phase 9: Evaluation Pipeline
**Goal**: System quality is measured automatically with no human checkpoints, producing actionable quality reports
**Depends on**: Phase 4
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. System performs automated structural comparison between generated output and reference scores using MusicXML diff (note accuracy, rhythm accuracy, articulation accuracy)
  2. System renders both reference and generated LilyPond to MIDI/audio and compares spectral similarity and articulation envelopes
  3. System performs automated visual comparison of rendered PDF pages between reference and generated output (layout, spacing, readability)
  4. Evaluation pipeline runs end-to-end with no human checkpoints, producing a quality report with per-metric scores
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

### Phase 10: Web UI
**Goal**: Users interact with the engrave pipeline through a browser-based interface with drag-and-drop upload and output configuration
**Depends on**: Phase 4
**Requirements**: FNDN-07
**Success Criteria** (what must be TRUE):
  1. Web UI provides a single-page interface (FastAPI + HTML/JS) with drag-and-drop file upload, text description field, output format checkboxes, and "Engrave" button
**Plans**: TBD

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10
(Phase 5 and Phase 9 can execute in parallel with other phases -- see dependency graph)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Scaffolding & Inference Router | 0/2 | Complete    | 2026-02-24 |
| 2. RAG Corpus & Retrieval | 0/4 | Complete    | 2026-02-25 |
| 3. MIDI-to-LilyPond Generation | 0/3 | Complete    | 2026-02-25 |
| 4. Rendering & Output Packaging | 1/3 | Complete    | 2026-02-25 |
| 5. Audio Input Pipeline | 0/6 | Complete    | 2026-02-25 |
| 6. Audio Understanding & Hints | 0/TBD | Not started | - |
| 7. Convergent Sight-Reading & Ensemble Intelligence | 0/3 | Not started | - |
| 8. Engraving Polish | 0/TBD | Not started | - |
| 9. Evaluation Pipeline | 0/TBD | Not started | - |
| 10. Web UI | 0/TBD | Not started | - |
