---
created: 2026-02-25T02:36:40.761Z
title: Standalone LilyPond-to-MusicXML converter via fine-tuned Qwen3-4B
area: planning
files:
  - .planning/REQUIREMENTS.md (TUNE-01, TUNE-02, ADVN-01)
  - .planning/phases/05.1-promote-advn-01-into-v1-scope-for-dorico/05.1-CONTEXT.md
---

## Problem

Phase 05.1's parallel fan-out (LilyPond + JSON notation events) produces aligned training pairs as a byproduct of normal operation. Every Engrave run generates ground truth (LilyPond text, structured JSON) pairs from identical context in the same inference cycle — not noisy or heuristically extracted.

Running Engrave on the Mutopia corpus (2,124 pieces, 10K+ sections) and PDMX corpus produces tens of thousands of aligned pairs. Fine-tuning Qwen3-4B on these yields a small, fast model that does reliable LilyPond-to-MusicXML conversion — something nobody in the open-source music world has managed.

The training task is tractable: structural translation between two notation representations, not musical understanding. `\relative c' { bes4\marcato }` -> `{"pitch": "bf4", "beat": 1.0, "duration": 1.0, "articulations": ["marcato"]}`.

Community impact: thousands of LilyPond users currently cannot get scores into Dorico without OCR'ing their own PDFs. A standalone `engrave convert score.ly --output score.musicxml` tool running locally on any laptop would make Engrave matter to users who never need audio-to-sheet-music.

## Solution

**Path to implementation:**

1. **Phase 05.1 (v1):** Parallel fan-out produces aligned (LilyPond, JSON) pairs. Save both in job directory — already planned in 05.1-CONTEXT.md.

2. **Corpus generation run (v1.1):** Run Engrave on Mutopia + PDMX corpora to mass-produce training pairs. Same pipeline, just pointed at the existing corpus.

3. **TUNE-01 extension (v2):** Fine-tune Qwen3-4B on (LilyPond -> JSON notation) pairs alongside the existing LilyPond compilation success training. Two LoRA adapters, same base model, same infrastructure.

4. **Standalone converter (v2):** Ship as `engrave convert` CLI command. LilyPond in, MusicXML out. No audio pipeline, no MIDI. Fine-tuned Qwen3-4B runs locally.

**Known limitation:** Engrave-generated LilyPond has a particular template style. Wild LilyPond (Mutopia, IMSLP, personal projects) uses exotic features: custom markup, Scheme extensions, overrides, non-standard staff configurations. Model will be great on "normal" LilyPond and degrade on exotic constructs. Improvable iteratively as training corpus grows.

**Feedback loop:** TUNE-02's error telemetry pattern applies — when the converter produces invalid MusicXML or drops constructs, log it, feed it back, retrain. The flywheel spins.

**Key insight:** The data is the moat. Phase 05.1 is already building the machine that produces it. Collection is free; not collecting is irreversible.
