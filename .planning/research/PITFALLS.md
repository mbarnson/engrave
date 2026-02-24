# Pitfalls Research

**Domain:** AI-powered music engraving pipeline (audio/MIDI to LilyPond to PDF)
**Researched:** 2026-02-24
**Confidence:** MEDIUM-HIGH (domain-specific findings verified across multiple sources; some areas rely on training data for domain synthesis)

## Critical Pitfalls

### Pitfall 1: LilyPond Compilation Failures from LLM-Generated Code

**What goes wrong:**
LLMs generate LilyPond source that fails to compile, producing no PDF output. The most frequent errors are: unmatched braces (missing `}` at end of score blocks or no whitespace before closing braces in lyrics blocks), incorrect duration specifications (omitting durations or placing octave marks after durations instead of before), misuse of `\relative` mode (nesting `\relative` inside `\repeat` creates duplicate staves), unexpected `\new` commands in wrong contexts, and voice collision warnings from missing `\voiceXx` directives in polyphonic passages. LilyPond's error messages are notoriously cryptic -- a malformed input file can produce errors referencing `../ly/init.ly` that give no clue about the actual problem location.

**Why it happens:**
LilyPond syntax is niche. LLM training data contains far less LilyPond than Python or JavaScript. The language has unintuitive rules: duration sticks from the previous note (so omitting it is sometimes correct, sometimes catastrophic), octave marks interact with `\relative` mode in context-dependent ways, and the brace/bracket nesting for `\score`, `\new Staff`, and `\new Voice` is deep and easy to get wrong. A 17-instrument big band score can have 8+ levels of nesting.

**How to avoid:**
1. Always compile generated LilyPond before returning results. Build a compile-check-fix loop: generate code, run `lilypond`, parse stderr, feed errors back to the LLM for correction (up to 3-5 retries).
2. Use structural templates -- never ask the LLM to generate the full score skeleton. Provide the `\score`, `\new StaffGroup`, and `\new Staff` boilerplate; let the LLM fill in only the music expressions within pre-validated containers.
3. Include 3-5 complete, compilable LilyPond examples in RAG context for every generation request.
4. Validate brace matching and basic structure with a lightweight parser before invoking `lilypond`.

**Warning signs:**
- Compilation success rate below 70% in early prototyping
- Error messages referencing `init.ly` (indicates fundamentally malformed input)
- Generated code with inconsistent indentation (correlates with brace mismatch)
- LLM "inventing" LilyPond commands that don't exist (hallucinated syntax)

**Phase to address:**
Phase 1 (LilyPond generation foundation). The compile-check-fix loop is non-negotiable infrastructure. Without it, nothing downstream works.

---

### Pitfall 2: Demucs Cannot Separate Brass, Woodwinds, or Individual Instruments

**What goes wrong:**
Demucs v4 (htdemucs) separates audio into only 4 stems: vocals, drums, bass, and "other." The experimental 6-stem model adds piano and guitar but groups everything else -- all brass (4 trumpets, 4 trombones), all saxes (5 in a big band), keyboards, and miscellaneous instruments -- into a single "other" stem. For a big band arrangement, this means the entire horn section comes out as one undifferentiated audio blob. Attempting to transcribe individual parts from this is fundamentally impossible without further separation, which doesn't exist at production quality.

Additionally, Demucs exhibits: vocal reverb bleeding into instrumental stems, hi-hat bleed into vocal stems, stereo phase artifacts on wide mixes, bass frequency muddiness between bass guitar and kick drum, and automatic output rescaling that breaks relative volume relationships between stems.

**Why it happens:**
Demucs was trained on pop/rock music datasets (MUSDB18) where the 4-stem separation (vocals/drums/bass/other) covers the primary use case. Big band and jazz ensemble arrangements with dense brass/woodwind voicings are far outside its training distribution. The harmonic content of brass instruments overlaps heavily in frequency space, making separation extremely difficult even in principle.

**How to avoid:**
1. Accept that Demucs is a preprocessing helper, not a solution. It usefully isolates drums, bass, and vocals. The "other" stem is a starting point, not an end product.
2. For the horn section: rely primarily on MIDI transcription (via MT3 or Basic Pitch) applied to the "other" stem, combined with audio LM understanding (Qwen2-Audio, Gemini) to identify instrument roles and voicings.
3. Do NOT architect the pipeline assuming individual instrument stems will be available. Design from the start for "mixed horn section audio" as the input to the transcription stage.
4. For Sam's recordings specifically: if the demo recordings are MIDI-originated (from a DAW), prefer the MIDI input path entirely and skip audio separation.
5. Consider Bandit/Banquet research for future fine-grained separation, but do not depend on it for v1.

**Warning signs:**
- Attempting to transcribe individual trumpet parts from Demucs "other" stem
- Pipeline design diagrams showing "Demucs -> individual instrument MIDI" without an intermediate step
- Testing only on recordings with few instruments and claiming it generalizes

**Phase to address:**
Phase 1 (Audio pipeline design). The pipeline architecture must account for this limitation from day one. Designing around per-instrument stems and discovering the limitation later forces a full rewrite.

---

### Pitfall 3: MT3 Instrument Leakage Fragments Transcriptions Across Wrong Instruments

**What goes wrong:**
MT3 splits audio into non-overlapping segments and transcribes each segment independently. This causes "instrument leakage" -- a melody played by one instrument across several segments gets its notes assigned to different instruments in each segment. A trumpet melody might be labeled as trumpet in bars 1-4, then saxophone in bars 5-8, then back to trumpet. The transcription is technically correct in pitch and rhythm but completely wrong in instrument assignment. For an engraving pipeline that needs to produce separate parts, this is catastrophic.

**Why it happens:**
MT3 has no memory across segments. Each ~6-second window is transcribed in isolation. Without inter-segment context, the model makes independent instrument classification decisions that are locally reasonable but globally inconsistent.

**How to avoid:**
1. Use MT3/Basic Pitch primarily for pitch and rhythm extraction. Do NOT rely on MT3's instrument labels for part assignment.
2. Use the audio LM (Qwen2-Audio, Gemini) to identify which instruments are playing and their approximate roles (melody, harmony, bass line). This provides the "what instrument plays what" information that MT3 cannot reliably provide.
3. Consider MR-MT3 (Memory Retaining MT3) which addresses this with a memory retention mechanism, but note it is a research prototype, not production-ready.
4. Design the pipeline with an explicit "instrument assignment" stage that is separate from "note transcription" -- don't conflate these two tasks.
5. For the MIDI input path, instrument assignments come from MIDI channel/program data and this pitfall doesn't apply.

**Warning signs:**
- Test transcriptions where instrument labels change mid-phrase
- Part extraction producing fragments of multiple instruments in one part
- Evaluation metrics that measure only pitch/rhythm accuracy but ignore instrument assignment

**Phase to address:**
Phase 2 (Transcription pipeline). Must be addressed before any attempt to generate per-instrument LilyPond parts.

---

### Pitfall 4: Convergent Sight-Reading Treated as Independent Part Generation

**What goes wrong:**
Section parts (e.g., 4 trumpets playing a soli passage) are generated one at a time, each as an independent LLM call. The result: Trumpet 1 gets staccato markings, Trumpet 2 gets tenuto, Trumpet 3 has no articulations, and Trumpet 4 has accents. Beam groupings differ. Dynamic markings don't align. When the section sight-reads at rehearsal, they sound like 4 soloists, not a section. This is the project's self-identified "hard problem" and the most likely failure mode.

**Why it happens:**
LLM context windows and prompting naturally handle one thing at a time. The path of least resistance is generating each part separately. Even with instructions to "match articulations across the section," an LLM generating Trumpet 4 has no reliable memory of what it chose for Trumpets 1-3 unless the full prior output is in context.

**How to avoid:**
1. Generate section parts as a single, joint output. All 4 trumpet parts in one LLM call, structured so the model writes them together (e.g., as a `\new StaffGroup` containing all 4 staves).
2. For context-length constraints: generate the section in phrase-sized chunks (4-8 bars at a time across all section instruments), not instrument-by-instrument.
3. Include explicit articulation/dynamics constraints in the prompt: "All instruments in this section MUST have identical articulation markings, beam groupings, and dynamics unless a specific deviation is notated."
4. Post-process: build a "section coherence validator" that diffs articulations, dynamics, and beam groupings across parts in the same section and flags divergences.
5. In the RAG corpus, specifically curate examples showing section writing -- parallel parts with consistent markings.

**Warning signs:**
- Parts that individually look fine but diverge in markings
- No section-level test in the evaluation pipeline (only individual part accuracy)
- Generated output where one part has `\f` and another has `\mf` at the same bar
- Architecture diagrams that show per-instrument generation paths with no merge/validation step

**Phase to address:**
Phase 3 (Section-aware generation). This is the core differentiator. It should have its own dedicated phase with specific evaluation criteria, not be treated as an afterthought.

---

### Pitfall 5: Transposition Errors in Instrument Parts

**What goes wrong:**
Generated parts have wrong key signatures, wrong note spellings, or notes transposed by the wrong interval. A Bb trumpet part shows concert pitch instead of transposed pitch. An Eb alto sax part is transposed as if it were a Bb instrument. The score shows concert pitch but parts show transposed pitch with the wrong key signature. Or worse: the LilyPond source stores music in transposed pitch and the `\transpose` command is applied on top, double-transposing.

**Why it happens:**
Transposition is one of the most error-prone areas in music notation, even for human copyists. The rules are: Bb trumpet sounds a major 2nd lower than written (so write a major 2nd UP from concert pitch). Eb alto sax sounds a major 6th lower (write a major 6th UP). French horn in F sounds a perfect 5th lower. Each instrument has a different transposition interval, and the direction (up vs. down) is counterintuitive. LilyPond's `\transposition` command requires the pitch that sounds when the player reads `c'`, entered in absolute mode. Getting this wrong silently produces wrong pitches.

**How to avoid:**
1. Store ALL music in concert pitch internally. This is LilyPond best practice (documented in official LilyPond notation reference). Apply transposition only at the final rendering stage.
2. Build a verified transposition table as a configuration artifact. For every instrument in every ensemble preset, define the `\transposition` value and validate it against known intervals. Test with a C major scale: does each instrument's part show the correct key signature?
3. Never let the LLM decide transposition intervals. The LLM generates concert-pitch music; a deterministic post-processing step applies transposition using the verified table.
4. Include transposition validation in the evaluation pipeline: extract concert-pitch MIDI from generated LilyPond, compare against expected MIDI, flag any pitch discrepancies.

**Warning signs:**
- Key signatures that don't match expected instrument transpositions
- The LLM generating `\transpose` commands in its output (it should not be)
- Parts that sound wrong when played but look plausible on paper
- Test output where all parts show the same key signature (indicates concert pitch was not transposed)

**Phase to address:**
Phase 2 (Part extraction and rendering). Transposition must be handled as deterministic infrastructure, not LLM output.

---

### Pitfall 6: Context Window Overflow on Full Big Band Scores

**What goes wrong:**
A full big band score with 17 instruments (5 saxes, 4 trumpets, 4 trombones, piano, bass, drums, guitar) spanning a 5-minute chart at ~120 bars is enormous in LilyPond source. Each instrument might be 100-300 lines of LilyPond. The full score can exceed 3,000-5,000 lines. Adding RAG context (few-shot examples, LilyPond documentation snippets) easily pushes total prompt size to 50K-100K+ tokens. Local models via LMStudio (Qwen3-30B-a3B) may have effective context limits of 8K-32K tokens, and even models that claim 128K context degrade in quality at the extremes ("lost in the middle" effect).

**Why it happens:**
Music is inherently information-dense. A single bar of a 4-part brass soli contains 4 pitches, durations, articulations, dynamics, beam groupings, and possibly lyrics/chord symbols. LilyPond's text encoding is verbose compared to binary formats like MIDI. Multiplied across 17 instruments and 120 bars, the token count explodes.

**How to avoid:**
1. Generate in phrase-sized chunks (4-8 bars) for a section at a time, not full scores in one pass.
2. Use LilyPond's variable/include system: generate each instrument's music as a separate variable, then assemble the score from a template. The LLM only needs to see the template structure + the current chunk being generated + relevant context.
3. For RAG examples: curate compact, targeted examples (single phrase, one section type) rather than full scores. A 4-bar brass soli example is more useful than a full 120-bar arrangement.
4. Benchmark actual token counts for representative LilyPond passages early in development. Measure, don't estimate.
5. For local models: prefer cloud APIs (Claude, GPT-4) for the generation step where context length matters most, and use local models for cheaper tasks (embedding, classification).

**Warning signs:**
- Truncated or degraded output quality after bar ~40 of a generated piece
- LLM "forgetting" articulation patterns established in earlier bars
- Generation that works on short examples but fails on full-length charts
- Token count exceeding 50% of model's context window for generation prompt

**Phase to address:**
Phase 1 (Architecture design). The chunked generation strategy must be designed into the pipeline from the start. Retrofitting chunking onto a monolithic generation approach is painful.

---

### Pitfall 7: RAG Retrieval Returns Irrelevant or Misleading LilyPond Examples

**What goes wrong:**
The RAG system retrieves LilyPond examples that are semantically similar to the query but syntactically wrong for the target context. Example: querying "big band brass soli, 4 trumpets, swing style" retrieves a string quartet example because the text descriptions share words like "4 instruments" and "ensemble." Or: the retrieved example uses LilyPond v2.18 syntax that is deprecated in v2.24+. Or: the example is structurally correct but musically inappropriate (a classical articulation pattern retrieved for a jazz context).

With only 350 examples in the corpus, the embedding space is sparse. Many queries will have no close match, and the "nearest" example may be far from relevant.

**Why it happens:**
General-purpose text embeddings don't understand music domain semantics. "4 trumpets playing in unison" and "4 violins playing in unison" are semantically similar in general embedding space but require completely different LilyPond code (different clefs, transpositions, ranges, articulation conventions). The corpus of 350 examples is thin -- standard RAG systems work best with thousands to millions of chunks. Few-shot overfitting is a real risk: the LLM may memorize and reproduce corpus patterns verbatim rather than adapting to new situations.

**How to avoid:**
1. Use structured metadata for retrieval, not just embedding similarity. Tag every corpus example with: instrument family, ensemble type, style (jazz/classical/rock), technique (soli/tutti/unison/counterpoint), time signature, key. Retrieve by metadata match first, then rank by embedding similarity within the filtered set.
2. Supplement the 350 original examples with open-source material from IMSLP/Mutopia. Even adding 200-500 additional diverse examples significantly improves coverage.
3. Version-lock all LilyPond examples to the target LilyPond version (v2.24 or v2.25). Strip or update deprecated syntax.
4. Chunk examples at the musical phrase level (4-8 bars of a section), not at the full-score level. This gives more retrieval granularity -- 350 scores might yield 5,000-10,000 phrase-level chunks.
5. Test retrieval quality independently before integrating with generation. Build a retrieval evaluation: given a query, do the top-5 results actually contain relevant LilyPond patterns?

**Warning signs:**
- Retrieved examples that are always from the same 10-15 scores (indicates embedding space clustering)
- Generated output that closely mimics a single corpus piece rather than adapting to the input
- Retrieval that returns classical examples for jazz queries or vice versa
- LilyPond compilation errors caused by deprecated syntax from old corpus examples

**Phase to address:**
Phase 2 (RAG system). RAG quality is a prerequisite for generation quality. Must be tested and tuned before the generation pipeline is considered reliable.

---

### Pitfall 8: Audiveris OMR Quality Too Low for Automated Corpus Building

**What goes wrong:**
Running Audiveris on Sam's 350 PDF scores to extract MusicXML produces output riddled with errors: wrong note durations, misread accidentals, missing ties and slurs, confused beam groupings, incorrect time signatures, missed key changes, and garbled articulation markings. Audiveris developers themselves acknowledge "100% recognition ratio is simply out of reach in many cases." Noteheads and stems are detected with >75% recall, but higher-level musical structures (ties, slurs, dynamics, articulations) are much less reliable. The extracted MusicXML is then used as ground truth for the training corpus -- meaning the corpus itself is corrupted.

**Why it happens:**
OMR is a hard computer vision problem. Sam's PDFs may be scans of printed music (introducing scan quality issues) or digitally-generated PDFs (better, but still imperfect for OMR). Dense big band scores with many staves, small noteheads, and overlapping markings are among the hardest OMR inputs. Audiveris was primarily designed for simpler scores.

**How to avoid:**
1. Do NOT use OMR output as ground truth without human verification. Budget significant time for manual correction of Audiveris output, especially for articulations, dynamics, and slurs.
2. Prioritize the MIDI/audio input paths for corpus building. If recordings exist as MIDI or can be re-exported from Sam's DAW, prefer that over OMR.
3. Use OMR output only for structural scaffolding (pitches, rhythms, bar structure) and manually annotate articulations and dynamics.
4. Start with the simplest scores first (lead sheets, small ensembles) where OMR quality is higher, and tackle full big band scores later when the pipeline is more robust.
5. Consider using Audiveris's interactive editor to correct the most critical scores, but don't plan to correct all 350 -- focus on 50-100 high-quality examples instead.

**Warning signs:**
- Accepting OMR output without spot-checking against the original PDF
- MusicXML files with missing measures, inconsistent bar lengths, or zero-duration notes
- Evaluation pipeline reporting "high accuracy" because it's comparing against corrupted ground truth
- Corpus examples that don't compile in LilyPond after MusicXML-to-LilyPond conversion

**Phase to address:**
Phase 1 (Corpus construction). Garbage in, garbage out. The corpus quality ceiling determines the pipeline quality ceiling.

---

### Pitfall 9: Audio LM 30-Second Clip Limitation Misses Song-Level Structure

**What goes wrong:**
Qwen2-Audio (the preferred local audio LM) processes clips under 30 seconds effectively but degrades on longer audio. A typical chart is 3-5 minutes. Processing it in 30-second clips loses song-level structure: the model doesn't know that the soli at bar 17 is a response to the intro at bar 1, that the key change at the bridge changes the harmonic context for all subsequent sections, or that the rhythm section pattern established at the top should inform feel throughout.

**Why it happens:**
Qwen2-Audio was trained on short clips. Longer audio requires resampling to 16kHz and padding, risking information loss. The model's developers acknowledge this limitation and plan to address it in future versions. Even Gemini 2.0 Flash, which handles long-form audio better, processes audio as a continuous stream without explicit musical structure awareness.

**How to avoid:**
1. Use the audio LM for local understanding (instrument identification, style, articulation feel, harmonic function) and handle global structure separately.
2. Implement a two-pass architecture: first, segment the audio into structural sections (intro, head, soli, bridge, outro) using onset detection and spectral analysis. Then, process each section with the audio LM with context about its role.
3. The user's natural language description ("soli at bar 17") provides the structural information the audio LM cannot infer. Treat user hints as authoritative for structure.
4. For Gemini 2.0 Flash: use it specifically for long-form structure analysis where Qwen2-Audio falls short. Accept the cloud API cost for this specific stage.

**Warning signs:**
- Audio LM descriptions that contradict each other across different 30-second windows
- Generated scores where the feel or style changes abruptly at segment boundaries
- Missing structural landmarks (key changes, tempo changes, section boundaries) in transcriptions

**Phase to address:**
Phase 2 (Audio understanding pipeline). Must be addressed before full-chart processing is attempted.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Generating full scores in one LLM call | Simpler pipeline code | Fails on anything longer than ~32 bars for big band | Never -- design chunked generation from day one |
| Skipping the compile-check-fix loop | Faster iteration during development | 30-50% of outputs unusable with no recovery | Never -- must be in place for any user-facing output |
| Using general-purpose embeddings for LilyPond RAG | Faster setup, no custom model needed | Poor retrieval quality, irrelevant examples pollute generation | Acceptable for v1 prototype if combined with metadata filtering |
| Accepting raw Audiveris OMR output as ground truth | Fast corpus building | Corrupted training data caps quality at ~75% | Only for structural data (pitches/rhythms); never for articulations |
| Hard-coding transpositions per instrument | Works for one ensemble type | Breaks when adding new instruments or custom ensembles | Acceptable for v1 if stored in a config file, not code |
| Testing only on short (8-16 bar) examples | Fast test cycle | Misses context-length failures, coherence drift, memory issues | During initial development only; must add full-chart tests before v1 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LilyPond CLI | Treating compilation as pass/fail binary | Parse stderr for warnings too -- warnings indicate engraving quality issues (collisions, spacing) even when compilation "succeeds" |
| Demucs | Expecting individual instrument stems | Accept 4-stem output; design pipeline around "mixed section audio" |
| MT3 / Basic Pitch | Trusting instrument labels in multi-instrument transcription | Use pitch/rhythm output only; assign instruments via audio LM or user hints |
| Audiveris OMR | Running batch OMR and trusting output | Sample-check 10% of output, budget for manual correction time |
| Qwen2-Audio | Passing full-length audio (>30s) and expecting coherent analysis | Segment audio first; process sections individually with structural context |
| YouTube download (yt-dlp) | Assuming consistent audio quality from YouTube | YouTube audio is lossy (AAC/Opus ~128-256kbps); quality varies wildly. Prefer original recordings when available |
| LilyPond MusicXML export | Expecting roundtrip LilyPond -> MusicXML -> LilyPond | LilyPond has NO native MusicXML export. Use Frescobaldi experimental export or generate MusicXML independently from internal representation |
| LMStudio local inference | Assuming local model quality matches cloud APIs | Local models (Qwen3-30B) are significantly less capable than Claude/GPT-4 for code generation. Use local for prototyping cost savings; benchmark against cloud before committing |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| LilyPond compilation on full big band score | 30-60 second compilation times for 17-instrument scores | Compile individual parts first (fast), full score only when needed | Scores >100 bars with many instruments |
| Demucs on full-length audio without GPU | 5-10x realtime processing on CPU | Ensure MPS (Metal) acceleration on M4 Max; use htdemucs (not htdemucs_ft) for speed | Audio files >3 minutes on CPU |
| Embedding all 350 scores as full documents | Slow retrieval, poor result quality | Chunk at phrase level (4-8 bars) for 5K-10K searchable chunks | When corpus grows beyond initial 350 |
| Sequential LLM calls for each instrument part | 17 separate API calls per chart, each with full context | Generate section groups together; parallelize independent sections | Full big band charts with multiple sections |
| Loading full Qwen2-Audio model for each clip | High memory usage, slow inference | Load model once, process clips in sequence through the loaded model | Processing more than ~10 clips |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Long processing time with no feedback | User thinks app is frozen; abandons process | Show stage-by-stage progress: "Separating audio... Transcribing... Generating parts... Compiling..." |
| Compilation failure returns nothing | User gets error with no usable output | Return partial results: "Parts 1-12 compiled successfully. Parts 13-17 had issues. Download available parts?" |
| Transposition errors in parts | Players sight-read wrong notes at rehearsal; trust destroyed | Always include a "preview" mode showing first 8 bars of each part for quick visual sanity check |
| No way to correct/edit results | User stuck with whatever the pipeline produces | Provide LilyPond source alongside PDF so advanced users can hand-edit |
| Articulation inconsistency across section | Section sounds bad at rehearsal; user blames tool | Highlight section coherence in output: "All trumpet parts share articulation set: staccato, accent. All trombone parts: legato, tenuto." |

## "Looks Done But Isn't" Checklist

- [ ] **PDF output:** Parts exist and compile -- but verify key signatures match instrument transpositions (Bb trumpet should NOT show concert key)
- [ ] **Articulation marks:** Present on individual parts -- but verify they are IDENTICAL across all instruments in a section
- [ ] **Dynamic markings:** Written on score -- but verify they align at the same bar numbers across section parts
- [ ] **Beam groupings:** Correct for time signature -- but verify they reflect the musical style (swing 8ths beamed differently than straight 8ths)
- [ ] **Clef assignments:** Each part has a clef -- but verify baritone sax uses bass clef (not treble), trombone uses tenor clef where needed for high passages
- [ ] **Pickup measures/anacrusis:** First measure looks correct -- but verify it has the right duration (partial measure, not full)
- [ ] **Repeats and codas:** Structure markers present -- but verify D.S., D.C., coda, and fine navigation is correct and playable
- [ ] **Chord symbols:** Present on chord chart output -- but verify slash notation vs. specific voicings are appropriate for the instrument
- [ ] **Page turns:** PDF pages look fine -- but verify page turns don't fall mid-phrase for any instrumental part
- [ ] **Evaluation pipeline:** Reports high accuracy -- but verify ground truth is correct (not corrupted OMR output)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LilyPond compilation failure | LOW | Feed error + source back to LLM for fix (automated); 3-5 retry loop |
| Wrong transposition | LOW | Deterministic fix: correct the `\transposition` value and recompile |
| Instrument leakage from MT3 | MEDIUM | Re-run transcription on isolated stems; manual instrument reassignment for problem passages |
| Incoherent section articulations | MEDIUM | Post-processing pass: choose most common articulation per beat across section, apply uniformly |
| Poor OMR quality from Audiveris | HIGH | Manual correction in Audiveris editor or re-entry; no automated recovery |
| Context window overflow mid-generation | MEDIUM | Regenerate using chunked approach; rewrite pipeline for phrase-level generation |
| RAG returning irrelevant examples | MEDIUM | Add metadata filters; manually curate example set for common query types; re-embed with domain-tuned model |
| Audio LM missing song structure | LOW | Supplement with user-provided structural description; use Gemini for long-form where Qwen2-Audio fails |
| Convergent sight-reading failure (overall) | HIGH | Requires architectural change to joint section generation; cannot be patched onto per-instrument pipeline |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LilyPond compilation failures | Phase 1: Foundation | Compilation success rate >95% on test corpus |
| Demucs stem limitation | Phase 1: Architecture | Pipeline design doc explicitly states 4-stem assumption |
| MT3 instrument leakage | Phase 2: Transcription | Instrument consistency test across segment boundaries |
| Convergent sight-reading | Phase 3: Section generation | Section coherence diff: articulations, dynamics, beams match across parts |
| Transposition errors | Phase 2: Part rendering | C major scale test for every instrument in every ensemble preset |
| Context window overflow | Phase 1: Architecture | Token count measurement for representative full-chart generation |
| RAG retrieval quality | Phase 2: RAG system | Retrieval precision@5 >60% on curated evaluation queries |
| OMR corpus quality | Phase 1: Corpus building | Spot-check 10% of OMR output against source PDFs; error rate <15% for pitches/rhythms |
| Audio LM clip limitation | Phase 2: Audio pipeline | Full-chart structural consistency test: landmarks appear in correct order and location |

## Sources

- [LilyPond Common Errors Documentation](https://lilypond.org/doc/v2.25/Documentation/usage/common-errors) -- HIGH confidence
- [LilyPond Learning Manual: Some Common Errors](https://lilypond.org/doc/v2.24/Documentation/learning/some-common-errors) -- HIGH confidence
- [LilyPond Instrument Transpositions Reference](https://lilypond.org/doc/v2.25/Documentation/notation/instrument-transpositions) -- HIGH confidence
- [LilyPond Writing Parts Reference](https://lilypond.org/doc/v2.25/Documentation/notation/writing-parts) -- HIGH confidence
- [LilyPond Beams Reference](https://lilypond.org/doc/v2.25/Documentation/notation/beams) -- HIGH confidence
- [Demucs GitHub Repository](https://github.com/facebookresearch/demucs) -- HIGH confidence
- [MT3 Paper: Multi-Task Multitrack Music Transcription](https://arxiv.org/abs/2111.03017) -- HIGH confidence
- [MR-MT3: Memory Retaining Multi-Track Music Transcription](https://arxiv.org/abs/2403.10024) -- HIGH confidence
- [Seven Failure Points When Engineering a RAG System](https://arxiv.org/abs/2401.05856) -- HIGH confidence
- [Retrieval Augmented Generation of Symbolic Music with LLMs](https://arxiv.org/html/2311.10384v2) -- MEDIUM confidence (research prototype, limited evaluation)
- [Qwen2-Audio Technical Report](https://arxiv.org/abs/2407.10759) -- HIGH confidence
- [Basic Pitch: Spotify's Audio-to-MIDI Converter](https://engineering.atspotify.com/2022/6/meet-basic-pitch) -- HIGH confidence
- [Audiveris GitHub Repository](https://github.com/Audiveris/audiveris) -- MEDIUM confidence (community discussions, not formal benchmarks)
- [NotaGen: Symbolic Music Generation with LLM Training](https://arxiv.org/html/2502.18008v5) -- MEDIUM confidence (recent, limited independent verification)
- [LilyPond-MusicXML Conversion Study](https://francopasut.netlify.app/post/lilypond_musescore_musicxml/) -- LOW confidence (single author blog post, but verified against LilyPond docs)
- [LLM Repair: Automated Code Correction](https://www.emergentmind.com/topics/llm-repair) -- MEDIUM confidence (general LLM code repair, not LilyPond-specific)

---
*Pitfalls research for: AI-powered music engraving pipeline (audio/MIDI to LilyPond to PDF)*
*Researched: 2026-02-24*
