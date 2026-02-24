# Feature Research

**Domain:** AI-powered music engraving pipeline (audio/MIDI to publication-quality engraved parts)
**Researched:** 2026-02-24
**Confidence:** MEDIUM-HIGH (features well-understood from established domain; AI transcription accuracy is the uncertainty)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these means the product fails its core promise of replacing a human copyist.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **PDF output of individual parts** | Every player needs their own part on paper. This is the entire point of engraving. | LOW | LilyPond handles this natively via `\book` and `\bookpart`. One PDF per instrument. |
| **Full conductor score PDF** | The director/conductor needs a transposed or concert-pitch full score to follow along. | LOW | LilyPond supports full score layout. Big band scores are landscape A3/Tabloid format per convention. |
| **Correct transpositions for all instruments** | A Bb trumpet part written in concert pitch is unplayable. Transposition errors = immediate loss of trust. | MEDIUM | LilyPond's `\transpose` handles this, but the system must know every instrument's transposition interval. Big band: Bb trumpet, Bb tenor sax, Eb alto sax, Eb bari sax, etc. |
| **Proper clef assignment per instrument** | Bass clef for trombone/bass, treble for trumpet/sax, grand staff for piano. Wrong clef = unreadable. | LOW | Straightforward mapping. Define once per instrument in ensemble presets. |
| **Key signatures per transposed part** | Each transposing instrument sees the key signature in their reading key, not concert. | LOW | Handled automatically by LilyPond when transposition is set up correctly. |
| **Rehearsal marks and measure numbers** | Players and conductors reference "letter B" or "bar 33" to communicate. Without these, rehearsal breaks down. | LOW | LilyPond `\mark` and bar numbering. Place rehearsal marks every 8-16 bars and at structural landmarks. |
| **Multi-format input (MP3, WAV, MIDI, YouTube)** | Sam's workflow starts from demos and recordings. Restricting input = broken workflow. | MEDIUM | Audio requires Demucs + transcription pipeline. MIDI bypasses audio stages. YouTube requires yt-dlp extraction. |
| **Correct rhythmic notation and beaming** | Sloppy beaming (e.g., beaming across beat 3 in 4/4) makes parts unreadable for sight-reading. Gould's "Behind Bars" is the reference standard. | MEDIUM | LilyPond has excellent default beaming but needs configuration for jazz conventions (straight-ahead vs Latin). |
| **Dynamic markings** | Players need to know how loud/soft to play. After rests, restate the dynamic. | MEDIUM | Must be inferred from audio analysis or user hints. Restate dynamics after multi-bar rests per engraving convention. |
| **Tempo and style markings** | "Swing," "Bossa Nova," "Ballad" at the top of the chart. Tempo at key changes. | LOW | User-provided via natural language hints. Place at top of score and at style changes. |
| **Multi-bar rests** | A trombone 4 part sitting out for 32 bars should see one consolidated rest, not 32 individual bars. | LOW | LilyPond `\compressMMRests` handles this automatically. |
| **Repeat signs and endings** | D.S. al Coda, first/second endings, repeat barlines. Charts without these waste paper and confuse players. | MEDIUM | Must be inferred from structural analysis or user hints. LilyPond supports all standard repeat constructs. |
| **Chord symbols** | Rhythm section (guitar, piano, bass) reads chord changes above the staff. Horn players need them for solo sections. | MEDIUM | Must be extracted from harmonic analysis. LilyPond `\chordmode` handles rendering. Critical for rhythm section parts. |
| **Cues during long rests** | After 16+ bars rest, show a small cue of what another instrument is playing so the player knows where they are. | MEDIUM | Requires cross-referencing parts. LilyPond supports cue notes via `\cueDuring`. Convention: add cue at 8+ bars rest. |

### Differentiators (Competitive Advantage)

Features that set Engrave apart from existing tools. These are where the product competes.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Convergent sight-reading (section-joint generation)** | THE key differentiator. When 4 trumpet parts are generated together (not independently), articulations co-vary, beam groupings reflect section-wide emphasis, dynamics align. The section sounds like a section on first read. No existing tool does this. | VERY HIGH | This is the hard problem. Parts must be generated as joint output. Tim Davies' "default" principle applies: if all 4 trumpets have the same articulation, omit it (the default handles it). Divergent articulations must be explicit. Beam groupings across a section must agree on emphasis patterns. |
| **Natural language intent layer** | User types "Soli at bar 17, brass shout chorus bar 33, soft ending" and the system encodes this as structural/articulation metadata that shapes the output. No other tool accepts plain English. | HIGH | Maps NL to structured musical annotations. LLM-mediated. This is what makes it accessible to composers who think in musical concepts, not notation software menus. |
| **Audio LM understanding (not just transcription)** | Beyond pitch/rhythm detection: understand the musical character, feel, articulation intent, section roles. Qwen2-Audio or Gemini can describe "punchy brass stabs" which informs articulation choices in ways raw MIDI cannot. | HIGH | Audio LMs produce structured text descriptions. This semantic layer bridges the gap between "what notes are played" and "how they should be notated." |
| **Ensemble presets with deep knowledge** | Not just instrument lists but full copyist knowledge: big band score order (saxes/brass/rhythm), standard transpositions, section groupings, voicing conventions, staff sizes, part layout norms. | MEDIUM | Encode the conventions from Tim Davies, Evan Rogers, Gould. Big band preset defines: instrument order, transpositions, clefs, staff sizes, score orientation (landscape), part formatting rules. |
| **Automated evaluation pipeline** | MusicXML structural diff, audio envelope comparison, visual PDF comparison. No human-in-the-loop checkpoints. This enables rapid iteration on the pipeline itself. | HIGH | Three-layer evaluation: symbolic (MusicXML diff), acoustic (rendered audio comparison), visual (PDF image comparison). Each catches different error classes. |
| **Nashville number system / lead sheet output** | Rhythm section players often prefer Nashville numbers over standard notation, especially in Nashville and contemporary church music contexts. Generate both. | MEDIUM | Transpose chord symbols to scale degrees. Existing tools (JotChord, 1Chart, Band-in-a-Box) do this standalone but none as part of an AI pipeline. |
| **LilyPond source output (editable)** | Unlike PDF-only tools, the user gets the LilyPond source code. They can hand-edit, version-control, and re-render. Power users want this. | LOW | This is inherent to the pipeline -- LilyPond code is the intermediate representation. Just include it in the output ZIP. |
| **MusicXML export** | Enables import into Dorico, Sibelius, MuseScore for further editing. The "escape hatch" that prevents vendor lock-in. | MEDIUM | LilyPond-to-MusicXML conversion is imperfect (ly2xml is experimental). Better approach: maintain MusicXML as a parallel output from the internal representation, not converted from LilyPond. |
| **RAG-augmented code generation** | Few-shot examples from curated corpus (Mutopia LilyPond, Sam's charts) dramatically improve LLM output quality for LilyPond generation. | HIGH | The corpus of (LilyPond source, MIDI, text description) triples enables retrieval of similar musical passages as context. This is the mechanism that makes RAG-first viable without fine-tuning. |
| **Source separation pipeline (Demucs)** | Separate a mixed recording into stems (drums, bass, vocals, other) before transcription. This dramatically improves multi-instrument transcription accuracy. | MEDIUM | Demucs v4 is mature and runs locally on M4 Max. The "other" stem still mixes horns/keys/guitar which needs further separation or instrument-aware transcription. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Explicitly NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Interactive notation editor** | "Let me fix a wrong note in the browser." | Building a notation editor is a multi-year project (MuseScore has 15+ years of development). Engrave is a pipeline, not an editor. Scope explosion guaranteed. | Output LilyPond source and MusicXML. Users edit in MuseScore/Dorico/Frescobaldi. Engrave does the hard part (transcription + engraving); editing tools do the easy part (tweaks). |
| **Real-time playback with audio engine** | "I want to hear what the chart sounds like." | Building/integrating a playback engine (sample libraries, MIDI routing, mixing) is an enormous distraction. MuseScore and Dorico do this well already. | Export MIDI. Users play back in their DAW or MuseScore. LilyPond can generate MIDI as a side effect. |
| **Arrangement completion / AI composition** | "Fill in the trombone 3 and 4 parts for me." | This is composition, not engraving. Crossing this line changes the product from a tool into an AI co-composer, which is a completely different product with different trust requirements. | v1 takes the arrangement as given. If only 2 trumpet parts exist in the audio, output 2 trumpet parts. Do not hallucinate parts that don't exist. Defer to v2+ after validation. |
| **Fine-tuning custom models** | "Train a model on Sam's specific style." | Fine-tuning requires infrastructure, GPU compute, data pipelines, evaluation frameworks. RAG + prompting is sufficient for v1 and dramatically simpler. | RAG-first with Sam's 350 charts as retrieval corpus. The (LilyPond, MIDI, description) triples provide style context without fine-tuning. Revisit in v2 if RAG hits a ceiling. |
| **Mobile app** | "Engrave on my phone." | The workflow involves uploading audio files, writing detailed text descriptions, and reviewing PDF output. This is inherently a desktop workflow. | Web UI works on tablets. Mobile is out of scope for v1 and likely v2. |
| **Real-time collaboration** | "Multiple arrangers working on the same chart." | Single-user workflow matches Sam's actual process. Collaboration adds WebSocket infrastructure, conflict resolution, permissions -- all orthogonal to the core value. | Single-user. Sam works alone on arrangements. |
| **Over-notation (marking every articulation)** | "Be explicit about everything." | Tim Davies' "default" principle: jazz musicians have strong defaults. Over-notation creates clutter, slows sight-reading, and paradoxically makes parts LESS readable. Redundant markings (staccato on a note that's already short by default) insult the player's intelligence. | Follow the jazz default: only notate departures from the default. Unmarked quarter notes are short. Unmarked eighth notes are long. Mark only when you want something different from what the player would naturally do. |
| **Support for every possible ensemble type at launch** | "Also support marching band, string orchestra, wind ensemble..." | Each ensemble type has its own conventions, transposition maps, score layouts, and idiomatic notation rules. Supporting all at launch means supporting none well. | Launch with big band (Sam's use case), piano solo, and small combo. Add string quartet, rock band after validation. Each new ensemble preset requires research into its specific conventions. |

## Feature Dependencies

```
[Audio Input (MP3/WAV/FLAC/YouTube)]
    |
    v
[Source Separation (Demucs)]
    |
    v
[MIDI Transcription (MT3/Basic Pitch)]--------+
    |                                          |
    v                                          |
[Audio LM Understanding]                       |
    |                                          |
    v                                          v
[Structured Musical Description] <--- [MIDI Input (direct)]
    |
    +--- [Natural Language Hints (user)]
    |
    v
[Ensemble Preset Selection]
    |
    v
[LilyPond Code Generation (RAG-augmented LLM)]
    |          ^
    |          |
    |     [RAG Corpus (Mutopia, Sam's charts, open-source)]
    |
    v
[LilyPond Rendering]
    |
    +---> [Full Score PDF]
    +---> [Individual Part PDFs (transposed)]
    +---> [Lead Sheet / Nashville Numbers]
    +---> [LilyPond Source]
    +---> [MusicXML Export]
    +---> [MIDI Export]
    |
    v
[Output ZIP Package]
```

### Dependency Notes

- **Source separation requires audio input:** MIDI input bypasses source separation and transcription entirely (the clean path).
- **MIDI transcription requires source separation:** Transcribing a mixed recording directly produces terrible results (instrument leakage, ghost notes). Separation first is mandatory.
- **Audio LM understanding enhances but does not replace MIDI transcription:** The audio LM provides semantic context (style, feel, articulation intent) but not note-level data. Both are needed.
- **Convergent sight-reading requires ensemble preset:** The system must know which instruments form a section before it can co-generate their parts.
- **RAG corpus requires curated data:** The quality of LilyPond generation depends directly on the quality of few-shot examples. Corpus curation is a prerequisite for good output.
- **MusicXML export should NOT depend on LilyPond:** LilyPond-to-MusicXML conversion is unreliable. Better to generate MusicXML from the internal representation in parallel with LilyPond.
- **Cues require all parts to be generated:** You cannot write "cue: Trumpet 1" in the Trombone 4 part until Trumpet 1 exists. Part generation must be holistic, not sequential.
- **Evaluation pipeline requires ground truth:** The automated evaluation needs reference scores to compare against. The open-source corpus provides this.

## Open-Source Corpora for Training and Evaluation

A critical component of the pipeline is access to freely-licensed musical data for RAG retrieval, evaluation, and benchmarking. Here is what exists:

### Corpora with Score + MIDI + Audio (The Triple)

| Corpus | Content | Size | License | Score | MIDI | Audio | Ensemble Types | Value for Engrave |
|--------|---------|------|---------|-------|------|-------|----------------|-------------------|
| **MAESTRO** | Piano performances from International Piano-e-Competition | 200+ hours, ~1,200 performances | CC BY-NC-SA 4.0 | No (scores not included) | Yes (fine-aligned, ~3ms) | Yes (CD quality WAV) | Piano solo only | HIGH for piano transcription eval. Audio-MIDI alignment is gold standard. No scores limits LilyPond training. |
| **ASAP** | Classical piano scores aligned with performances | 222 scores, 1,068 performances, 92+ hours | CC BY-NC-SA 4.0 | Yes (MusicXML + quantized MIDI) | Yes (performance MIDI) | Partial (via MAESTRO) | Piano solo only | VERY HIGH -- has the full triple. Score-to-performance alignment enables evaluation of transcription-to-engraving accuracy. |
| **MusicNet** | Classical chamber music with note-level annotations | 330 recordings, 34 hours, 1M+ labels | Public domain recordings | No (annotations only) | Yes (aligned MIDI labels) | Yes (freely-licensed recordings) | Chamber music (10 instruments) | HIGH for multi-instrument transcription eval. 11 instrument types including strings, winds, piano. ~4% label error rate. |
| **Slakh2100** | Synthesized multi-track audio from Lakh MIDI | 2,100 tracks, 145 hours | Research use | No | Yes (aligned MIDI per stem) | Yes (synthesized stems + mix) | Multi-instrument (34 classes) | HIGH for source separation + transcription eval. Has individual stems with aligned MIDI. Synthetic audio limits realism. |

### Corpora with Score + MIDI (No Audio)

| Corpus | Content | Size | License | Format | Value for Engrave |
|--------|---------|------|---------|--------|-------------------|
| **Mutopia Project** | Public domain classical scores typeset in LilyPond | 2,124 pieces | Public domain / CC | LilyPond source + PDF + MIDI | CRITICAL -- the primary source of (LilyPond source, MIDI) pairs for RAG. These are human-curated, publication-quality LilyPond. Includes Bach, Beethoven, Chopin, etc. |
| **PDMX** | Large-scale public domain MusicXML from MuseScore | 250K+ files (222K verified license-clean) | Public domain / CC-0 | MusicXML + PDF + MIDI | VERY HIGH -- massive scale. MusicXML can be converted to LilyPond via musicxml2ly. Quality varies (community-contributed). Use the `no_license_conflict` subset. |
| **OpenScore** | Public domain scores in multiple formats | Growing (thousands) | CC-BY | MuseScore + MusicXML + PDF + MIDI + MP3 | HIGH -- CC-BY allows any use. Multiple formats. Quality is curated (MuseScore + IMSLP collaboration). |
| **KernScores** | Musical scores in Humdrum **kern format | 108,703 files, 7.8M+ notes | Varies by collection | Humdrum **kern | MEDIUM -- large collection but requires kern-to-LilyPond conversion. Strong for music analysis. Includes Josquin, Tasso, Polish music collections. |
| **GigaMIDI** | Largest MIDI collection with expressive annotations | 1.4M+ unique MIDI files (v2: 2.1M) | Research (fair dealing) | MIDI | MEDIUM -- massive scale but MIDI only (no scores). Useful for MIDI analysis and understanding, not for LilyPond generation training. |
| **Lakh MIDI Dataset** | Large MIDI collection matched to Million Song Dataset | 176,581 unique MIDI files | Research | MIDI | MEDIUM -- useful for MIDI understanding but no score pairs. The Slakh2100 subset adds synthesized audio. |

### Audio-Only Corpora (Supplementary)

| Corpus | Content | Size | License | Value for Engrave |
|--------|---------|------|---------|-------------------|
| **Musopen** | Public domain orchestral/chamber recordings | Thousands of recordings | CC-PD / Public domain | MEDIUM -- good for audio pipeline testing with orchestral content. No aligned scores/MIDI. |
| **IMSLP Recordings** | Community-contributed recordings of public domain works | 92,788 recordings | Varies (check per recording) | MEDIUM -- vast but licensing is per-item. Useful when paired with IMSLP scores for creating aligned data. |

### Recommended Corpus Strategy for Engrave

1. **Primary RAG corpus:** Mutopia Project (2,124 LilyPond source files). These are publication-quality, human-curated LilyPond with MIDI. Convert to (LilyPond, MIDI, structured description) triples.

2. **Scale expansion:** PDMX (222K MusicXML files). Convert via musicxml2ly to LilyPond. Quality filtering needed -- community-contributed scores vary widely.

3. **Evaluation ground truth:** ASAP dataset for piano; MusicNet for chamber music; Slakh2100 for multi-instrument source separation accuracy.

4. **Sam's corpus:** 350 original arrangements (PDF + YouTube recordings). PDFs need OMR via Audiveris to extract MusicXML, then conversion to LilyPond. This is the most valuable data for big band specifically but requires significant preprocessing.

5. **Audio pipeline testing:** MAESTRO for clean piano; Musopen for orchestral; Slakh2100 for multi-instrument with ground truth stems.

**Gap:** There is no freely-licensed big band corpus with aligned audio + score + MIDI. Sam's 350 charts partially fill this gap, but they require OMR processing and YouTube audio extraction. This is the most significant data gap for Engrave's specific use case.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what's needed for Sam to test with his band at rehearsal.

- [ ] **MIDI input to LilyPond** -- The cleanest path. Skip audio entirely. Prove the code generation pipeline works.
- [ ] **Big band ensemble preset** -- 4 trumpets, 4 trombones, 5 saxes, rhythm section. Correct transpositions, clefs, score order.
- [ ] **Individual part PDFs (correctly transposed)** -- Each player gets their part. This is the deliverable.
- [ ] **Full conductor score PDF** -- Landscape, transposed, with rehearsal marks and measure numbers.
- [ ] **Basic articulation conventions** -- Apply Tim Davies' defaults: staccato, tenuto, accent, marcato. Do not over-notate.
- [ ] **Chord symbols on rhythm section parts** -- Guitar and piano need chord changes. Bass needs chord changes for walking bass sections.
- [ ] **Multi-bar rests** -- Consolidate rests. This is trivial in LilyPond but missing it makes parts look amateur.
- [ ] **Natural language hint input** -- User describes structure, style, key sections. Even a simple version of this differentiates from all competitors.
- [ ] **RAG-augmented LilyPond generation** -- Few-shot examples from Mutopia corpus. This is the mechanism that makes output quality viable without fine-tuning.
- [ ] **Output ZIP** -- PDFs + LilyPond source. Clean packaging.

### Add After Validation (v1.x)

Features to add once MIDI-to-parts works and Sam has tested with his band.

- [ ] **Audio input pipeline (Demucs + transcription)** -- Add when MIDI path is solid. Audio introduces transcription error that compounds with engraving error.
- [ ] **YouTube URL input** -- Convenience feature built on audio pipeline.
- [ ] **Convergent sight-reading (section-joint generation)** -- The differentiator. Add once basic part generation is working. This requires generating section parts as a group, not independently.
- [ ] **Audio LM understanding** -- Semantic analysis of audio character to inform articulation choices. Adds value on top of basic transcription.
- [ ] **Cues during long rests** -- Cross-part referencing. Requires holistic generation.
- [ ] **MusicXML export** -- Escape hatch for editing in Dorico/Sibelius/MuseScore.
- [ ] **Nashville number system output** -- Parallel output format for rhythm section.
- [ ] **Automated evaluation pipeline** -- Three-layer eval once there's enough output to evaluate.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Additional ensemble presets** -- String quartet, wind ensemble, rock band, choir. Each requires research into conventions.
- [ ] **Fine-tuning on Sam's style** -- If RAG hits a ceiling, fine-tune on the 350-chart corpus. Requires GPU infrastructure.
- [ ] **Arrangement completion** -- Fill in missing voices. This crosses into AI composition territory.
- [ ] **OMR pipeline for Sam's existing PDFs** -- Audiveris to extract MusicXML from 350 PDF scores. Important for corpus building but not for the user-facing product.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| MIDI input to LilyPond | HIGH | MEDIUM | P1 |
| Big band ensemble preset | HIGH | MEDIUM | P1 |
| Individual transposed part PDFs | HIGH | LOW | P1 |
| Full conductor score PDF | HIGH | LOW | P1 |
| Basic articulation conventions | HIGH | MEDIUM | P1 |
| Chord symbols | HIGH | MEDIUM | P1 |
| Multi-bar rests | MEDIUM | LOW | P1 |
| Natural language hints | HIGH | MEDIUM | P1 |
| RAG corpus + retrieval | HIGH | HIGH | P1 |
| Output ZIP packaging | MEDIUM | LOW | P1 |
| Audio input (Demucs + transcription) | HIGH | HIGH | P2 |
| YouTube URL input | MEDIUM | LOW | P2 |
| Convergent sight-reading | VERY HIGH | VERY HIGH | P2 |
| Audio LM understanding | HIGH | HIGH | P2 |
| Cues during long rests | MEDIUM | MEDIUM | P2 |
| MusicXML export | MEDIUM | MEDIUM | P2 |
| Nashville numbers | LOW | MEDIUM | P2 |
| Automated evaluation | HIGH (internal) | HIGH | P2 |
| Repeat signs / D.S. al Coda | MEDIUM | MEDIUM | P2 |
| Additional ensemble presets | MEDIUM | MEDIUM | P3 |
| Fine-tuning | MEDIUM | VERY HIGH | P3 |
| Arrangement completion | LOW | VERY HIGH | P3 |
| OMR for Sam's PDFs | MEDIUM (internal) | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (MIDI-to-parts for Sam's rehearsal)
- P2: Add after core validation (audio pipeline, convergent sight-reading, evaluation)
- P3: Future consideration (ensemble expansion, fine-tuning, AI composition)

## Competitor Feature Analysis

| Feature | Dorico/Sibelius/MuseScore | AnthemScore | ScoreCloud | Piano2Notes | **Engrave** |
|---------|--------------------------|-------------|------------|-------------|-------------|
| Audio to notation | No (manual entry only) | Yes (polyphonic) | Yes (real-time) | Yes (piano only) | Yes (multi-instrument via separation) |
| Multi-instrument support | Yes (full editing) | Poor (piano staff only) | Limited | No (piano only) | Yes (ensemble-aware) |
| Part extraction | Yes (built-in) | No | No | No | Yes (automatic, correctly transposed) |
| Transposition handling | Yes (concert/transposed toggle) | No | No | No | Yes (automatic per instrument) |
| Ensemble presets | Partial (templates) | No | No | No | Yes (deep convention knowledge) |
| Chord symbols | Yes (manual entry) | No | Yes (detection) | No | Yes (extracted + generated) |
| Section-joint articulation | No (manual per part) | No | No | No | **Yes (convergent sight-reading)** |
| Natural language input | No | No | No | No | **Yes** |
| Publication-quality PDF | Yes | Basic | Basic | Basic | Yes (LilyPond quality) |
| Editable source output | Proprietary format | MusicXML/MIDI | MusicXML | MusicXML | LilyPond + MusicXML (open formats) |
| Price | $0-$844 | $29-$99 | $0-$20/mo | Free tier + paid | Open source (self-hosted) |

**Key insight:** No existing tool bridges the gap between "AI audio transcription" (AnthemScore, ScoreCloud) and "professional engraving" (Dorico, Sibelius). AnthemScore can hear notes but cannot produce playable ensemble parts. Dorico can engrave beautifully but requires manual note entry. Engrave bridges this gap. The convergent sight-reading feature has no analog in any existing product.

## Engraving Convention Requirements

Based on research into professional copyist practices (Tim Davies, Evan Rogers, Gould's "Behind Bars"), Engrave must encode these conventions:

### Big Band Score Layout
- **Orientation:** Landscape, A3/Tabloid
- **Instrument order:** Alto 1-2, Tenor 1-2, Bari Sax | Trumpet 1-4 | Trombone 1-4 | Guitar, Piano, Bass, Drums
- **Staff size:** Score: minimum 4.5mm. Parts: minimum 7.0mm
- **Bars per system:** 8 bars (aligns with standard phrase length)
- **Score type:** Transposed score (not concert pitch) per big band convention

### Part Layout
- **Bars per line:** 4, 6, or 8 (respect musical phrases)
- **Lines per page:** ~10 staves
- **Page turns:** Place at rests, never mid-phrase. Add blank pages for page turns with "Blank Page for Page Turn" text
- **Bar numbers:** At start of each line
- **Rehearsal marks:** Every 8-16 bars, boxed, at structural landmarks
- **Cues:** After 8+ bars rest, transposed to reading key, from an audible instrument
- **Dynamic restatement:** Restate dynamic after multi-bar rests

### Jazz Articulation Defaults (Tim Davies)
- **Unmarked quarter notes:** Short (the "jazz default")
- **Unmarked eighth notes:** Long
- **Swing assumed** unless "Straight 8s" marked
- **Fast notes:** Slurred by default
- **Long notes:** Swell by default
- **Four primary articulations:** Staccato, tenuto, accent, marcato (cap = always short in jazz)
- **DO NOT pair** staccato+accent or staccato+cap (redundant)
- **Section consistency:** If all parts in a section have the same articulation, the default handles it -- do not mark. Only mark departures from the section's collective default.

## Sources

### Notation Software
- [Top 10 Music Notation Software 2025 - Cotocus](https://www.cotocus.com/blog/top-10-music-notation-software-tools-in-2025-features-pros-cons-comparison/) (MEDIUM confidence)
- [MuseScore vs Dorico - Slant](https://www.slant.co/versus/12704/34890/~musescore_vs_dorico) (LOW confidence -- community opinions)
- [Comparison of Notation Software - Berklee Online](https://online.berklee.edu/help/notation-software/2078428-comparison-of-notation-software) (MEDIUM confidence)

### AI Transcription
- [AnthemScore](https://www.lunaverus.com/) (MEDIUM confidence -- official site)
- [Audio to MIDI in 2025 - Arranger For Hire](https://arrangerforhire.com/audio-to-midi-transcription-in-2025-how-good-is-it-really/) (MEDIUM confidence -- practitioner review, verified by multiple sources)
- [Klangio](https://klang.io/) (MEDIUM confidence -- official site)

### Jazz Notation Conventions
- [Tim Davies - Jazz Notation: The Default](https://www.timusic.net/debreved/jazz-notation/) (HIGH confidence -- authoritative practitioner source, Grammy-nominated arranger)
- [Evan Rogers - Big Band Score Layout](https://www.evanrogersmusic.com/blog-contents/big-band-arranging/score-layout) (HIGH confidence -- professional arranger)
- [Elaine Gould - Behind Bars](https://www.behindbarsnotation.co.uk/) (HIGH confidence -- industry-standard reference)
- [Mostly Modern Festival - Music Preparation Guidelines](https://mostlymodernfestival.org/music-preparation-guidelines-for-composers) (MEDIUM confidence)
- [Silver Clef Music - Engraving Guidelines](https://silverclefmusic.com/engraving-guidelines/) (MEDIUM confidence)

### Music Formats
- [LilyPond Instrument Transpositions](https://lilypond.org/doc/v2.25/Documentation/notation/instrument-transpositions) (HIGH confidence -- official docs)
- [LilyPond Scores and Parts](https://lilypond.org/doc/v2.23/Documentation/learning/scores-and-parts) (HIGH confidence -- official docs)
- [MusicXML-LilyPond interop study](https://francopasut.netlify.app/post/lilypond_musescore_musicxml/) (MEDIUM confidence)
- [Wikipedia - Comparison of Scorewriters](https://en.wikipedia.org/wiki/Comparison_of_scorewriters) (MEDIUM confidence)

### Open-Source Corpora
- [MAESTRO Dataset - Google Magenta](https://magenta.withgoogle.com/datasets/maestro) (HIGH confidence -- official source)
- [ASAP Dataset - GitHub](https://github.com/fosfrancesco/asap-dataset) (HIGH confidence -- peer-reviewed ISMIR paper)
- [MusicNet - Zenodo](https://zenodo.org/records/5120004) (HIGH confidence -- peer-reviewed)
- [Slakh2100 - Zenodo](https://zenodo.org/records/4599666) (HIGH confidence -- peer-reviewed)
- [Mutopia Project](https://www.mutopiaproject.org/) (HIGH confidence -- official site)
- [PDMX Dataset - Zenodo](https://zenodo.org/records/14648209) (HIGH confidence -- peer-reviewed, 2025)
- [OpenScore - MuseScore](https://musescore.org/en/user/57401/blog/2017/01/11/introducing-openscore) (MEDIUM confidence)
- [KernScores](https://kern.ccarh.org/) (HIGH confidence -- official site)
- [GigaMIDI - Hugging Face](https://huggingface.co/datasets/Metacreation/GigaMIDI) (HIGH confidence -- peer-reviewed TISMIR 2025)
- [Lakh MIDI Dataset](https://colinraffel.com/projects/lmd/) (HIGH confidence -- well-established)
- [Musopen](https://musopen.org/) (MEDIUM confidence -- licensing varies per item)

---
*Feature research for: AI-powered music engraving pipeline*
*Researched: 2026-02-24*
