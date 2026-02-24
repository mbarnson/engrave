# Engrave

## What This Is

An AI-powered pipeline that transforms audio recordings, YouTube links, and MIDI files into professionally engraved, performance-ready sheet music as PDF — with correct transpositions, section-appropriate articulation markings, and notation conventions that enable convergent sight-reading across an ensemble section. Built for composers like Sam Graber who write for big bands and ensembles and currently pay $500-$2,000 per chart for skilled human copyists.

## Core Value

When Sam uploads a rough demo recording and types "Big band, 4 trumpets, 4 bones, 5 saxes, rhythm section. Soli at bar 17" — his players can sight-read the extracted parts at rehearsal and the brass section sounds like a section. The notation encodes interpretive intent so precisely that multiple players independently arrive at the same musical result.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Audio input pipeline: accept MP3, WAV, AIFF, FLAC files and YouTube URLs
- [ ] MIDI input pipeline: accept MIDI type 0 and 1 files (bypasses audio stages)
- [ ] Source separation via Demucs v4 (drums, bass, vocals, other stems)
- [ ] MIDI transcription via MT3 or Basic Pitch from separated stems
- [ ] Audio understanding via audio LM (Qwen2-Audio, LFM2.5-Audio, Gemini 2.0) producing structured musical descriptions
- [ ] Natural language hint layer — user describes ensemble, style, structural markers, articulation intent
- [ ] Ensemble presets with transposition/clef configuration (big band, small group, rock band, piano solo, string quartet, custom)
- [ ] LilyPond code generation via RAG-augmented LLM (multi-provider: Anthropic API, OpenAI API, LMStudio local)
- [ ] LilyPond rendering to PDF (full conductor score + extracted transposed parts per instrument)
- [ ] Output packaging: ZIP with selected PDFs, LilyPond source, MusicXML export
- [ ] Chord chart / lead sheet output option (Nashville number system or chord symbols)
- [ ] Convergent sight-reading: section parts generated jointly (articulations co-vary, beam groupings reflect section-wide emphasis, dynamics align)
- [ ] Open-source training/evaluation corpus from freely-licensed scores, MIDI, and audio (IMSLP, Mutopia, etc.)
- [ ] Automated evaluation pipeline: structural diff (MusicXML), audio envelope comparison, visual PDF comparison — no human checkpointing
- [ ] Web UI: single-page FastAPI + HTML/JS, drag-and-drop upload, description field, output options, "Engrave" button
- [ ] RAG system against curated corpus for few-shot LilyPond generation examples

### Out of Scope

- Fine-tuning models — v1 is RAG-first; v2 fine-tuning target is Qwen3-4B (not 30B) — narrow task favors specialized small model, local inference advantage, LilyPond compiler feedback as free reward signal (RLCF). v1 error telemetry feeds fine-tuning corpus prioritization.
- Arrangement completion — Engrave v1 takes the arrangement as given, does not fill in incomplete voicings
- Mobile app — web-first
- Real-time collaboration — single-user workflow
- Commercial deployment — prototype for Sam's personal use and validation

## Context

- **Collaboration:** [Shared Google Drive](https://drive.google.com/drive/folders/1Te9xTPCD46GoS4IMuwejDG9KsUyvSm6u?usp=sharing) — Matt & Sam working docs
- **Primary user:** Sam Graber, prolific composer writing for rock trio and full big band
- **Hardware:** Matt's M4 Max, 128GB RAM — local inference preferred, cloud OK when needed
- **Inference strategy:** Multi-provider — Anthropic API, OpenAI API, LMStudio local endpoints. Pipeline may use different models at different stages. LMStudio is cheapest for prototyping, using `lms` CLI to swap models.
- **Model candidates for Stage 4 (code gen):** Qwen3.5-Medium (30B-A3B), Qwen3-Coder-Next (80B-A3B), gpt-oss-120b, Claude, GPT-4 — to be benchmarked. ML landscape moves fast — new models drop constantly (Qwen3.5-Medium released Feb 2026). LMStudio + `lms` CLI enables rapid model swapping.
- **Audio LM candidates (Stage 3):** Qwen2-Audio (local on Apple Silicon), LFM2.5-Audio (Matt has experience), Gemini 2.0 Flash (best for long-form audio, closed API)
- **Corpus strategy:** v1 uses open-source freely-licensed material — Mutopia Project (2,124 LilyPond scores + MIDI), PDMX (222K MusicXML), OpenScore, KernScores, MAESTRO, ASAP, MusicNet, Slakh2100. v1.1 adds Sam's 350 original arrangements via OMR (Audiveris PDF → MusicXML). No freely-licensed big band corpus exists — Sam's charts fill that gap.
- **Training triple format:** (LilyPond source, MIDI tokens, structured text description)
- **LilyPond:** Not yet installed — needs setup as project dependency
- **Key insight:** Once audio becomes MIDI and MIDI becomes structured text, the text-to-LilyPond transformation is a code generation problem. LLMs are already excellent at code generation.
- **The hard problem:** Convergent sight-reading — section parts must be generated as joint output, not independent lines. Articulations, beam groupings, dynamics must co-vary across a section.

## Constraints

- **Tech stack:** Python + FastAPI backend, simple HTML/JS frontend — no heavy JS framework
- **Inference:** Must support Anthropic API, OpenAI API, and LMStudio local endpoints
- **Local-first:** ML inference should run locally on M4 Max where possible; cloud APIs acceptable for models that don't run locally
- **No fine-tuning:** v1 uses RAG + prompting only — avoids the fine-tuning dependency
- **Corpus licensing:** Open-source corpus must use freely-licensed material only (public domain, CC-BY, etc.) for the proof-of-concept. Sam's original works cover the core big band use case.
- **Automated evaluation:** Quality assessment must be fully automated — no human-in-the-loop checkpoints for the evaluation pipeline

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + FastAPI for backend | Matches ML ecosystem, simple deployment | — Pending |
| RAG-first, no fine-tuning for v1 | Lower barrier, Matt has no fine-tuning experience, modern models may be sufficient | — Pending |
| Multi-provider inference | Flexibility to benchmark models, LMStudio cheapest for prototyping | — Pending |
| LilyPond as rendering engine | Open-source, text-based (LLM can write it directly), publication-quality output | — Pending |
| Open-source corpus for POC | Avoids copyright issues, supplements Sam's originals, enables automated evaluation | — Pending |
| Audio + MIDI + YouTube from day 1 | Full pipeline needed for Sam's rehearsal test | — Pending |
| Automated multi-layer evaluation | MusicXML diff + audio comparison + visual PDF diff — no human gate | — Pending |

---
*Last updated: 2026-02-24 after initialization*
