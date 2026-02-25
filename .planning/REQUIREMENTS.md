# Requirements: Engrave

**Defined:** 2026-02-24
**Core Value:** When Sam uploads a recording and describes his ensemble, his players can sight-read the extracted parts at rehearsal and the brass section sounds like a section.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [ ] **FNDN-01**: System accepts MIDI type 0 and type 1 files as input and routes them directly to the notation stage (bypassing audio processing)
- [ ] **FNDN-02**: System accepts audio files (MP3, WAV, AIFF, FLAC) as input and routes them through the full audio processing pipeline
- [ ] **FNDN-03**: System accepts YouTube URLs as input via yt-dlp, extracts audio, and routes through audio processing pipeline
- [x] **FNDN-04**: System supports multiple LLM providers (Anthropic API, OpenAI API, LMStudio local) via LiteLLM, configurable per pipeline stage
- [x] **FNDN-05**: System provides a compile-check-fix retry loop that detects LilyPond compilation errors, feeds them back to the LLM, and retries up to 5 times
- [ ] **FNDN-06**: System packages output as a ZIP containing selected PDFs, LilyPond source files, and MusicXML export
- [ ] **FNDN-07**: Web UI provides a single-page interface (FastAPI + HTML/JS) with drag-and-drop file upload, text description field, output format checkboxes, and "Engrave" button

### Audio Processing

- [ ] **AUDP-01**: System performs source separation on audio input via best-available model per stem (BS-RoFormer for vocals, Mel-Band RoFormer for drums/other, HTDemucs ft for bass) using audio-separator, producing drums, bass, vocals, and other stems
- [ ] **AUDP-02**: System transcribes separated stems to MIDI via Basic Pitch (default, single-instrument) or MT3 (multi-instrument mode for dense ensemble content), extracting pitch, timing, and velocity per voice -- with fallback strategy when primary model produces poor results
- [ ] **AUDP-03**: System produces structured musical descriptions from audio via audio LM (Qwen3-Omni-30B-A3B-Captioner for local inference, Gemini 3 Flash for cloud/long-form), capturing key, tempo, style, dynamics, articulation intent, and structural form
- [ ] **AUDP-04**: User can provide natural language hints describing ensemble composition, style, structural markers, and articulation intent -- hints are treated as authoritative when conflicting with audio inference

### RAG & Corpus

- [x] **CORP-01**: System ingests open-source LilyPond scores from Mutopia Project (2,124 pieces) and indexes them as (LilyPond source, MIDI, structured text description) triples in ChromaDB
- [x] **CORP-02**: System ingests MusicXML scores from PDMX and converts to LilyPond via musicxml2ly for RAG corpus expansion
- [x] **CORP-03**: RAG system retrieves relevant few-shot examples based on structured metadata (instrument family, ensemble type, style, musical context) to provide context for LilyPond generation
- [x] **CORP-04**: Corpus is chunked at phrase level (4-8 bars) to expand 2K+ scores into 10K+ retrievable examples

### LilyPond Generation

- [ ] **LILY-01**: System generates compilable LilyPond source code from MIDI tokens + structured text description + user hints + ensemble preset + RAG examples
- [x] **LILY-02**: System generates scores section-by-section (4-8 bar chunks) with coherence state passing to maintain consistency across sections (key, articulations, dynamics, voicing patterns)
- [x] **LILY-03**: All music is stored internally in concert pitch; transposition is applied deterministically at render time using a verified transposition table
- [x] **LILY-04**: System achieves >90% LilyPond compilation success rate on first attempt (before retry loop)

### Engraving Output

- [ ] **ENGR-01**: System renders a full conductor score PDF with standard instrument ordering (woodwinds, brass, percussion, rhythm), system brackets and braces, landscape orientation for big band
- [ ] **ENGR-02**: System renders one extracted part PDF per instrument, correctly transposed to the instrument's reading key with proper clef and key signature
- [ ] **ENGR-03**: Parts include rehearsal marks (every 8-16 bars and at structural landmarks), measure numbers at the start of each line, and multi-bar rests (consolidated)
- [ ] **ENGR-04**: Parts include dynamic markings with restatement after multi-bar rests
- [ ] **ENGR-05**: Parts include correct rhythmic notation and beaming per style conventions (jazz beaming for swing, straight beaming for Latin/rock)
- [ ] **ENGR-06**: Parts include cue notes from an audible instrument after 8+ bars of rest, transposed to the player's reading key
- [ ] **ENGR-07**: Parts include repeat signs, first/second endings, D.S. al Coda, and other navigation marks as inferred from structural analysis or user hints
- [ ] **ENGR-08**: System generates chord chart / lead sheet output with Nashville number system or chord symbol notation, optional melody line, and lyric underlay if text is provided
- [ ] **ENGR-09**: LilyPond source files (.ly) are always included in the output ZIP for downstream editing in Frescobaldi or text editor
- [ ] **ENGR-10**: Page turns in parts are placed at rests, never mid-phrase

### Ensemble & Articulation

- [ ] **ENSM-01**: System includes a big band ensemble preset encoding: 5 saxes (AATBT), 4 Bb trumpets, 4 trombones (3 tenor + 1 bass), piano, guitar, bass, drums -- with correct transpositions, clefs, score order, and staff sizes
- [ ] **ENSM-02**: System generates section parts jointly (e.g., all 4 trumpets in one LLM call) so articulations, dynamics, and beam groupings co-vary -- enabling convergent sight-reading
- [ ] **ENSM-03**: System applies Tim Davies jazz articulation defaults: unmarked quarter notes are short, unmarked eighth notes are long, swing assumed unless marked "Straight 8s," staccato+accent not paired (redundant)
- [ ] **ENSM-04**: System generates chord symbols on rhythm section parts (guitar, piano, bass) with changes placed above the staff
- [ ] **ENSM-05**: Section consistency rule: if all parts in a section have the same articulation, omit it (the default handles it) -- only mark departures from the section's collective default

### Evaluation

- [ ] **EVAL-01**: System performs automated structural comparison between generated output and reference scores using MusicXML diff (note accuracy, rhythm accuracy, articulation accuracy)
- [ ] **EVAL-02**: System performs automated audio comparison by rendering both reference and generated LilyPond to MIDI/audio and comparing spectral similarity / articulation envelopes
- [ ] **EVAL-03**: System performs automated visual comparison of rendered PDF pages between reference and generated output (layout, spacing, readability)
- [ ] **EVAL-04**: Evaluation pipeline runs end-to-end with no human checkpoints, producing a quality report with per-metric scores

## v1.1 Requirements

Deferred to after open-source corpus proves the concept.

### Corpus Expansion

- **CORP-05**: Sam's 350 original arrangements ingested via Audiveris OMR (PDF to MusicXML to LilyPond) with manual quality verification on 10% sample
- **CORP-06**: YouTube recordings paired with Sam's scores to create (LilyPond source, MIDI tokens, structured text description) triples for big band RAG corpus

## v2 Requirements

Deferred to future release.

### Fine-Tuning

- **TUNE-01**: Fine-tune Qwen3-4B (or equivalent small model) on curated LilyPond corpus using LoRA, targeting >95% compilation success rate
- **TUNE-02**: Use v1 error telemetry to prioritize fine-tuning examples -- oversample patterns the general model gets wrong most often
- **TUNE-03**: Explore RLCF (reinforcement learning from compiler feedback) using LilyPond compilation success/failure as reward signal

### Additional Ensemble Presets

- **ENSM-06**: Jazz small group preset (lead sheet + piano + bass + drums + optional horn)
- **ENSM-07**: Rock band chart preset (chord chart + lead vocal + guitar + keys + bass + drums)
- **ENSM-08**: String quartet preset (Violin I, Violin II, Viola, Cello)
- **ENSM-09**: Piano solo preset (grand staff, optional fingering and pedal markings)
- **ENSM-10**: Custom preset via free text or instrument picker

### Advanced Features

- **ADVN-01**: MusicXML export generated from internal representation (not converted from LilyPond) for reliable import into Dorico/Sibelius/MuseScore
- **ADVN-02**: Arrangement completion -- fill in missing voices when MIDI has incomplete voicings

## Out of Scope

| Feature | Reason |
|---------|--------|
| Interactive notation editor | Multi-year project (MuseScore = 15+ years). Engrave is a pipeline, not an editor. Users edit in MuseScore/Dorico/Frescobaldi. |
| Real-time playback / audio engine | Enormous distraction. Export MIDI, play back in DAW or MuseScore. |
| AI composition / arrangement completion | Crosses from engraving into composition -- different product, different trust requirements. v1 takes arrangement as given. |
| Mobile app | Inherently desktop workflow (upload files, write descriptions, review PDFs). |
| Real-time collaboration | Single-user workflow matches Sam's actual process. |
| Over-notation (marking every articulation) | Tim Davies "default" principle -- over-notation creates clutter, slows sight-reading, insults the player. Only mark departures from default. |
| All ensemble types at launch | Each requires dedicated convention research. Start with big band. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FNDN-01 | Phase 3 | Pending |
| FNDN-02 | Phase 5 | Pending |
| FNDN-03 | Phase 5 | Pending |
| FNDN-04 | Phase 1 | Complete |
| FNDN-05 | Phase 1 | Complete |
| FNDN-06 | Phase 4 | Pending |
| FNDN-07 | Phase 10 | Pending |
| AUDP-01 | Phase 5 | Pending |
| AUDP-02 | Phase 5 | Pending |
| AUDP-03 | Phase 6 | Pending |
| AUDP-04 | Phase 6 | Pending |
| CORP-01 | Phase 2 | Complete |
| CORP-02 | Phase 2 | Complete |
| CORP-03 | Phase 2 | Complete |
| CORP-04 | Phase 2 | Complete |
| LILY-01 | Phase 3 | Pending |
| LILY-02 | Phase 3 | Complete |
| LILY-03 | Phase 3 | Complete |
| LILY-04 | Phase 3 | Complete |
| ENGR-01 | Phase 4 | Pending |
| ENGR-02 | Phase 4 | Pending |
| ENGR-03 | Phase 4 | Pending |
| ENGR-04 | Phase 4 | Pending |
| ENGR-05 | Phase 7 | Pending |
| ENGR-06 | Phase 8 | Pending |
| ENGR-07 | Phase 8 | Pending |
| ENGR-08 | Phase 8 | Pending |
| ENGR-09 | Phase 4 | Pending |
| ENGR-10 | Phase 8 | Pending |
| ENSM-01 | Phase 4 | Pending |
| ENSM-02 | Phase 7 | Pending |
| ENSM-03 | Phase 7 | Pending |
| ENSM-04 | Phase 4 | Pending |
| ENSM-05 | Phase 7 | Pending |
| EVAL-01 | Phase 9 | Pending |
| EVAL-02 | Phase 9 | Pending |
| EVAL-03 | Phase 9 | Pending |
| EVAL-04 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation*
