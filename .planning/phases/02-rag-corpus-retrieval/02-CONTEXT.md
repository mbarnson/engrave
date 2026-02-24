# Phase 2: RAG Corpus & Retrieval - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest open-source LilyPond scores from Mutopia Project and PDMX, build a ChromaDB vector index with phrase-level chunking, attach structured metadata, and provide a retrieval interface that Phase 3 uses for few-shot LilyPond code generation context. No generation happens in this phase -- only corpus building and retrieval.

</domain>

<decisions>
## Implementation Decisions

### Ingestion Pipeline
- Scores that fail to compile are run through the Phase 1 compile-fix loop first; if that fixes them, include; otherwise skip and log
- PDMX MusicXML originals stored alongside converted LilyPond (keep both formats)
- Minimal quality filter only: exclude degenerate cases (empty scores, single-note files) but keep exercises, short pieces, and scores without instrument metadata
- MIDI compiled from LilyPond source ourselves (not using pre-existing MIDI from archives) to guarantee consistency between MIDI and indexed LilyPond

### Chunking Strategy
- Music-aware phrase boundaries: use structural cues from LilyPond source (rehearsal marks, double barlines, key/time changes, repeat signs) to find natural phrase boundaries; fall back to fixed 4-8 bar chunks when no structural cues exist
- Both single-instrument chunks and full-score vertical chunks (all parts at same bar range) created from multi-part scores -- supports both single-part and section-level retrieval

### Metadata & Descriptions
- No LLM-generated descriptions for v1 -- user insight: language models produce desultory music descriptions ("fast music plays", "sombre music plays"), not useful musical analysis
- Structured text descriptions templated from programmatically extracted metadata:
  - **Core notation facts:** key signature, time signature, tempo marking, instrument/clef, bar range
  - **Density metrics:** note density (notes per bar), dynamic range (pp-ff), articulation count, chord symbol presence
  - **Source provenance:** composer, era (if available from archive metadata), ensemble type, source collection (Mutopia vs PDMX)
- MIDI-derived features (tempo curve, velocity histogram, pitch range, rhythmic complexity) included when MIDI compilation succeeds
- Music Flamingo (nvidia/music-flamingo-hf) identified as future enrichment path for rich audio-derived descriptions, but explicitly NOT a v1 dependency -- research/noncommercial license, not MLX-native

### Retrieval Interface
- Python library, direct import (`from engrave.corpus import retrieve`) -- no HTTP service for v1
- Hybrid scoring: metadata filter (instrument family, ensemble type, style) combined with embedding similarity for stylistic match within the filtered set
- Configurable result count with default of 5 examples per query; Phase 3 can request more or fewer based on generation task complexity

### Claude's Discretion
- Chunk overlap strategy (whether to overlap and by how many bars)
- Repeat/D.S./coda handling during chunking (expand vs chunk as-written)
- Embedding model choice (code-focused vs general text vs hybrid)
- ChromaDB schema design for future enrichment (whether to include empty slots for rich descriptions)

</decisions>

<specifics>
## Specific Ideas

- User has researched the music description landscape extensively: Music Flamingo (NVIDIA, Nov 2025) is the state of the art for deep structural description but is research-only; BASS benchmark (Feb 2026) evaluates audio LMs on musicological analysis using Pandora's Music Genome annotations; all current models still struggle with sonority and rhythm
- Templated metadata descriptions are explicitly preferred over LLM narratives because the user has observed that LLM music descriptions lack the detail needed for meaningful retrieval
- The corpus serves Phase 3 directly -- retrieval quality matters more than corpus completeness

</specifics>

<deferred>
## Deferred Ideas

- Music Flamingo enrichment of corpus descriptions -- future backfill after v1 proves the pipeline works (v1.1 or v2)
- Sam's 350 original arrangements ingestion (already captured as CORP-05/CORP-06 in v1.1 requirements)

</deferred>

---

*Phase: 02-rag-corpus-retrieval*
*Context gathered: 2026-02-24*
