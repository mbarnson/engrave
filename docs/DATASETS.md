# Paired MIDI/Audio/Sheet-Music Datasets for Pipeline Evaluation

Research survey of datasets with paired modalities relevant to the engrave pipeline.
Each dataset is evaluated for whether it provides all three: **MIDI + Audio + Sheet Music Engraving**.

## Summary Table

| Dataset | MIDI | Audio | Sheet Music | All 3? | Size | License |
|---|---|---|---|---|---|---|
| **MSMD** | Yes | Yes (synth) | LilyPond + PDF | **YES** | 497 pieces | CC (Mutopia) |
| **ASAP + MAESTRO** | Yes | Yes (WAV) | MusicXML (renderable) | **~Yes** | 236 scores / 200h audio | CC BY-NC-SA 4.0 |
| **PDMX** | Yes | Synthesizable | MusicXML + PDF | **~Yes** | 254K scores | CC-BY 4.0 |
| **Mutopia Project** | Yes | Synthesizable | LilyPond + PDF | **~Yes** | ~2,124 pieces | PD / CC |
| **MAESTRO** | Yes | Yes (WAV) | No | No | 1,276 perfs / 199h | CC BY-NC-SA 4.0 |
| **MAPS** | Yes | Yes (WAV) | No | No | ~270 pieces / 65h | CC BY-NC-SA 2.0 |
| **MusicNet** | Yes | Yes (WAV) | No | No | 330 recordings / 34h | CC / PD |
| **Lakh MIDI** | Yes | No | No | No | 176,581 files | CC-BY 4.0 |
| **GiantMIDI-Piano** | Yes | No (not distributed) | No | No | 10,855 works | CC-BY 4.0 |
| **ACPAS** | Yes | Yes (WAV) | No (MIDI scores) | No | 2,189 perfs / 180h | CC BY-NC-SA 4.0 |
| **KernScores** | Convertible | No | Convertible | No | ~108K files | Per-file, mixed |
| **IMSLP** | Sparse | ~93K recordings | PDF (850K scores) | Not paired | 254K+ works | PD / CC (varies) |

---

## Tier 1: True Triple-Paired Datasets

### MSMD (Multimodal Sheet Music Dataset) — BEST FIT

- **Source**: Built from 497 Mutopia Project pieces by Dorfer et al. (CPJKU, 2018)
- **Formats**: LilyPond source, rendered PDF sheet music images (with per-notehead pixel coordinates), MIDI, synthesized audio (FluidSynth)
- **Alignment**: Fine-grained — 344,742 notehead-to-audio onset pairs
- **Size**: 497 pieces of classical music
- **License**: Creative Commons (inherited from Mutopia — generally CC-BY or CC-BY-SA)
- **Access**: [GitHub: CPJKU/msmd](https://github.com/CPJKU/msmd) | [Zenodo](https://zenodo.org/records/2597505)
- **Build requirement**: Requires LilyPond + FluidSynth + ImageMagick to regenerate
- **Why it matters**: Only dataset with native LilyPond source + rendered images + MIDI + audio, all aligned at notehead level. Perfect for end-to-end engrave pipeline evaluation.

### ASAP + MAESTRO (Combined)

- **Source**: ASAP (Aligned Scores and Performances) by Foscarin et al. (CPJKU, 2020), linked to MAESTRO
- **ASAP provides**: MusicXML scores (236 distinct), quantized MIDI scores, performance MIDI, beat/downbeat/key/time-signature annotations
- **MAESTRO provides**: High-quality WAV audio (Disklavier recordings, ~3ms MIDI-audio alignment), 1,276 performances, 199 hours
- **Combined**: MusicXML scores + performance MIDI + real audio for overlapping pieces
- **License**: CC BY-NC-SA 4.0
- **Access**: [GitHub: CPJKU/asap-dataset](https://github.com/CPJKU/asap-dataset) | [MAESTRO](https://magenta.tensorflow.org/datasets/maestro)
- **Conversion needed**: MusicXML → LilyPond via `musicxml2ly` (well-supported)
- **Why it matters**: Real audio (not synthesized), large scale, professional-grade performances. MusicXML-to-LilyPond conversion is straightforward.

---

## Tier 2: Two Modalities + Synthesizable Third

### PDMX (Public Domain MusicXML)

- **Source**: Curated from MuseScore community uploads (Long et al., 2024)
- **Formats**: MusicXML (compressed MXL), MIDI, PDF sheet music, JSON metadata
- **Audio**: Not pre-rendered but synthesizable via included MusicRender + FluidSynth pipeline; future release plans pre-rendered 44.1 kHz WAV
- **Size**: ~254,000 scores (~6,250 hours of music); 222,856 in "no license conflict" subset
- **License**: CC-BY 4.0 (commercially viable)
- **Access**: [Zenodo](https://zenodo.org/records/14648209) | [GitHub: pnlong/PDMX](https://github.com/pnlong/PDMX)
- **Why it matters**: Massive scale with clean licensing. MusicXML → LilyPond conversion is standard. Audio synthesis is trivial. Closest to a production-scale triple-paired dataset.

### Mutopia Project

- **Source**: Volunteer-maintained, all pieces hand-engraved in LilyPond
- **Formats**: LilyPond source (every piece), PDF (rendered, A4 + Letter), MIDI (auto-generated from LilyPond)
- **Audio**: Not included; trivially synthesizable from MIDI via FluidSynth
- **Size**: ~2,124 pieces. Strong in Baroque/Classical piano, guitar (395), harpsichord (183), cello (107)
- **License**: Public Domain or Creative Commons (CC-BY, CC-BY-SA)
- **Access**: [mutopiaproject.org](https://www.mutopiaproject.org/) | [GitHub: MutopiaProject/MutopiaProject](https://github.com/MutopiaProject/MutopiaProject) (bulk clone)
- **Why it matters**: The gold standard for LilyPond source data. Every piece is human-curated engraving, not algorithmic conversion. MSMD is built from this.

---

## Tier 3: MIDI + Audio Only (No Sheet Music)

### MAESTRO (standalone)

- **Source**: International Piano-e-Competition, Yamaha Disklavier (Google Magenta)
- **Formats**: MIDI + WAV, aligned to ~3ms. Metadata CSV/JSON.
- **Size**: 1,276 performances, 198.7 hours, 7.04M notes. 101 GB compressed.
- **License**: CC BY-NC-SA 4.0
- **Access**: [magenta.tensorflow.org/datasets/maestro](https://magenta.tensorflow.org/datasets/maestro)

### MAPS (MIDI Aligned Piano Sounds)

- **Source**: Telecom Paris (ADASP Group). Software synthesis + real Disklavier recordings.
- **Formats**: WAV (CD quality) + aligned MIDI + text annotations
- **Size**: ~270 pieces × 9 recording conditions, ~65 hours, ~31-40 GB
- **License**: CC BY-NC-SA 2.0 FR
- **Access**: [adasp.telecom-paris.fr](https://adasp.telecom-paris.fr/resources/2010-07-08-maps-database/)

### MusicNet

- **Source**: Classical chamber music from museums/archives (Thickstun et al., 2017)
- **Formats**: WAV + reference MIDI + CSV annotations (note-level)
- **Size**: 330 recordings, 34 hours, 1M+ annotated labels. ~10 GB compressed.
- **License**: CC / Public Domain
- **Access**: [Zenodo](https://zenodo.org/records/5120004) | [Kaggle](https://www.kaggle.com/datasets/imsparsh/musicnet-dataset)

### ACPAS (Aligned Classical Piano Audio and Score)

- **Source**: Cheng et al.
- **Formats**: WAV audio + performance MIDI + MIDI scores + rhythm/key annotations
- **Size**: 497 scores, 2,189 performances, 179.77 hours
- **License**: CC BY-NC-SA 4.0
- **Access**: [GitHub: cheriell/ACPAS-dataset](https://github.com/cheriell/ACPAS-dataset) | [Zenodo](https://zenodo.org/records/5569680)

### Slakh2100 (Synthesized Lakh)

- **Source**: Northwestern Interactive Audio Lab. Multi-track audio synthesized from Lakh MIDI.
- **Formats**: FLAC audio + aligned MIDI, multi-track (professional sample instruments)
- **Size**: 2,100 tracks, 145 hours, ~104 GB compressed
- **License**: CC-BY 4.0
- **Access**: [Zenodo](https://zenodo.org/records/4599666)

---

## Tier 4: Symbolic Only (Sheet Music / MIDI, No Audio)

### IMSLP (International Music Score Library Project)

- **Size**: ~850,000 score files, 254,050 works, 27,474 composers, ~93,000 recordings
- **Formats**: Primarily scanned PDF. Some MusicXML/LilyPond sources (rare). Audio recordings exist but are separate.
- **License**: Public domain / CC (varies per file)
- **Access**: [imslp.org](https://imslp.org/) — no bulk download API
- **Pairing efforts**: [Linking Lakh MIDI to IMSLP](https://pages.hmc.edu/ttsai/assets/LinkingLakhIMSLP.pdf) (Tsai et al.) — 200 MIDI files matched to 5,000 piano scores

### Lakh MIDI Dataset

- **Size**: 176,581 unique MIDI files. ~1.65 GB compressed.
- **Formats**: MIDI only. LMD-matched subset (45,129 files) links to Million Song Dataset.
- **License**: CC-BY 4.0
- **Access**: [colinraffel.com/projects/lmd](https://colinraffel.com/projects/lmd/)
- **Related**: Slakh2100 synthesizes audio from Lakh MIDI for 2,100 tracks.

### KernScores (kern.humdrum.org)

- **Size**: ~108,700 files, ~7.87M notes. GitHub mirror: ~26,490 files.
- **Formats**: **kern (Humdrum text-based symbolic notation)
- **License**: Per-file, mixed
- **Access**: [kern.ccarh.org](https://kern.ccarh.org/) | [GitHub: humdrum-tools/humdrum-data](https://github.com/humdrum-tools/humdrum-data)
- **Conversion**: `hum2ly` (kern→LilyPond), `converter21` (kern↔MusicXML/LilyPond/MEI/ABC)

### GiantMIDI-Piano

- **Size**: 10,855 solo piano works, 2,786 composers, 1,237 hours. ~193 MB download.
- **Formats**: MIDI only (transcribed from YouTube audio, but audio not distributed)
- **License**: CC-BY 4.0
- **Access**: [GitHub: bytedance/GiantMIDI-Piano](https://github.com/bytedance/GiantMIDI-Piano)

---

## Tier 5: Score Images Only (OMR-focused)

### MusicScore

- **Formats**: Score page images + text metadata (from IMSLP)
- **Size**: 400 / 14K / 200K image-text pairs (three scales)
- **Access**: [Hugging Face: ZheqiDAI/MusicScore](https://huggingface.co/datasets/ZheqiDAI/MusicScore)

### PrIMuS (Printed Images of Music Staves)

- **Formats**: PNG score images + MEI encoding + simplified encodings
- **Size**: 87,678 real-music incipits
- **Access**: [grfia.dlsi.ua.es/primus](https://grfia.dlsi.ua.es/primus/)

---

## Recommendations for Engrave Pipeline Evaluation

### Immediate Use (ready today)

1. **MSMD** — 497 pieces with LilyPond + MIDI + audio + pixel-aligned noteheads. Start here for ground-truth evaluation.
2. **Mutopia Project** — 2,124 pieces with LilyPond + MIDI. Synthesize audio with FluidSynth. 4× MSMD's size.

### Medium-Term (conversion needed)

3. **ASAP + MAESTRO** — Real audio + MusicXML scores. Convert MusicXML→LilyPond with `musicxml2ly`. Best source of real (non-synthesized) piano audio with aligned scores.
4. **PDMX** — 254K scores with MusicXML + PDF + MIDI. Convert to LilyPond; synthesize audio. Massive scale, clean CC-BY licensing.

### Format Conversion Pipeline

For datasets without native LilyPond:
```
MusicXML → LilyPond:  musicxml2ly (ships with LilyPond)
**kern → LilyPond:    hum2ly or converter21
MIDI → Audio:          FluidSynth + soundfont (e.g., FluidR3_GM)
MIDI → LilyPond:      music21 (quantize) → musicxml2ly (lower quality than human engravings)
```

### Key Insight

No single dataset ships all three modalities at scale. The practical approach is:
- **MSMD for quality** (small but perfectly aligned, native LilyPond)
- **PDMX for scale** (254K scores, needs audio synthesis + LilyPond conversion)
- **ASAP+MAESTRO for real audio** (needs MusicXML→LilyPond conversion)
