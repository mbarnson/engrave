# Phase 2: RAG Corpus & Retrieval - Research

**Researched:** 2026-02-24
**Domain:** Vector database corpus ingestion, LilyPond parsing, music-aware chunking, embedding-based retrieval
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Scores that fail to compile are run through the Phase 1 compile-fix loop first; if that fixes them, include; otherwise skip and log
- PDMX MusicXML originals stored alongside converted LilyPond (keep both formats)
- Minimal quality filter only: exclude degenerate cases (empty scores, single-note files) but keep exercises, short pieces, and scores without instrument metadata
- MIDI compiled from LilyPond source ourselves (not using pre-existing MIDI from archives) to guarantee consistency between MIDI and indexed LilyPond
- Music-aware phrase boundaries: use structural cues from LilyPond source (rehearsal marks, double barlines, key/time changes, repeat signs) to find natural phrase boundaries; fall back to fixed 4-8 bar chunks when no structural cues exist
- Both single-instrument chunks and full-score vertical chunks (all parts at same bar range) created from multi-part scores -- supports both single-part and section-level retrieval
- No LLM-generated descriptions for v1 -- structured text descriptions templated from programmatically extracted metadata only
- Structured metadata includes: key signature, time signature, tempo marking, instrument/clef, bar range, note density, dynamic range, articulation count, chord symbol presence, composer, era, ensemble type, source collection
- MIDI-derived features (tempo curve, velocity histogram, pitch range, rhythmic complexity) included when MIDI compilation succeeds
- Python library retrieval interface: `from engrave.corpus import retrieve` -- no HTTP service for v1
- Hybrid scoring: metadata filter (instrument family, ensemble type, style) combined with embedding similarity for stylistic match within the filtered set
- Configurable result count with default of 5 examples per query

### Claude's Discretion
- Chunk overlap strategy (whether to overlap and by how many bars)
- Repeat/D.S./coda handling during chunking (expand vs chunk as-written)
- Embedding model choice (code-focused vs general text vs hybrid)
- ChromaDB schema design for future enrichment (whether to include empty slots for rich descriptions)

### Deferred Ideas (OUT OF SCOPE)
- Music Flamingo enrichment of corpus descriptions -- future backfill after v1 proves the pipeline works (v1.1 or v2)
- Sam's 350 original arrangements ingestion (already captured as CORP-05/CORP-06 in v1.1 requirements)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORP-01 | Ingest Mutopia Project LilyPond scores (2,124 pieces) as (LilyPond, MIDI, structured text description) triples in ChromaDB | Mutopia GitHub repo provides git-cloneable corpus; python-ly provides LilyPond parsing; LilyPond compiler produces MIDI via `\midi {}` block; ChromaDB 1.5.1 PersistentClient for storage |
| CORP-02 | Ingest PDMX MusicXML scores converted to LilyPond via musicxml2ly | PDMX v2 on Zenodo provides 254K MusicXML scores (mxl.tar.gz); musicxml2ly ships with LilyPond; compile-fix loop handles conversion errors |
| CORP-03 | Retrieval by structured metadata (instrument family, ensemble type, style, musical context) with embedding similarity | ChromaDB metadata filtering ($eq, $in, $and, $or operators) + cosine embedding search; hybrid query pattern documented below |
| CORP-04 | Phrase-level chunking expanding 2K+ scores into 10K+ examples | python-ly lexer tokenizes LilyPond structural elements (bar checks, rehearsal marks, key/time changes); regex-based boundary detection for chunking |
</phase_requirements>

## Summary

Phase 2 builds a RAG corpus from two open-source music score collections (Mutopia Project ~2,124 LilyPond scores, PDMX ~254K MusicXML scores) and makes them retrievable via ChromaDB with hybrid metadata-filtered embedding search. The phase has four major workstreams: (1) corpus download and ingestion pipeline, (2) LilyPond parsing and music-aware phrase chunking, (3) structured metadata extraction and description templating, and (4) the retrieval interface with hybrid scoring.

The primary technical challenge is the LilyPond parsing/chunking layer. LilyPond is a complex notation language and no full parser exists in the Python ecosystem -- python-ly provides lexer-level tokenization but not a complete AST. The chunking strategy must use a combination of python-ly tokenization and regex pattern matching to identify phrase boundaries (rehearsal marks, double barlines, key/time signature changes, repeat signs), with a fallback to bar-count-based chunking when no structural cues exist.

**Primary recommendation:** Use ChromaDB 1.5.1 with PersistentClient for storage, python-ly 0.9.9 for LilyPond tokenization supplemented by regex boundary detection, `all-MiniLM-L6-v2` as default embedding model (with a custom embedding function interface to allow swapping to nomic-embed-text-v2-moe if retrieval quality is insufficient), and templated structured descriptions for embedding text.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chromadb | 1.5.1 | Vector database for corpus storage and retrieval | De facto Python-native vector DB; built-in metadata filtering, persistent storage, embedding function abstraction |
| python-ly | 0.9.9 | LilyPond source parsing and tokenization | Only maintained Python library for LilyPond parsing; used by Frescobaldi; provides lexer, document model, bar check handling |
| sentence-transformers | latest | Embedding model host | ChromaDB's default embedding backend; provides all-MiniLM-L6-v2 and can load any HuggingFace embedding model |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| music21 | latest | MIDI feature extraction (pitch range, rhythmic complexity, tempo curve) | After MIDI compilation succeeds; extract velocity histogram, pitch statistics, rhythmic features for metadata |
| mido | latest | Low-level MIDI file reading | Lightweight alternative to music21 for basic MIDI parsing (tempo, note count, velocity stats); use if music21 is too heavy |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-ly | quickly (frescobaldi/quickly) | Successor library using parce parser; better architecture but in "early development stage" -- not production-ready |
| python-ly | Raw regex parsing | No library dependency; but LilyPond syntax is complex (nested blocks, Scheme expressions, implicit contexts) -- too error-prone for reliable chunking |
| all-MiniLM-L6-v2 | nomic-embed-text-v2-moe | Better retrieval quality (MoE architecture, 475M params) but larger/slower; evaluate if retrieval precision is insufficient with default model |
| all-MiniLM-L6-v2 | all-mpnet-base-v2 | Higher accuracy on benchmarks (~87-88% vs ~84-85% similarity tasks) but 5x slower; 768-dim vs 384-dim doubles storage |
| ChromaDB | LanceDB | Lighter weight, no server; but less mature metadata filtering, fewer embedding integrations |

**Installation:**
```bash
uv add chromadb python-ly sentence-transformers
# Optional for MIDI feature extraction:
uv add mido
```

**Note on python-ly Python 3.12 compatibility:** python-ly 0.9.9 officially lists support for Python 3.8-3.11 on PyPI. However, Gentoo packages it for Python 3.12/3.13/3.14, indicating it works. The library is pure Python with no C extensions, so compatibility risk is LOW. Verify at install time. If broken, pin to the `quickly` successor or use raw tokenization with regex.

## Architecture Patterns

### Recommended Project Structure
```
src/engrave/
  corpus/
    __init__.py          # Public API: retrieve(), ingest()
    models.py            # Pydantic models: Chunk, ScoreMetadata, RetrievalQuery, RetrievalResult
    store.py             # ChromaDB wrapper: collection management, add, query
    ingest/
      __init__.py
      mutopia.py         # Mutopia-specific ingestion: header parsing, file discovery
      pdmx.py            # PDMX-specific: MusicXML download, musicxml2ly conversion
      pipeline.py        # Shared ingestion pipeline: compile, chunk, extract metadata, index
    chunker.py           # Music-aware phrase chunking logic
    metadata.py          # Metadata extraction from LilyPond source and MIDI
    description.py       # Template-based structured text description generation
    embeddings.py        # Custom embedding function wrapper for ChromaDB
```

### Pattern 1: Ingestion Pipeline (ETL for Scores)
**What:** A pipeline that takes raw score files, validates/compiles them, chunks them into phrases, extracts metadata, generates descriptions, and indexes into ChromaDB.
**When to use:** For both Mutopia and PDMX ingestion, with source-specific adapters.
**Example:**
```python
# Source: Architecture pattern for score ingestion
from dataclasses import dataclass
from pathlib import Path

@dataclass
class IngestionResult:
    source_path: Path
    chunks_indexed: int
    midi_generated: bool
    errors: list[str]

async def ingest_score(
    ly_source: str,
    source_path: Path,
    source_collection: str,  # "mutopia" or "pdmx"
    header_metadata: dict,
    compiler: LilyPondCompiler,
    store: CorpusStore,
) -> IngestionResult:
    """Ingest a single LilyPond score into the corpus.

    1. Compile to validate (and produce MIDI)
    2. If compilation fails, run through compile-fix loop
    3. If still fails, skip and log
    4. Parse source for structural boundaries
    5. Chunk into phrase-level segments
    6. Extract metadata per chunk
    7. Generate templated description per chunk
    8. Index chunks into ChromaDB
    """
    ...
```

### Pattern 2: Hybrid Retrieval (Metadata Filter + Embedding)
**What:** Two-stage retrieval: first filter by structured metadata, then rank by embedding similarity within the filtered set.
**When to use:** Every retrieval query from Phase 3.
**Example:**
```python
# Source: ChromaDB metadata filtering + embedding query
def retrieve(
    query_text: str,
    instrument_family: str | None = None,
    ensemble_type: str | None = None,
    style: str | None = None,
    n_results: int = 5,
) -> list[RetrievalResult]:
    """Retrieve relevant LilyPond phrase examples.

    Builds a ChromaDB where clause from structured filters,
    then queries with embedding similarity for ranking.
    """
    where_clauses = []
    if instrument_family:
        where_clauses.append({"instrument_family": instrument_family})
    if ensemble_type:
        where_clauses.append({"ensemble_type": ensemble_type})
    if style:
        where_clauses.append({"style": style})

    where = {"$and": where_clauses} if len(where_clauses) > 1 else (where_clauses[0] if where_clauses else None)

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
    )
    return _format_results(results)
```

### Pattern 3: Music-Aware Chunking
**What:** Parse LilyPond source to identify structural boundaries, then split into phrase-level chunks (4-8 bars).
**When to use:** During ingestion, after compilation validates the source.
**Example:**
```python
# Source: Chunking strategy using python-ly + regex
import re

# LilyPond structural boundary patterns
BOUNDARY_PATTERNS = [
    r'\\mark\s+\\default',          # Rehearsal marks
    r'\\mark\s+\d+',                # Numbered rehearsal marks
    r'\\bar\s+"\\|\\|"',            # Double barlines
    r'\\bar\s+"\\.:',               # Repeat barlines
    r'\\key\s+\w+\s*\\(major|minor)',  # Key changes
    r'\\time\s+\d+/\d+',            # Time signature changes
    r'\\repeat\s+(volta|segno)',     # Repeat structures
    r'\\section',                    # Section divisions
    r'\\fine',                       # Fine marks
    r'\\segnoMark',                  # Segno marks
    r'\\codaMark',                   # Coda marks
]

def find_phrase_boundaries(ly_source: str) -> list[int]:
    """Find character positions of structural boundaries in LilyPond source."""
    boundaries = []
    for pattern in BOUNDARY_PATTERNS:
        for match in re.finditer(pattern, ly_source):
            boundaries.append(match.start())
    return sorted(set(boundaries))
```

### Pattern 4: ChromaDB Collection Schema
**What:** Schema design for the corpus collection with metadata fields supporting future enrichment.
**When to use:** Collection creation during corpus initialization.
**Example:**
```python
# Source: ChromaDB collection creation with HNSW config
import chromadb

client = chromadb.PersistentClient(path="./data/corpus_db")

collection = client.get_or_create_collection(
    name="lilypond_phrases",
    metadata={"hnsw:space": "cosine"},
    # Default embedding function (all-MiniLM-L6-v2) unless overridden
)

# Each document is the structured text description
# The LilyPond source is stored in metadata (or a parallel store)
collection.add(
    ids=["mutopia_bach_bwv846_chunk_01"],
    documents=["Key: C major. Time: 4/4. Tempo: Allegro. Instrument: Piano, treble clef. "
               "Bars 1-8. Note density: 12.5 notes/bar. Dynamic range: mf-f. "
               "Articulations: 3. Chord symbols: none. Composer: J.S. Bach. "
               "Era: Baroque. Source: Mutopia."],
    metadatas=[{
        "source_collection": "mutopia",
        "source_path": "ftp/BachJS/BWV846/bwv846.ly",
        "chunk_index": 0,
        "bar_start": 1,
        "bar_end": 8,
        "chunk_type": "single_instrument",  # or "full_score"
        "key_signature": "C major",
        "time_signature": "4/4",
        "tempo": "Allegro",
        "instrument": "Piano",
        "instrument_family": "keyboard",
        "clef": "treble",
        "ensemble_type": "solo",
        "style": "Baroque",
        "composer": "BachJS",
        "note_density": 12.5,
        "dynamic_range": "mf-f",
        "articulation_count": 3,
        "has_chord_symbols": False,
        "has_midi": True,
        # Reserved for future enrichment (Music Flamingo etc.)
        "rich_description": "",
    }],
)
```

### Anti-Patterns to Avoid
- **Embedding the raw LilyPond source as the document:** LilyPond code has poor semantic density for embedding models trained on natural language. Instead, embed the structured text description and store the LilyPond source in metadata or a parallel file store.
- **One collection per source:** Don't separate Mutopia and PDMX into different ChromaDB collections. Use a single `lilypond_phrases` collection with a `source_collection` metadata field for filtering. This enables cross-source retrieval.
- **Storing full scores as single documents:** The whole point of chunking is phrase-level retrieval. Always store chunks, not full scores. Keep a separate index mapping chunks back to their parent scores if needed.
- **Running musicxml2ly at query time:** All conversion happens at ingestion time. The corpus stores LilyPond only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LilyPond tokenization | Custom regex-only parser for LilyPond | python-ly `ly.lex` tokenizer | LilyPond syntax has nested contexts, Scheme expressions, implicit durations -- regex alone will miss edge cases |
| Vector similarity search | Custom cosine similarity over numpy arrays | ChromaDB's built-in HNSW index | Battle-tested ANN search with metadata filtering; handles index persistence, updates, deletions |
| Embedding generation | Raw transformer inference code | sentence-transformers via ChromaDB's embedding function interface | Handles tokenization, batching, GPU/CPU dispatch; ChromaDB persists the embedding function config |
| MIDI feature extraction | Custom MIDI binary parsing | mido (lightweight) or music21 (full-featured) | MIDI is a binary format with running status, delta times, meta events -- too many edge cases to parse manually |
| MusicXML to LilyPond conversion | Custom XML parser | musicxml2ly (ships with LilyPond) | Handles hundreds of MusicXML elements; LilyPond team maintains it alongside the notation engine |

**Key insight:** The two most tempting things to hand-roll -- LilyPond parsing and MIDI parsing -- are both deceptively complex binary/structured formats with many edge cases. Use the existing tools even if they're imperfect.

## Common Pitfalls

### Pitfall 1: Mutopia LilyPond Version Mismatch
**What goes wrong:** Mutopia scores span 20+ years of LilyPond versions. Older scores use deprecated syntax (e.g., `\context` vs `\new`, old `\paper` blocks) that won't compile with current LilyPond 2.24+.
**Why it happens:** The Mutopia project has a wiki page dedicated to updating files, confirming this is a known issue. Not all scores in the repo are updated.
**How to avoid:** Run every score through compilation first. Failures go through the Phase 1 compile-fix loop (user decision). Log and skip persistent failures. Expect 10-20% of Mutopia scores to need fixes or to be skipped.
**Warning signs:** High failure rate on initial compilation batch; error messages mentioning deprecated syntax.

### Pitfall 2: PDMX Scale Overwhelms Ingestion
**What goes wrong:** PDMX has 254K scores. Ingesting all of them (with musicxml2ly conversion + LilyPond compilation + MIDI generation + chunking) takes prohibitively long.
**Why it happens:** Each score requires subprocess calls to musicxml2ly and lilypond, each taking seconds. 254K * ~5 seconds = ~350 hours sequential.
**How to avoid:** Start with the deduplicated+rated subset (R intersect D = ~13K scores). This subset has higher quality (community-rated) and is 95% unique. Only expand to the full dataset if retrieval quality demands it. Use multiprocessing for batch ingestion.
**Warning signs:** Ingestion pipeline taking more than a few hours; many conversion failures from low-quality MuseScore user uploads.

### Pitfall 3: LilyPond MIDI Output Requires Source Modification
**What goes wrong:** LilyPond only produces MIDI output when the source file contains a `\midi {}` block inside the `\score {}` block. Most Mutopia scores have `\layout {}` but not all have `\midi {}`.
**Why it happens:** MIDI output is opt-in per score in LilyPond. The `--formats=midi` CLI flag alone is insufficient -- the `\midi {}` block must be present in the source.
**How to avoid:** Programmatically inject `\midi {}` into the `\score {}` block before compilation if not already present. This is a simple text insertion (find `\layout {}` or `\score {`, insert `\midi {}` alongside).
**Warning signs:** Compilation succeeds but no .midi file is produced.

### Pitfall 4: Chunking Breaks LilyPond Compilability
**What goes wrong:** Naive chunking at bar boundaries produces LilyPond fragments that can't compile because they lack context (version declaration, score block, key/time signature preamble).
**Why it happens:** LilyPond requires complete document structure to compile. A chunk of bars 9-16 has no `\version`, no `\score`, no initial `\key`/`\time`.
**How to avoid:** Store chunks as *source fragments* (not compilable files), but store the preamble context alongside each chunk in metadata. The retrieval consumer (Phase 3) will use the fragments as few-shot examples, not as compilable files. Optionally, also store a compilable wrapper version for validation.
**Warning signs:** Attempting to compile individual chunks and getting parse errors.

### Pitfall 5: Embedding Model Mismatch for Music/Code Domain
**What goes wrong:** General-purpose text embedding models (all-MiniLM-L6-v2) may produce poor similarity scores for structured music descriptions because they weren't trained on music terminology.
**Why it happens:** Training data for these models is predominantly web text, not music notation or music theory descriptions.
**How to avoid:** Embed the *structured text description* (natural language about the music), not the LilyPond code itself. Structured descriptions use common English words ("key: C major", "tempo: Allegro", "instrument: Piano") that general embeddings handle well. Use metadata filtering as the primary retrieval mechanism, with embedding similarity as a secondary ranking signal.
**Warning signs:** Retrieval returns semantically unrelated results despite correct metadata matches; similarity scores are uniformly low.

### Pitfall 6: ChromaDB Collection Size Limits
**What goes wrong:** ChromaDB performance degrades with very large collections (>1M documents) when using the default in-process configuration.
**Why it happens:** HNSW index memory usage scales with collection size; the in-process Python client keeps the index in memory.
**How to avoid:** With 10K-50K chunks from the initial corpus (2K Mutopia + 13K PDMX rated), this is well within ChromaDB's comfortable range. If expanding to full PDMX (254K scores * ~5 chunks = ~1.3M chunks), consider sharding by source collection or using ChromaDB's server mode.
**Warning signs:** Slow query times (>500ms); high memory usage during ingestion.

### Pitfall 7: musicxml2ly Conversion Quality
**What goes wrong:** musicxml2ly does not produce perfect LilyPond output for all MusicXML files. Complex notation (tuplets, cross-staff beaming, guitar tablature) may convert poorly.
**Why it happens:** musicxml2ly maps MusicXML's graphical elements to LilyPond's semantic elements -- some are not 1:1 mappable. PDMX scores from MuseScore user uploads may have non-standard MusicXML.
**How to avoid:** Run converted files through the compile-fix loop (user decision). Accept that some PDMX scores will fail conversion and be skipped. Track conversion success rate and log failures for debugging. Start with the rated subset where quality is higher.
**Warning signs:** >30% conversion failure rate; compile-fix loop exhausting attempts frequently.

## Code Examples

### ChromaDB PersistentClient Setup
```python
# Source: ChromaDB docs (https://docs.trychroma.com/docs/run-chroma/persistent-client)
import chromadb

# Persistent storage in project data directory
client = chromadb.PersistentClient(path="./data/corpus_db")

# Create collection with cosine distance (best for text similarity)
collection = client.get_or_create_collection(
    name="lilypond_phrases",
    metadata={"hnsw:space": "cosine"},
)
```

### ChromaDB Metadata-Filtered Query
```python
# Source: ChromaDB docs (https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
results = collection.query(
    query_texts=["big band trumpet section, swing style, forte dynamics"],
    n_results=5,
    where={
        "$and": [
            {"instrument_family": "brass"},
            {"style": {"$in": ["Jazz", "Baroque"]}},
        ]
    },
)

# results contains: ids, documents, metadatas, distances
for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
    print(f"Score: {meta['source_path']}, Bars: {meta['bar_start']}-{meta['bar_end']}, Distance: {dist:.4f}")
```

### Mutopia Header Extraction
```python
# Source: Mutopia Project contribution guidelines
# (https://github.com/MutopiaProject/MutopiaProject/wiki/LilyPond-code:-best-practices-for-new-submissions)
import re

MUTOPIA_HEADER_FIELDS = [
    "mutopiatitle", "mutopiacomposer", "mutopiainstrument",
    "style", "source", "license", "maintainer",
    "mutopiapoet", "mutopiaopus", "date",
]

def extract_mutopia_header(ly_source: str) -> dict[str, str]:
    """Extract Mutopia metadata fields from LilyPond \\header block."""
    header = {}
    # Match \header { ... } block
    header_match = re.search(r'\\header\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', ly_source, re.DOTALL)
    if not header_match:
        return header

    header_text = header_match.group(1)
    for field in MUTOPIA_HEADER_FIELDS:
        # Match field = "value" or field = value
        match = re.search(rf'{field}\s*=\s*"([^"]*)"', header_text)
        if match:
            header[field] = match.group(1)
    return header
```

### MIDI Block Injection
```python
# Source: LilyPond docs (https://lilypond.org/doc/v2.25/Documentation/notation/creating-midi-output)
def ensure_midi_block(ly_source: str) -> str:
    """Inject \\midi {} into \\score {} block if not already present."""
    if r'\midi' in ly_source:
        return ly_source  # Already has MIDI block

    # Find \layout {} and add \midi {} after it
    layout_match = re.search(r'(\\layout\s*\{[^}]*\})', ly_source)
    if layout_match:
        insert_pos = layout_match.end()
        return ly_source[:insert_pos] + '\n  \\midi { }\n' + ly_source[insert_pos:]

    # No \layout either -- find \score { and insert both
    score_match = re.search(r'(\\score\s*\{)', ly_source)
    if score_match:
        # Insert before the closing brace of \score -- requires more careful parsing
        # Simplified: insert after the opening brace
        pass

    return ly_source  # Could not inject; log and proceed without MIDI
```

### Structured Description Template
```python
# Source: User decision -- templated from extracted metadata
def generate_description(
    key_sig: str,
    time_sig: str,
    tempo: str,
    instrument: str,
    clef: str,
    bar_start: int,
    bar_end: int,
    note_density: float,
    dynamic_range: str,
    articulation_count: int,
    has_chord_symbols: bool,
    composer: str,
    era: str,
    ensemble_type: str,
    source: str,
) -> str:
    """Generate structured text description for embedding."""
    parts = [
        f"Key: {key_sig}." if key_sig else "",
        f"Time: {time_sig}." if time_sig else "",
        f"Tempo: {tempo}." if tempo else "",
        f"Instrument: {instrument}, {clef} clef." if instrument else "",
        f"Bars {bar_start}-{bar_end}.",
        f"Note density: {note_density:.1f} notes/bar." if note_density else "",
        f"Dynamic range: {dynamic_range}." if dynamic_range else "",
        f"Articulations: {articulation_count}." if articulation_count else "",
        f"Chord symbols: {'yes' if has_chord_symbols else 'none'}.",
        f"Composer: {composer}." if composer else "",
        f"Era: {era}." if era else "",
        f"Ensemble: {ensemble_type}." if ensemble_type else "",
        f"Source: {source}.",
    ]
    return " ".join(p for p in parts if p)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ChromaDB duckdb+parquet backend | ChromaDB 1.x with Rust-based storage | Mid-2025 | Faster queries, better persistence, breaking API changes from 0.x |
| python-ly only parser | quickly (parce-based) successor in development | 2024-ongoing | python-ly still works but successor uses modern parser architecture; quickly not yet production-ready |
| all-MiniLM-L6-v2 default | nomic-embed-text-v2-moe (MoE architecture) | Feb 2025 | Better retrieval quality at similar speed; 475M total params, 305M active |
| PDMX v1 (data + metadata only, 1.6 GB) | PDMX v2 (includes MXL, MIDI, PDF, 14.4 GB) | 2025 | v2 includes pre-converted MusicXML files we can use directly |

**Deprecated/outdated:**
- ChromaDB 0.x API (pre-1.0): Collection API changed significantly; examples from pre-2025 may use deprecated methods
- python-ly documentation on readthedocs is for 0.9.5 (latest release is 0.9.9) -- some APIs may have changed

## Open Questions

1. **python-ly on Python 3.12+**
   - What we know: PyPI lists support for 3.8-3.11; Gentoo packages for 3.12-3.14; pure Python library
   - What's unclear: Whether any Python 3.12 breaking changes (e.g., removed distutils, changed typing) affect python-ly 0.9.9
   - Recommendation: Install and test early. If broken, evaluate `quickly` or fall back to regex-only parsing with reduced reliability. LOW risk given pure Python codebase.

2. **Optimal embedding model for music metadata descriptions**
   - What we know: all-MiniLM-L6-v2 is fast and good for general text; nomic-embed-text-v2-moe has better retrieval quality; neither is trained on music-specific text
   - What's unclear: Whether general embedding models distinguish between "swing style, brass, forte" and "straight 8s, strings, piano" effectively enough for useful retrieval ranking
   - Recommendation: Start with all-MiniLM-L6-v2 (ChromaDB default, zero config). Build the embedding function interface to be swappable. Evaluate retrieval quality after corpus is built; upgrade to nomic-embed-text-v2-moe only if needed.

3. **PDMX download size and subset selection**
   - What we know: Full PDMX v2 is 14.4 GB; mxl.tar.gz alone is 1.9 GB for 254K scores; rated+deduplicated subset is ~13K scores
   - What's unclear: Whether the rated subset has adequate genre diversity for big band jazz retrieval (PDMX is heavily classical/folk)
   - Recommendation: Download mxl.tar.gz only (1.9 GB). Start with the rated+deduplicated subset (~13K). This is sufficient for the 10K+ chunk target. Expand later if retrieval quality demands it.

4. **Chunk overlap strategy**
   - What we know: Overlap ensures context continuity; too much overlap wastes storage
   - What's unclear: Optimal overlap for musical phrase retrieval (1 bar? 2 bars? 0?)
   - Recommendation: Start with 0 overlap (non-overlapping chunks at structural boundaries, fallback to 4-8 bar windows). Music phrases at structural boundaries are naturally self-contained. Add overlap later if retrieval misses cross-boundary patterns.

5. **Repeat/D.S./coda handling**
   - What we know: LilyPond `\repeat volta` and `\repeat segno` wrap repeated sections; expanding them would duplicate content
   - What's unclear: Whether expanding repeats produces better retrieval examples (longer contexts) or worse ones (redundant content)
   - Recommendation: Chunk as-written (don't expand repeats). A repeated section is the same music -- expanding it just creates duplicates. The chunk should contain the `\repeat` block as a structural element.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-bdd |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=engrave --cov-report=term-missing` |
| Estimated runtime | ~15 seconds (once corpus fixtures are built) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORP-01 | Mutopia scores ingested as (LilyPond, MIDI, description) triples in ChromaDB | integration | `pytest tests/integration/test_mutopia_ingest.py -x` | No -- Wave 0 gap |
| CORP-02 | PDMX MusicXML converted via musicxml2ly and indexed | integration | `pytest tests/integration/test_pdmx_ingest.py -x` | No -- Wave 0 gap |
| CORP-03 | Retrieval by metadata + embedding similarity returns relevant results | integration | `pytest tests/integration/test_retrieval.py -x` | No -- Wave 0 gap |
| CORP-04 | Phrase-level chunking expands scores into 10K+ examples | unit | `pytest tests/unit/test_chunker.py -x` | No -- Wave 0 gap |
| -- | ChromaDB store CRUD operations | unit | `pytest tests/unit/test_store.py -x` | No -- Wave 0 gap |
| -- | Metadata extraction from LilyPond source | unit | `pytest tests/unit/test_metadata.py -x` | No -- Wave 0 gap |
| -- | Structured description generation | unit | `pytest tests/unit/test_description.py -x` | No -- Wave 0 gap |
| -- | Mutopia header parsing | unit | `pytest tests/unit/test_mutopia_header.py -x` | No -- Wave 0 gap |
| -- | MIDI block injection | unit | `pytest tests/unit/test_midi_injection.py -x` | No -- Wave 0 gap |
| -- | LilyPond boundary detection for chunking | unit | `pytest tests/unit/test_boundaries.py -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `pytest tests/ -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_chunker.py` -- covers CORP-04 (phrase boundary detection, bar-count fallback, multi-part vertical chunks)
- [ ] `tests/unit/test_store.py` -- covers ChromaDB wrapper (add, query, metadata filter, collection lifecycle)
- [ ] `tests/unit/test_metadata.py` -- covers metadata extraction from LilyPond source
- [ ] `tests/unit/test_description.py` -- covers structured description templating
- [ ] `tests/unit/test_mutopia_header.py` -- covers Mutopia header field extraction
- [ ] `tests/unit/test_midi_injection.py` -- covers `\midi {}` block injection logic
- [ ] `tests/unit/test_boundaries.py` -- covers structural boundary pattern matching
- [ ] `tests/integration/test_mutopia_ingest.py` -- covers CORP-01 (end-to-end Mutopia ingestion with fixtures)
- [ ] `tests/integration/test_pdmx_ingest.py` -- covers CORP-02 (end-to-end PDMX conversion + ingestion with fixtures)
- [ ] `tests/integration/test_retrieval.py` -- covers CORP-03 (hybrid retrieval with pre-populated test corpus)
- [ ] `tests/fixtures/corpus/` -- sample LilyPond scores for testing (2-3 small scores, varying complexity)
- [ ] `tests/fixtures/musicxml/` -- sample MusicXML files for testing musicxml2ly conversion
- [ ] `tests/conftest.py` -- extend with corpus-specific fixtures (ChromaDB test client, sample scores)

## Sources

### Primary (HIGH confidence)
- [ChromaDB PyPI](https://pypi.org/project/chromadb/) -- version 1.5.1, Feb 2026
- [ChromaDB Docs: Usage Guide](https://docs.trychroma.com/guides) -- API patterns
- [ChromaDB Docs: Metadata Filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering) -- filter operators
- [ChromaDB Docs: Embedding Functions](https://docs.trychroma.com/docs/embeddings/embedding-functions) -- supported providers, custom functions
- [ChromaDB Docs: Persistent Client](https://docs.trychroma.com/docs/run-chroma/persistent-client) -- PersistentClient setup
- [Mutopia Project GitHub](https://github.com/MutopiaProject/MutopiaProject) -- repository structure, 2,124 pieces
- [Mutopia Project Contribution Guide](https://www.mutopiaproject.org/contribute.html) -- header field specification
- [PDMX GitHub](https://github.com/pnlong/PDMX) -- dataset documentation, API
- [PDMX Zenodo v2](https://zenodo.org/records/15571083) -- download, 254K scores, 14.4 GB total (mxl.tar.gz = 1.9 GB)
- [PDMX Zenodo v1](https://zenodo.org/records/13763756) -- original release, 1.6 GB
- [python-ly PyPI](https://pypi.org/project/python-ly/) -- v0.9.9, Jan 2025
- [python-ly GitHub](https://github.com/frescobaldi/python-ly) -- modules, parser architecture
- [python-ly Documentation](https://python-ly.readthedocs.io/en/latest/ly.html) -- ly.lex, ly.music, ly.document API
- [LilyPond Notation Reference: Bars](https://lilypond.org/doc/v2.25/Documentation/notation/bars) -- barline syntax
- [LilyPond Notation Reference: Long Repeats](https://lilypond.org/doc/v2.25/Documentation/notation/long-repeats) -- repeat/volta/segno syntax
- [LilyPond Notation Reference: MIDI Output](https://lilypond.org/doc/v2.25/Documentation/notation/creating-midi-output) -- \midi block requirement

### Secondary (MEDIUM confidence)
- [PDMX arXiv Paper (HTML)](https://arxiv.org/html/2409.10831v2) -- MusicRender fields, deduplication, genre stats, quality filtering
- [Nomic Embed Text V2 HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe) -- MoE architecture, 475M params, 305M active
- [sentence-transformers/all-MiniLM-L6-v2 HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) -- 22M params, 384-dim
- [BentoML: Best Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models) -- model comparison

### Tertiary (LOW confidence)
- [quickly (python-ly successor) GitHub](https://github.com/frescobaldi/quickly) -- "early development stage"; not yet usable for production
- python-ly Python 3.12 compatibility -- inferred from Gentoo packaging but not verified by PyPI classifiers or CI

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM -- ChromaDB and python-ly are well-documented, but the combination for music corpus retrieval is novel; no existing examples found
- Architecture: MEDIUM -- patterns are derived from ChromaDB best practices and LilyPond domain knowledge, but not validated by prior art in this specific domain
- Pitfalls: HIGH -- version mismatches, MIDI block injection, and conversion quality are well-documented issues in the LilyPond and Mutopia communities

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (ChromaDB stable; python-ly slow-moving; PDMX dataset fixed)
