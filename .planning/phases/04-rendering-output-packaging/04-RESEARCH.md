# Phase 4: Rendering & Output Packaging - Research

**Researched:** 2026-02-24
**Domain:** LilyPond rendering, part extraction, transposition, score layout, ZIP packaging
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Conductor Score Layout:**
  - Paper: tabloid (11x17") landscape as default, configurable via engrave.toml
  - Bracketing: section-level brackets per SCORING_GUIDE.md -- Saxophones bracket, Trumpets bracket, Trombones bracket, Rhythm Section brace (with curly brace on piano grand staff)
  - Empty staves: hide empty staves on all systems except the first (which always shows all instruments)
  - Pitch: concert pitch only -- never generate a transposed conductor score
  - Chord symbols: display above the top staff (Alto Sax 1 line) on the conductor score, in addition to rhythm section parts
- **Part Extraction & Transposition:**
  - Transposition mechanism: LilyPond's `\transpose` command applied at render time -- concert-pitch music is the single source of truth
  - File architecture: shared music-definitions.ly containing all concert-pitch content, with separate part-{instrument}.ly files that `\include` the shared music and apply `\transpose`
  - Paper: letter (8.5x11") portrait as default, configurable (A4 option) via engrave.toml
  - Transposition verification: round-trip check -- transpose to reading key, transpose back to concert, diff against original to catch any bugs
  - Transposition table: use the exact table from docs/SCORING_GUIDE.md (Alto/Bari = Eb, Tenor/Trumpet = Bb, Trombone/Bass Trombone = C in bass clef, Rhythm = C)
- **Rehearsal Marks & Multi-bar Rests:**
  - Rehearsal marks: sequential letters (A, B, C...) at structural landmarks, with A always anchored at the start of the head
  - Section names: optional secondary text below the letter mark (e.g., "Swing" or "Shout Chorus" below [B])
  - Studio mode: when flagged (via user hint or config), switch to bar numbers on every measure with no rehearsal letters -- for recording session use
  - Multi-bar rests: traditional H-bar notation (LilyPond's `\compressFullBarRests`), number above horizontal bar
  - Multi-bar rest breaks: always break multi-bar rests at rehearsal marks -- never show a monolithic rest spanning a structural boundary
  - Dynamic restatement: always restate the current dynamic at any entrance following 2+ bars of rest -- this rule aligns with the multi-bar rest consolidation threshold (one unified rule)
  - Measure numbers: display at the start of every system in parts; also display on multi-bar rest glyphs
- **ZIP Packaging:**
  - Structure: flat with prefixes -- all files at ZIP root (score.pdf, part-trumpet-1.pdf, part-alto-sax-1.pdf, music-definitions.ly, part-trumpet-1.ly, output.mid, etc.)
  - Naming: {song-title}-{YYYY-MM-DD}.zip (slugified song title + generation date)
  - Contents: always include all outputs -- conductor score PDF, all 17 instrument part PDFs, all .ly source files, MIDI file
  - No user selection of parts in v1 -- all parts always included

### Claude's Discretion
- Staff sizes and spacing for conductor score vs parts
- Exact LilyPond stylesheet/layout block parameters
- Font choices for rehearsal marks, measure numbers, and text annotations
- How to derive song title from input (MIDI metadata, filename, user hint)
- Error handling when LilyPond compilation fails during part extraction
- Tempo/style text formatting at top of parts

### Deferred Ideas (OUT OF SCOPE)
- Cue notes after 8+ bars rest -- Phase 8 (ENGR-06)
- Page turn optimization (turns at rests only) -- Phase 8 (ENGR-10)
- Repeat signs, D.S. al Coda, first/second endings -- Phase 8 (ENGR-07)
- Chord chart / lead sheet output -- Phase 8 (ENGR-08)
- Style-aware beaming (jazz vs straight) -- Phase 7 (ENGR-05)
- Joint section generation for convergent sight-reading -- Phase 7 (ENSM-02)
- Part selection/filtering (--parts flag) -- could be added later if needed
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FNDN-06 | System packages output as a ZIP containing selected PDFs, LilyPond source files, and MusicXML export | Python `zipfile` stdlib module; flat ZIP structure with `\bookOutputName` controlling PDF filenames; MIDI generated via `\midi` block |
| ENGR-01 | System renders a full conductor score PDF with standard instrument ordering, system brackets/braces, landscape orientation for big band | LilyPond `StaffGroup`/`GrandStaff` contexts with `systemStartDelimiterHierarchy`; tabloid landscape via `#(set-paper-size "tabloid" 'landscape)`; `\RemoveEmptyStaves` with first-system exception |
| ENGR-02 | System renders one extracted part PDF per instrument, correctly transposed to reading key with proper clef and key signature | `\transpose` at render time in per-part .ly files; `\include "music-definitions.ly"` pattern; `\bookOutputName` for filename control |
| ENGR-03 | Parts include rehearsal marks, measure numbers at start of each line, and consolidated multi-bar rests | `\mark \default` for sequential letters; `\compressMMRests` for H-bar rests; `\override Score.BarNumber.break-visibility` for measure numbers at every system |
| ENGR-04 | Parts include dynamic markings with restatement after multi-bar rests | Post-processing pass inserts dynamic restatement at every entrance after 2+ bars rest; dynamics tracked through concert-pitch source |
| ENGR-09 | LilyPond source files (.ly) always included in output ZIP | Direct file inclusion in ZIP from work directory; music-definitions.ly + all part-*.ly files |
| ENSM-01 | Big band ensemble preset: 5 saxes (AATBT), 4 trumpets, 4 trombones, piano, guitar, bass, drums with correct transpositions, clefs, score order, staff sizes | Ensemble preset dataclass encoding all 17 instruments with transposition intervals, clefs, staff group assignments, and score ordering |
| ENSM-04 | Chord symbols on rhythm section parts (guitar, piano, bass) above the staff | LilyPond `ChordNames` context with `\chordmode`; `\chords` shorthand placed above `\new Staff` in `<<>>` parallel |
</phase_requirements>

## Summary

Phase 4 transforms the concert-pitch LilyPond source produced by Phase 3 into a professional output package: a full conductor score PDF, 17 individual transposed part PDFs, and a ZIP bundle containing all PDFs, source files, and MIDI. The primary technical domain is LilyPond's rendering pipeline, specifically its `\book`/`\bookOutputName` system for generating multiple PDFs, the `\transpose` command for deterministic part transposition, and the `StaffGroup`/`GrandStaff` context hierarchy for conductor score layout.

The architecture follows a well-established LilyPond pattern: a shared `music-definitions.ly` file stores all concert-pitch music variables (produced by Phase 3's assembler), and separate per-instrument `.ly` files `\include` that shared file, applying `\transpose` and part-specific formatting (compressed rests, rehearsal marks, chord symbols). This is exactly the architecture described in the official LilyPond Learning Manual's "Scores and parts" section. The conductor score `.ly` file includes the same shared definitions but renders all instruments in concert pitch with full-score layout.

**Primary recommendation:** Build a `src/engrave/rendering/` package with three modules: (1) an ensemble preset system encoding the 17-instrument big band configuration, (2) a LilyPond file generator that produces the shared definitions file, per-instrument part files, and conductor score file from Phase 3 output, and (3) a packager that orchestrates LilyPond compilation and ZIP assembly.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LilyPond | 2.24.4 (stable) | Music notation rendering to PDF and MIDI | Only production-quality open-source music engraver; project already depends on it via Phase 1 compiler |
| Python `zipfile` | stdlib (Python 3.12) | ZIP archive creation | Standard library, no external dependency; sufficient for flat archive with deflate compression |
| Python `pathlib` | stdlib | File path manipulation for work directories | Already used throughout codebase (Phase 1) |
| Python `tempfile` | stdlib | Temporary work directories for compilation | Already used in Phase 1 compiler; needed for isolated compilation runs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `slugify` (python-slugify) | 8.x | Song title slugification for ZIP filename | When deriving ZIP filename from song title; handles Unicode, special chars |
| Python `shutil` | stdlib | Directory cleanup, file copying | Work directory management during compilation |
| Python `subprocess` | stdlib | LilyPond invocation (already wrapped in compiler.py) | Extended via existing `LilyPondCompiler` class |
| Python `difflib` | stdlib | Round-trip transposition verification | Compare original concert pitch vs retransposed output for correctness check |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-slugify | `re.sub` manual slugification | python-slugify handles Unicode edge cases (accented chars in song titles) properly; manual regex is fragile |
| `zipfile` (stdlib) | `shutil.make_archive` | `shutil.make_archive` is simpler for directory-to-zip but gives less control over flat structure and individual file naming |
| Multiple LilyPond invocations (one per .ly file) | Single .ly with multiple `\book` blocks | Separate files are more debuggable, editable in Frescobaldi, and match the user decision for file architecture |

**Installation:**
```bash
uv add python-slugify
```

## Architecture Patterns

### Recommended Project Structure
```
src/engrave/
  rendering/
    __init__.py          # Re-exports public API
    ensemble.py          # BigBandPreset, InstrumentSpec dataclasses
    generator.py         # LilyPond file generation (score, parts, shared defs)
    packager.py          # Compilation orchestration + ZIP assembly
    stylesheet.py        # LilyPond layout/paper block constants
  lilypond/              # (existing from Phase 1)
    compiler.py          # LilyPondCompiler -- reused for PDF generation
    parser.py            # Error parser -- reused for error handling
    fixer.py             # Compile-fix loop -- reused for compilation retries
```

### Pattern 1: Ensemble Preset as Data
**What:** Encode the entire big band instrumentation as a structured data model, not as template strings.
**When to use:** Always -- the preset drives score ordering, transposition, bracketing, and part file generation.
**Example:**
```python
# Source: Project-specific pattern derived from SCORING_GUIDE.md
from dataclasses import dataclass
from enum import Enum

class StaffGroupType(Enum):
    BRACKET = "bracket"   # Saxes, Trumpets, Trombones
    BRACE = "brace"       # Rhythm section
    GRAND_STAFF = "grand_staff"  # Piano only

@dataclass(frozen=True)
class InstrumentSpec:
    name: str                    # "Alto Sax 1"
    short_name: str              # "A.Sx. 1"
    variable_name: str           # "altoSaxOne"
    concert_to_written: str      # LilyPond transpose interval: "c a"  (Eb instrument)
    clef: str                    # "treble" | "bass" | "percussion"
    section: str                 # "Saxophones" | "Trumpets" | "Trombones" | "Rhythm"
    group_type: StaffGroupType   # bracket or brace
    score_order: int             # 0-16, top to bottom
    has_chord_symbols: bool      # True for piano, guitar, bass
    is_transposing: bool         # True if concert_to_written != "c c"

@dataclass(frozen=True)
class BigBandPreset:
    instruments: tuple[InstrumentSpec, ...]
    name: str = "Big Band"
```

### Pattern 2: Shared Music Definitions + Per-Part Files
**What:** Generate a `music-definitions.ly` file containing all concert-pitch music variables, then generate separate `.ly` files for each part and the conductor score that `\include` the shared file.
**When to use:** Always -- this is the user-locked file architecture decision.
**Example architecture:**
```
work_dir/
  music-definitions.ly    # All concert-pitch music as LilyPond variables
  score.ly                # Conductor score: \include "music-definitions.ly", full layout
  part-alto-sax-1.ly      # \include "music-definitions.ly", \transpose c a \altoSaxOne
  part-trumpet-1.ly       # \include "music-definitions.ly", \transpose c d \trumpetOne
  ...
```

**music-definitions.ly pattern:**
```lilypond
% Source: LilyPond Learning Manual "Scores and parts"
% https://lilypond.org/doc/v2.24/Documentation/learning/scores-and-parts
\version "2.24.4"

% Concert-pitch music definitions (single source of truth)
globalMusic = {
  \key bes \major
  \time 4/4
  \tempo "Medium Swing" 4 = 132
  % ... rehearsal marks, structure
}

altoSaxOne = \relative c'' {
  % concert-pitch music
}

trumpetOne = \relative c' {
  % concert-pitch music
}

% ... all 17 instruments
chordSymbols = \chordmode {
  bes1:7 | ees:7 | bes:7 | bes:7 |
  % ...
}
```

### Pattern 3: LilyPond Multi-Book Output with `\bookOutputName`
**What:** Each `.ly` file produces exactly one PDF via a single `\book` block with `\bookOutputName` controlling the filename.
**When to use:** For both the conductor score and each part file.
**Example:**
```lilypond
% Source: LilyPond Notation Reference 3.2.4
% https://lilypond.org/doc/v2.24/Documentation/notation/output-file-names
\book {
  \bookOutputName "part-trumpet-1"
  \header { instrument = "Trumpet 1" }
  \score {
    <<
      \new ChordNames { \chordSymbols }  % only for rhythm section
      \new Staff \with {
        instrumentName = "Trumpet 1"
        shortInstrumentName = "Tpt. 1"
      } {
        \compressMMRests {
          \transpose c d  % Bb instrument: concert C sounds as written D
          \trumpetOne
        }
      }
    >>
    \layout { }
    \midi { }   % MIDI output for packaged ZIP
  }
}
```

### Pattern 4: Conductor Score Layout with Staff Groups
**What:** Use nested `StaffGroup` and `GrandStaff` contexts to produce standard big band bracketing.
**When to use:** Conductor score file only.
**Example:**
```lilypond
% Source: LilyPond Notation Reference 1.6.1 / SCORING_GUIDE.md
\book {
  \bookOutputName "score"
  #(set-global-staff-size 14)  % Smaller for conductor score
  \paper {
    #(set-paper-size "tabloid" 'landscape)
  }
  \score {
    <<
      \new ChordNames { \chordSymbols }  % Above top staff

      \new StaffGroup = "Saxophones" <<
        \new Staff \with { instrumentName = "Alto Sax 1" } \altoSaxOne
        \new Staff \with { instrumentName = "Alto Sax 2" } \altoSaxTwo
        % ... Tenor 1, Tenor 2, Bari
      >>

      \new StaffGroup = "Trumpets" <<
        \new Staff \with { instrumentName = "Trumpet 1" } \trumpetOne
        % ... Trumpet 2, 3, 4
      >>

      \new StaffGroup = "Trombones" <<
        \new Staff \with { instrumentName = "Trombone 1" } \tromboneOne
        % ... Trombone 2, 3, Bass Trombone
      >>

      \new StaffGroup = "Rhythm" \with {
        systemStartDelimiter = #'SystemStartBrace
      } <<
        \new PianoStaff = "Piano" <<
          \new Staff \pianoRight
          \new Staff \pianoLeft
        >>
        \new Staff \with { instrumentName = "Guitar" } \guitar
        \new Staff \with { instrumentName = "Bass" } \bass
        \new DrumStaff \with { instrumentName = "Drums" } \drums
      >>
    >>
    \layout {
      \context {
        \Staff
        \RemoveEmptyStaves
        \override VerticalAxisGroup.remove-first = ##f  % Keep first system complete
      }
    }
  }
}
```

### Pattern 5: Round-Trip Transposition Verification
**What:** Verify transposition correctness by transposing to reading key and back, diffing against original.
**When to use:** As a post-generation safety check, before final packaging.
**Example:**
```python
# Pseudocode for round-trip verification
def verify_transposition(
    original_concert: str,
    instrument: InstrumentSpec,
    compiler: LilyPondCompiler,
) -> bool:
    """Transpose to reading key, back to concert, diff."""
    # Build: \transpose c written_pitch \music -> reading key
    # Then:  \transpose written_pitch c \transposed_music -> back to concert
    # Compile both, compare MIDI output note-by-note
    # Or: use LilyPond's display-lily-music to compare text output
    pass
```

### Anti-Patterns to Avoid
- **Embedding transposition in music-definitions.ly:** The shared file MUST contain only concert-pitch music. Transposition belongs exclusively in per-part .ly files at render time.
- **Using `\relative` with `\transpose`:** `\transpose` must wrap `\relative`, not the other way around. However, per Phase 3's decision, all music is in absolute pitch mode (no `\relative` at all), so this anti-pattern is already avoided.
- **One giant .ly file with multiple `\book` blocks:** While LilyPond supports this, separate files per part are more debuggable, editable in Frescobaldi, and align with the user decision.
- **Hardcoding LilyPond layout parameters in generation code:** Extract all `\paper` and `\layout` settings into a stylesheet module for maintainability.
- **Generating MIDI separately from PDF:** LilyPond can produce both PDF and MIDI from a single `\score` block containing both `\layout {}` and `\midi {}`. Generate MIDI from the conductor score compilation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Music transposition | Custom pitch arithmetic | LilyPond `\transpose c <target>` | LilyPond handles enharmonic spelling, key signatures, accidentals correctly; hand-rolled transposition is a source of subtle bugs |
| Multi-bar rest consolidation | Custom rest-merging code | LilyPond `\compressMMRests` | LilyPond natively consolidates consecutive full-bar rests into H-bar notation with count |
| Staff grouping / bracketing | Manual bracket positioning | LilyPond `StaffGroup`, `GrandStaff`, `systemStartDelimiter` | LilyPond's context hierarchy handles bracket nesting, bar line continuation, and system start delimiters |
| PDF generation | External PDF library | LilyPond `--pdf` flag | LilyPond produces publication-quality PDFs with precise typography |
| MIDI generation | Custom MIDI writer | LilyPond `\midi {}` block in `\score` | LilyPond renders dynamics, tempo, and instrument assignments to MIDI natively |
| Chord symbol rendering | Manual text placement | LilyPond `ChordNames` context + `\chordmode` | LilyPond handles jazz chord naming (Ignatzek system), placement, and alignment |
| ZIP archive creation | Manual binary format | Python `zipfile` stdlib | Well-tested, handles compression and encoding correctly |
| Song title slugification | Manual regex | python-slugify | Handles Unicode, diacritics, special characters that arise in song titles |

**Key insight:** LilyPond is a full typesetting engine. The rendering phase should generate correct `.ly` files and let LilyPond handle all layout, transposition, rest consolidation, and PDF production. The Python code's job is orchestration and file management, not music typesetting.

## Common Pitfalls

### Pitfall 1: `\compressFullBarRests` vs `\compressMMRests` vs `\compressEmptyMeasures`
**What goes wrong:** Using the wrong command name for the LilyPond version, causing compilation failure.
**Why it happens:** LilyPond renamed these commands across versions. In v2.24 (our target):
- `\compressMMRests` -- wraps a music expression and compresses multi-measure rests within it (CORRECT for part extraction)
- `\compressEmptyMeasures` -- renamed from `\compressFullBarRests` in v2.21, works as a toggle
- `\compressFullBarRests` -- deprecated alias, may still work but should not be used
**How to avoid:** Always use `\compressMMRests { ... }` wrapping the entire music expression in part files. Despite the user's CONTEXT.md referencing `\compressFullBarRests`, the implementation must use `\compressMMRests` for LilyPond 2.24 compatibility.
**Warning signs:** Compilation warning about deprecated commands; rests not consolidating.

### Pitfall 2: `\transpose` Direction for Transposing Instruments
**What goes wrong:** Transposing in the wrong direction, producing parts a tritone off or in the wrong octave.
**Why it happens:** `\transpose c d` means "transpose UP from C to D" -- concert C becomes written D. For a Bb instrument (trumpet), concert C sounds when the player reads D, so `\transpose c d` is correct (concert -> written). Getting the direction wrong is a common error.
**How to avoid:** Use the SCORING_GUIDE.md transposition table verbatim. Test with a known passage (concert C major scale) and verify the transposed output matches expected reading key. The round-trip verification catches this automatically.
**Warning signs:** Parts sound wrong when played; key signatures don't match expected values.

### Pitfall 3: Baritone Sax Octave Transposition
**What goes wrong:** Baritone sax part is in the correct key (Eb) but the wrong octave.
**Why it happens:** Baritone sax is an Eb instrument that sounds an octave lower than alto sax. The `\transpose` interval must account for both the key and the octave: `\transpose c a,` (down to A below middle C), not `\transpose c a` (which would be alto sax transposition).
**How to avoid:** Encode the exact octave in the InstrumentSpec transposition interval. Verify with known passages.
**Warning signs:** Bari sax part written an octave too high or too low.

### Pitfall 4: Rehearsal Mark Breaks in Multi-bar Rests
**What goes wrong:** Multi-bar rests span across rehearsal marks, producing a single long rest that hides structural boundaries.
**Why it happens:** `\compressMMRests` consolidates ALL consecutive full-bar rests unless interrupted by a rehearsal mark or other event.
**How to avoid:** Rehearsal marks must be placed in the music stream before compression. Since rehearsal marks are in `globalMusic` (shared structure), they must be applied to each instrument's music via `<<>>` parallel combination before `\compressMMRests` wraps the result. Pattern: `\compressMMRests { << \globalMusic \instrumentMusic >> }`.
**Warning signs:** Players report missing rehearsal marks in their rests; long rests without section breaks.

### Pitfall 5: `\RemoveEmptyStaves` Removing the First System
**What goes wrong:** The conductor score's first system hides instruments that happen to rest at the beginning.
**Why it happens:** `\RemoveEmptyStaves` removes empty staves from ALL systems by default.
**How to avoid:** Use `\RemoveEmptyStaves` (NOT `\RemoveAllEmptyStaves`). The standard `\RemoveEmptyStaves` preserves the first system. Verify with `\override VerticalAxisGroup.remove-first = ##f` if needed.
**Warning signs:** First page of conductor score missing instruments.

### Pitfall 6: ChordNames Context Placement
**What goes wrong:** Chord symbols appear in wrong position or don't align with the music.
**Why it happens:** `ChordNames` must be placed OUTSIDE and BEFORE the `Staff` it should align with in the `<<>>` parallel block. If placed inside a `StaffGroup`, it inherits the group's bracketing incorrectly.
**How to avoid:** Place `\new ChordNames` at the very top of the score's `<<>>` block (before any `StaffGroup`), or directly above the target staff in part files within their own `<<>>` block.
**Warning signs:** Chord symbols inside brackets, misaligned with beats, or missing entirely.

### Pitfall 7: Compilation Timeout with Large Scores
**What goes wrong:** LilyPond compilation of the full conductor score (17 staves, multiple pages) exceeds the default 60-second timeout.
**Why it happens:** Full big band scores are complex; LilyPond's line-breaking and page-breaking algorithms are computationally expensive for large scores.
**How to avoid:** Use a longer timeout for conductor score compilation (180-300 seconds) vs individual parts (60 seconds). The existing `LilyPondCompiler` already accepts a `timeout` parameter.
**Warning signs:** Compilation "fails" but works fine when run manually with no timeout.

### Pitfall 8: Dynamic Restatement Requires Source Analysis
**What goes wrong:** Dynamics after multi-bar rests are missing because the original music has no restatement.
**Why it happens:** Phase 3's LLM generates concert-pitch music section by section. It may not consistently restate dynamics after rests, especially at section boundaries.
**How to avoid:** Implement a post-processing pass in the generator that analyzes the concert-pitch source for each instrument, tracks the "current dynamic," and inserts a restatement at any entrance following 2+ bars of rest. This is a text-processing operation on the LilyPond source, not something LilyPond handles natively.
**Warning signs:** Players have no dynamic indication after long rests; dynamics drift.

## Code Examples

Verified patterns from official sources:

### Tabloid Landscape Paper for Conductor Score
```lilypond
% Source: LilyPond Notation Reference 4.1.2
% https://lilypond.org/doc/v2.24/Documentation/notation/paper-size-and-automatic-scaling
\paper {
  #(set-paper-size "tabloid" 'landscape)
}
```

### Letter Portrait for Parts
```lilypond
% Source: LilyPond Notation Reference 4.1.2
\paper {
  #(set-paper-size "letter")
}
```

### Staff Size for Conductor Score vs Parts
```lilypond
% Source: LilyPond Notation Reference 4.2.2
% https://lilypond.org/doc/v2.24/Documentation/notation/setting-the-staff-size

% Conductor score: smaller staves to fit 17+ instruments
#(set-global-staff-size 14)  % 4.92mm staff height (default is 20 = 7.03mm)

% Individual parts: standard size
#(set-global-staff-size 20)  % 7.03mm (default)
```

### Transposition for Bb Trumpet
```lilypond
% Source: LilyPond Notation Reference 1.1.2
% https://lilypond.org/doc/v2.24/Documentation/notation/changing-multiple-pitches

% Concert C becomes written D (up a major 2nd)
\transpose c d \trumpetOneConcert

% For verification: transpose back should match original
\transpose d c \transpose c d \trumpetOneConcert
% Result should be identical to \trumpetOneConcert
```

### Eb Alto Sax Transposition
```lilypond
% Alto sax: concert C sounds when player reads A above
% \transpose c a means: concert C -> written A (up major 6th)
\transpose c a \altoSaxOneConcert
```

### Eb Baritone Sax Transposition (with octave)
```lilypond
% Bari sax: Eb instrument sounding octave lower than alto
% \transpose c a, means: concert C -> written A below middle C
\transpose c a, \baritoneSaxConcert
```

### Multi-Bar Rest Compression with Rehearsal Marks
```lilypond
% Source: LilyPond Notation Reference 1.6.3
% https://lilypond.org/doc/v2.24/Documentation/notation/writing-parts

\compressMMRests {
  <<
    \globalMusic  % Contains rehearsal marks, tempo, time sig
    \transpose c d \trumpetOneConcert
  >>
}
```

### Chord Symbols Above Staff
```lilypond
% Source: LilyPond Notation Reference 2.7.2
% https://lilypond.org/doc/v2.24/Documentation/notation/displaying-chords

<<
  \new ChordNames {
    \set chordChanges = ##t  % Only show when chord changes
    \chordSymbols
  }
  \new Staff \with {
    instrumentName = "Guitar"
    shortInstrumentName = "Gtr."
  } {
    \compressMMRests {
      <<
        \globalMusic
        \guitarConcert
      >>
    }
  }
>>
```

### Measure Numbers at Every System Start
```lilypond
% Source: LilyPond Notation Reference 1.2.5
% https://lilypond.org/doc/v2.24/Documentation/notation/bars
\layout {
  \context {
    \Score
    \override BarNumber.break-visibility = ##(#f #f #t)
    % #(#f #f #t) = end-of-line:no, mid-line:no, beginning-of-line:yes
    barNumberVisibility = #first-bar-number-invisible
  }
}
```

### Studio Mode: Bar Numbers on Every Measure
```lilypond
% Source: LilyPond wiki / Notation Reference 1.2.5
\layout {
  \context {
    \Score
    barNumberVisibility = #all-bar-numbers-visible
    \override BarNumber.break-visibility = ##(#t #t #t)
  }
}
```

### Rehearsal Marks with Section Names
```lilypond
% Source: LilyPond Notation Reference
\mark \default  % Produces A, B, C... sequentially

% With section name below:
\mark \default
-\markup { \italic "Swing" }
```

### `\bookOutputName` for Part PDF Naming
```lilypond
% Source: LilyPond Notation Reference 3.2.4
% https://lilypond.org/doc/v2.24/Documentation/notation/output-file-names
\book {
  \bookOutputName "part-trumpet-1"
  \score { ... }
}
% Produces: part-trumpet-1.pdf
```

### Hide Empty Staves (Conductor Score)
```lilypond
% Source: LilyPond Notation Reference 1.6.2
% https://lilypond.org/doc/v2.24/Documentation/notation/modifying-single-staves
\layout {
  \context {
    \Staff
    \RemoveEmptyStaves
    % First system always shows all staves (default behavior)
  }
  \context {
    \StaffGroup
    \consists Keep_alive_together_engraver
    % Removes entire groups together, not individual staves
  }
}
```

### MIDI Output from Score
```lilypond
% Source: LilyPond Notation Reference 3.6.3
% https://lilypond.org/doc/v2.24/Documentation/notation/the-midi-block
\score {
  << ... music ... >>
  \layout { }  % PDF output
  \midi { }    % MIDI output (produces .mid file alongside .pdf)
}
```

### ZIP Packaging (Python)
```python
# Source: Python stdlib docs
# https://docs.python.org/3/library/zipfile.html
import zipfile
from pathlib import Path

def package_output(
    work_dir: Path,
    output_path: Path,
) -> Path:
    """Package all output files into a ZIP archive."""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf in work_dir.glob("*.pdf"):
            zf.write(pdf, pdf.name)  # Flat structure: just filename
        for ly in work_dir.glob("*.ly"):
            zf.write(ly, ly.name)
        for mid in work_dir.glob("*.mid"):
            zf.write(mid, mid.name)
    return output_path
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `\compressFullBarRests` | `\compressEmptyMeasures` (toggle) / `\compressMMRests` (wrapper) | LilyPond 2.21 (2020) | Must use `\compressMMRests` for wrapping pattern in v2.24 |
| Manual `\override` for hiding staves | `\RemoveEmptyStaves` predefined shorthand | LilyPond 2.18+ | Simpler syntax, same effect |
| `\set Score.currentBarNumber` for numbering | `barNumberVisibility` context property | LilyPond 2.20+ | Cleaner control over when bar numbers appear |
| Single-file multi-book output | Separate files with `\include` | Always available, but ecosystem preference shifted | Better for editor compatibility (Frescobaldi), version control, debugging |

**Deprecated/outdated:**
- `\compressFullBarRests`: Renamed to `\compressEmptyMeasures` in LilyPond 2.21. Use `\compressMMRests` instead for the wrapping pattern needed in part extraction.
- LilyPond 2.22/2.23: Development versions. Stable is 2.24.4 (July 2024). Development branch is 2.25.x.

## Open Questions

1. **Dynamic restatement implementation strategy**
   - What we know: LilyPond has no native "restate dynamic after rest" feature. This requires source-level post-processing.
   - What's unclear: Whether to implement this as a text-processing pass on the `.ly` source before compilation, or as a separate analysis step that injects dynamics into the music variables.
   - Recommendation: Implement as a pre-compilation text-processing pass on each instrument's music content. Parse the LilyPond text to track dynamics (`\pp`, `\p`, `\mp`, `\mf`, `\f`, `\ff`, `\sfz`, etc.) and detect entrances after multi-measure rests (sequences of `R` notes). Insert the last-known dynamic at each such entrance. This keeps the logic in Python and avoids modifying Phase 3's generation output.

2. **Song title derivation priority**
   - What we know: Need a song title for ZIP filename. Sources: MIDI metadata (track name / sequence name), input filename, user hint text.
   - What's unclear: Exact priority when multiple sources conflict.
   - Recommendation: Priority: (1) explicit user hint if provided, (2) MIDI metadata title/sequence name if present, (3) input filename stem. Fall back to "untitled" if all are empty.

3. **Piano grand staff handling**
   - What we know: Piano needs a `PianoStaff` (two staves with brace) in the conductor score and a `PianoStaff` in its part.
   - What's unclear: Whether Phase 3 generates separate `pianoRight` and `pianoLeft` variables or a single `piano` variable. The templates module would need to handle this.
   - Recommendation: The ensemble preset should define piano as requiring two variables (`pianoRight`, `pianoLeft`). Phase 3's template generation should be made aware of this. If Phase 3 is not yet modified, Phase 4 can handle a single `piano` variable by placing it on a single treble-clef staff initially, with grand staff as a later enhancement.

4. **Drum notation**
   - What we know: Drums use `DrumStaff` and `\drummode` in LilyPond, with a percussion clef.
   - What's unclear: Whether Phase 3 generates drum notation in `\drummode` syntax or standard note syntax.
   - Recommendation: The ensemble preset should flag drums as requiring `DrumStaff`. If Phase 3 outputs standard notes, wrap in `\drummode` at render time. This can be refined when Phase 3 is complete.

5. **Compilation parallelism**
   - What we know: 18 separate .ly files (1 score + 17 parts) need compilation. Sequential compilation could take 5-10 minutes.
   - What's unclear: Whether LilyPond handles concurrent invocations safely (no shared state issues).
   - Recommendation: LilyPond is a stateless command-line tool; concurrent subprocess invocations in separate work directories are safe. Use `asyncio.gather` or `concurrent.futures.ProcessPoolExecutor` for parallel compilation. Start with sequential compilation (simpler), add parallelism as an optimization if timing is an issue.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-bdd + pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/ -x --timeout=30` |
| Full suite command | `uv run pytest tests/ -x --timeout=120` |
| Estimated runtime | ~15 seconds (unit), ~45 seconds (full with compilation) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENGR-01 | Conductor score .ly has correct StaffGroup hierarchy, tabloid landscape, concert pitch | unit | `pytest tests/unit/test_score_generator.py -x` | No -- Wave 0 gap |
| ENGR-02 | Part .ly files include shared defs, apply correct \transpose per instrument | unit | `pytest tests/unit/test_part_generator.py -x` | No -- Wave 0 gap |
| ENGR-03 | Parts have \mark \default, \compressMMRests, bar number visibility | unit | `pytest tests/unit/test_part_generator.py::test_rehearsal_marks -x` | No -- Wave 0 gap |
| ENGR-04 | Dynamic restatement after 2+ bars rest | unit | `pytest tests/unit/test_dynamic_restatement.py -x` | No -- Wave 0 gap |
| ENGR-09 | ZIP contains all .ly source files | unit | `pytest tests/unit/test_packager.py::test_zip_contains_ly -x` | No -- Wave 0 gap |
| FNDN-06 | ZIP contains score PDF, 17 part PDFs, .ly files, .mid file | integration | `pytest tests/integration/test_packaging.py -x` | No -- Wave 0 gap |
| ENSM-01 | BigBandPreset encodes 17 instruments with correct transpositions, clefs, ordering | unit | `pytest tests/unit/test_ensemble.py -x` | No -- Wave 0 gap |
| ENSM-04 | Rhythm section parts (piano, guitar, bass) include ChordNames context | unit | `pytest tests/unit/test_part_generator.py::test_chord_symbols -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `uv run pytest tests/unit/ -x --timeout=30`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_ensemble.py` -- covers ENSM-01 (BigBandPreset data model)
- [ ] `tests/unit/test_score_generator.py` -- covers ENGR-01 (conductor score .ly generation)
- [ ] `tests/unit/test_part_generator.py` -- covers ENGR-02, ENGR-03, ENSM-04 (part .ly generation)
- [ ] `tests/unit/test_dynamic_restatement.py` -- covers ENGR-04 (dynamic restatement post-processing)
- [ ] `tests/unit/test_packager.py` -- covers FNDN-06, ENGR-09 (ZIP packaging)
- [ ] `tests/integration/test_packaging.py` -- covers FNDN-06 end-to-end (compilation + packaging)
- [ ] `tests/fixtures/sample_concert_pitch.ly` -- minimal concert-pitch LilyPond for test inputs
- [ ] Framework install: no additional installs needed (pytest, pytest-bdd, pytest-asyncio already in dev deps)

## Sources

### Primary (HIGH confidence)
- [LilyPond Notation Reference v2.24 - File Structure](https://lilypond.org/doc/v2.24/Documentation/notation/file-structure) - `\book`, `\include`, file organization
- [LilyPond Notation Reference v2.24 - Output File Names](https://lilypond.org/doc/v2.24/Documentation/notation/output-file-names) - `\bookOutputName`, `\bookOutputSuffix`
- [LilyPond Notation Reference v2.24 - Changing Multiple Pitches](https://lilypond.org/doc/v2.25/Documentation/notation/changing-multiple-pitches) - `\transpose` command syntax and semantics
- [LilyPond Notation Reference v2.24 - Displaying Chords](https://lilypond.org/doc/v2.24/Documentation/notation/displaying-chords) - `ChordNames` context, `\chordmode`
- [LilyPond Notation Reference v2.24 - Writing Parts](https://lilypond.org/doc/v2.24/Documentation/notation/writing-parts) - `\compressMMRests`, cue notes, instrument names
- [LilyPond Notation Reference v2.24 - Modifying Single Staves](https://lilypond.org/doc/v2.24/Documentation/notation/modifying-single-staves) - `\RemoveEmptyStaves`
- [LilyPond Notation Reference v2.24 - Setting the Staff Size](https://lilypond.org/doc/v2.24/Documentation/notation/setting-the-staff-size) - `set-global-staff-size`
- [LilyPond Learning Manual v2.24 - Scores and Parts](https://lilypond.org/doc/v2.24/Documentation/learning/scores-and-parts) - shared definitions + part extraction pattern
- [Python zipfile stdlib docs](https://docs.python.org/3/library/zipfile.html) - ZIP creation API

### Secondary (MEDIUM confidence)
- [LilyPond Changes v2.21](https://lilypond.org/doc/v2.21/Documentation/changes/index.html) - `\compressFullBarRests` rename confirmed
- [LilyPond GitLab Issue #4375](https://gitlab.com/lilypond/lilypond/-/issues/4375) - rename rationale
- [LilyPond News/Downloads](https://lilypond.org/download.html) - v2.24.4 as current stable (July 2024)
- [Big Band Score Layout - Evan Rogers](https://www.evanrogersmusic.com/blog-contents/big-band-arranging/score-layout) - Score order and bracketing conventions
- Project SCORING_GUIDE.md (`docs/SCORING_GUIDE.md`) - authoritative transposition table and engraving rules

### Tertiary (LOW confidence)
- Compilation parallelism safety: based on LilyPond being a stateless CLI tool with no shared mutable state; not explicitly documented. Validated by common practice in Mutopia Project build systems.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - LilyPond 2.24 is the project's existing dependency; all features verified against official v2.24 docs
- Architecture: HIGH - shared definitions + per-part files is the documented LilyPond best practice for ensemble scores; user decision locks this pattern
- Pitfalls: HIGH - command naming, transposition direction, and multi-bar rest interaction with rehearsal marks are well-documented gotchas with verified solutions
- Dynamic restatement: MEDIUM - the implementation strategy (Python text post-processing) is sound but specifics of LilyPond dynamic syntax parsing need validation during implementation

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days - LilyPond stable, no fast-moving changes expected)
