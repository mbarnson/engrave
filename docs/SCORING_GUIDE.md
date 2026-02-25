# Scoring Guide for Engrave

## Who This Is For

This document is written for a conductor with a choral background who needs to make
intelligent scoring decisions for jazz ensemble (primarily big band) output. It maps
directly to the requirements in REQUIREMENTS.md — especially ENSM-01 through ENSM-05
and ENGR-01 through ENGR-10 — and draws heavily on Tim Davies' deBreved orchestration
philosophy.

The core question this document answers: **when the LLM generates notation, what rules
should govern every decision?**

---

## Part 1: The Mindset Shift — Choral to Ensemble

Coming from choir, you're used to:
- Four staves (SATB), all in concert pitch, all in treble or bass clef
- Text underlay driving phrasing
- Dynamics that apply uniformly across the section
- A conductor who shapes everything in real time

Jazz ensemble notation works differently in almost every dimension:

| Concept | Choral | Big Band |
|---|---|---|
| Pitch on the page | Concert pitch throughout | Each player reads in their transposed key |
| Clefs | Treble + bass | Treble for most winds; bass for trombone/bass |
| Phrasing driver | Lyrics | Articulation markings + style convention |
| Dynamics | Marked constantly | Marked at entrances; restated after rests |
| Rests | Usually short | Often long — require cues and rehearsal marks |
| "Section" | All voices blend freely | Brass/sax/rhythm are distinct sections with internal hierarchy |
| Conductor role | Shapes everything | In studio: keeps time and cues; players do the rest |

The single most important idea from Tim Davies for this project:

> **The orchestra/band is not waiting for you to tell them everything. They have defaults.
> Your job is to mark departures from those defaults — not to annotate the obvious.**

This is the opposite of how many beginning arrangers (and naive AI systems) write. The
failure mode is *over-notation*: marking every articulation, adding dynamics on every
bar, writing "swing" at the top and then marking every eighth note with a tenuto. This
clutter insults the players, slows sight-reading, and sounds mechanical.

---

## Part 2: The Big Band Ensemble (ENSM-01)

### Standard Instrumentation

The Engrave big band preset encodes:

```
Woodwinds:   Alto Sax 1, Alto Sax 2, Tenor Sax 1, Tenor Sax 2, Baritone Sax
Brass:       Trumpet 1, Trumpet 2, Trumpet 3, Trumpet 4
             Trombone 1, Trombone 2, Trombone 3, Bass Trombone
Rhythm:      Piano, Guitar, Bass, Drums
```

### Transpositions

Every wind player reads in a *different* key from concert pitch. The system stores all
music internally in concert pitch (LILY-03) and applies transposition at render time.

| Instrument | Transposition | Example: C concert sounds as... |
|---|---|---|
| Alto Sax 1 & 2 | Eb instrument | Written D (up M6) |
| Tenor Sax 1 & 2 | Bb instrument | Written D (up M2) |
| Baritone Sax | Eb instrument (octave lower) | Written D (up M6 + 8va) |
| Trumpet 1–4 | Bb instrument | Written D (up M2) |
| Trombone 1–3 | C instrument (tenor clef or bass) | Concert pitch, bass clef |
| Bass Trombone | C instrument | Concert pitch, bass clef |
| Piano, Guitar | C instrument | Concert pitch |
| Bass | C instrument (sounds 8vb) | Concert pitch, bass clef |
| Drums | Non-pitched | Percussion clef |

**Key signatures in parts:** Transposed correctly. If the concert key is Bb major,
alto sax parts are in G major (two sharps added), trumpets are in C major. The system
handles this deterministically from the transposition table.

### Score Order (Conductor Score)

Top to bottom, always in this order:

```
Alto Sax 1
Alto Sax 2
Tenor Sax 1
Tenor Sax 2
Baritone Sax
─────────────────  (bracket: Saxophones)
Trumpet 1
Trumpet 2
Trumpet 3
Trumpet 4
─────────────────  (bracket: Trumpets)
Trombone 1
Trombone 2
Trombone 3
Bass Trombone
─────────────────  (bracket: Trombones)
Piano
Guitar
Bass
Drums
─────────────────  (brace: Rhythm Section)
```

Conductor score is in **concert pitch**. Parts are transposed. This is standard
practice and is non-negotiable — do not generate transposed conductor scores.

---

## Part 3: Tim Davies Articulation Defaults (ENSM-03)

This is the most important section for code generation quality.

### The Jazz Default

Jazz ensemble parts operate with an **assumed default** that experienced players know
without being told. The system should only mark *departures from this default*.

**Swing feel:**
- Assumed unless the part is marked "Straight 8s," "Latin," "Rock," or similar
- Eighth notes in swing are played long-short (triplet subdivision), with the first note
  slightly longer — players know this; do not write triplets to explain it
- Do not write the "swing" eighth note notation (dotted eighth + sixteenth) — this is
  archaic and considered incorrect in modern jazz parts

**Note length defaults (unmarked notes):**
- **Unmarked quarter note** → played **short** (approximately 50% of its written value)
- **Unmarked eighth note in swing** → played **long** (approximately 75–85% of value,
  the "long" side of the swing pair)
- **Unmarked eighth note in straight/rock/Latin** → played **long** (~75%)

This seems counterintuitive from a choral perspective (where unmarked notes are full
value), but it reflects the articulation culture of jazz ensemble playing.

**Staccato:** Means "shorter than short" — used for accent effects, not just short
notes. In jazz, staccato on a quarter note shortens it further than the already-short
default.

**Never pair staccato + accent.** They are redundant in jazz context and mark a
beginner chart. If you want short + attacked, accent alone does it (accent implies
short). Staccato + accent together looks wrong to any professional reader.

**Accent (>):** "Hit this note harder than the context suggests." Implies the note is
also relatively short.

**Tenuto (—):** "Play this note full value and connected" — the opposite of the default
short quarter. Use this when you want a quarter note held out.

**Sforzando (sfz, sf):** Explosive accent, immediately followed by the ambient dynamic.

### Section Consistency Rule (ENSM-05)

> If every instrument in a section has the same articulation at a given passage, **omit
> the marking.** The section default handles it.

Only mark the exceptions. For example:

- All four trumpets are playing marked quarter notes. The default is short. Do not
  write staccato on all four — it's redundant noise.
- Trumpet 1 is playing a sustained melody line while Trumpets 2–4 comp underneath.
  The melody needs tenuto markings; the comp figures do not need staccato (it's the
  default).

This principle extends to dynamics:
- If the whole brass section is fortissimo, mark *ff* at the entrance.
- Do not repeat *ff* every four bars unless there was a dynamic change in between.

### Dynamic Restatement After Rests (ENGR-04)

This is where big band differs from choral: players cannot see adjacent staves in their
part. After any multi-bar rest (even 2–4 bars), the dynamic level must be restated at
the new entrance. The player has been waiting — they've lost context.

Rule: **Always restate the dynamic at any entrance that follows 2+ bars of rest.**

---

## Part 4: Rehearsal Infrastructure (ENGR-03)

Choir singers use letter rehearsal marks (A, B, C...) or measure numbers. Big band
uses both, but the conventions differ.

### Rehearsal Marks

- Place a rehearsal mark at the **start of every major structural section**: intro,
  verse, chorus, bridge, shout chorus, soli, coda, tag.
- Also place marks **every 8–16 bars** within long sections without natural landmarks.
- Use letters (A, B, C...) for structural landmarks; measure numbers are always shown
  at the start of each line.

### Measure Numbers

- Display at the **beginning of every system** (every line of music) in parts.
- In the conductor score, show at every system and optionally at every bar.

### Multi-Bar Rests

- Consolidate consecutive empty bars into a single multi-bar rest with the count shown
  above: `𝄦 12` (or LilyPond equivalent).
- Never leave individual empty bars in a part — a player counting 16 individual empty
  measures is miserable and will lose their place.
- Maximum multi-bar rest before a cue note is required: **8 bars** (ENGR-06).

### Cue Notes (ENGR-06)

After 8 or more bars of rest, the player needs a landmark to know where they are.
Provide a cue: small-sized notes showing a prominent, audible melody or figure from
another instrument, labeled with the source instrument name ("Tpt. 1", "Piano", etc.).

Cue notes are written in the player's **transposed key** (not concert pitch), in small
noteheads, and do not affect page formatting.

---

## Part 5: Page Layout & Part Formatting

### Part Orientation

- **Conductor score:** Landscape (11" × 8.5" or A3), to fit all staves per system
- **Individual parts:** Portrait (8.5" × 11" or A4), one instrument per page

### Page Turns (ENGR-10)

Never place a page turn mid-phrase. This is critical: a player cannot turn the page
while playing. The rule:

> **Page turns must occur only at rests of 2+ bars, or at the end of a logical phrase.**

If the music does not provide a natural rest, insert a measure of rest labeled "V.S."
(volti subito — turn quickly) with a warning, or restructure the layout to avoid the
conflict. In LilyPond this is managed via `\pageBreak` and system break placement.

### Chord Symbols on Rhythm Section Parts (ENSM-04)

Piano, guitar, and bass parts display chord symbols above the staff. These are not
suggestions — they define the harmonic language the rhythm section is expected to
realize. Format:

- Root + quality (C, Cm, C7, Cmaj7, Cm7, C7#11, etc.)
- Placed above the staff, at the beat where the chord changes
- Use standard jazz chord symbol conventions (not classical Roman numeral analysis)

---

## Part 6: Style-Specific Beaming (ENGR-05)

Beaming is not just a readability choice — it communicates rhythmic feel.

### Swing Beaming

In swing feel, beam eighth notes in pairs or groups that emphasize the *long-short*
swing subdivision. Generally:

- Beam two consecutive eighths together
- Do not beam across the middle of a 4/4 bar at the beat 3 boundary
- The visual grouping should reflect how a player phrases, not just fill the bar

### Latin / Rock / Straight 8s Beaming

In non-swing contexts, beam in groups of 4 eighths (filling each half of a 4/4 bar).
This tells the player "straight time, no swing." The beaming itself communicates the
feel change.

### Do Not Over-Beam

Do not beam a quarter + eighth as if they were tied — each note gets its own stem.
And do not beam across rests.

---

## Part 7: Notation Traps to Avoid

These are the most common mistakes an AI system (or beginning arranger) makes, drawn
directly from deBreved's "Over-Notation Nation" principle.

**Do not:**
- Mark every eighth note with a tenuto to mean "play these long" — it's the default
- Write "swing" text and then also notate dotted-eighth + sixteenth rhythms
- Pair staccato with an accent (redundant)
- Repeat dynamic markings every few bars without a dynamic change
- Leave individual empty bars where a multi-bar rest should be
- Mark the same articulation on every instrument in a section simultaneously (use the
  section default instead)
- Add courtesy accidentals excessively — once per bar is usually enough
- Cram too many notes per system — give the music room to breathe
- Write tempo = 120 when the feel is more meaningfully described as "Medium Swing ♩= 120"

**Do:**
- Trust the players to know the jazz defaults
- Mark only what departs from the default
- Restate dynamics after rests
- Include cue notes after long rests
- Use tempo + style text (not just a metronome number)
- Add a brief style description at the top of each section when the feel changes

---

## Part 8: Connecting to the Codebase

The scoring decisions in this document map to specific system requirements:

| This document | Requirement |
|---|---|
| Transposition table | ENSM-01, LILY-03 |
| Score order / bracketing | ENGR-01 |
| Transposed parts with clef/key | ENGR-02 |
| Rehearsal marks, measure numbers, multi-bar rests | ENGR-03 |
| Dynamic restatement after rests | ENGR-04 |
| Style-aware beaming | ENGR-05 |
| Cue notes after 8+ bars rest | ENGR-06 |
| Page turns at rests only | ENGR-10 |
| Tim Davies articulation defaults | ENSM-03 |
| Chord symbols on rhythm section | ENSM-04 |
| Section consistency rule | ENSM-05 |
| Joint section generation | ENSM-02 |

When writing LilyPond generation prompts (Phase 3, 7), reference the specific rules
here by name so the LLM has explicit grounding for its decisions. For example:

```
"Apply Tim Davies articulation defaults: unmarked quarter notes are short,
unmarked eighth notes are long. Mark only departures from the section
collective default (ENSM-05). Restate dynamics after any rest of 2+ bars (ENGR-04)."
```

---

## Key Resources

- **Tim Davies deBreved blog:** https://www.timusic.net/debreved/ — Start with
  Introduction, The Orchestral Default, Over-Notation Nation, A Neglected Relationship.
  The "How to Score" and "Jazz Notation – The Default" posts are directly applicable.
- **Extreme Australian Orchestration (screencast):** https://www.timusic.net/debreved/extreme-australian-orchestration/
  — Full workflow walkthrough from MIDI to studio-ready score
- **LilyPond Notation Reference:** https://lilypond.org/doc/v2.24/Documentation/notation/
  — The definitive reference for LilyPond syntax; use for specific markup questions
- **Scoring Notes:** https://www.scoringnotes.com — Engraving best practices and
  notation software tutorials
- **Mutopia Project:** https://www.mutopiaproject.org — Source for open-licensed
  LilyPond scores (corpus for Phase 2)

---

*Last updated: 2026-02-24*
*Author: Claude (based on project requirements and Tim Davies deBreved methodology)*
