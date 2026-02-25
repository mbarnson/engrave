# Engrave UAT Test Plan

**Date:** _______________
**Tester:** Sam (or: _______________)
**Purpose:** Evaluate the musical quality of Engrave output on real-world inputs.

This is not a bug-hunting exercise. The smoke test harness has already verified that nothing crashes or produces garbage. Your job is musical judgment: Can you hand these parts to your musicians for rehearsal?

---

## Prerequisites

Before starting, confirm these are working:

- [ ] Engrave installed and `engrave --version` prints a version number
- [ ] LilyPond installed (`lilypond --version`)
- [ ] LLM provider configured (`engrave check all` passes)
- [ ] PDF viewer available (Preview on macOS works fine)
- [ ] Optional: MuseScore or Dorico for MusicXML import testing

---

## Section 1: Smoke Test Pre-Validation

Run the automated smoke test first. This catches structural problems so you don't have to.

- [ ] Run: `engrave smoke-test ./test-fixtures/`
- [ ] Expected: All checks show green checkmarks in the terminal
- [ ] If any check fails: Stop and send the output to Pat before continuing
- [ ] If MusicXML checks show SKIPPED: That is normal (JSON fan-out is optional)

**Notes:** ___

---

## Section 2: MIDI-Only Pipeline (Fast Path)

For each test MIDI file in `test-fixtures/`, run the pipeline and evaluate the output.

### Steps per MIDI file

**File name:** _______________

- [ ] Run: `engrave generate <file.mid> --output output/`
- [ ] Run: `engrave render output/`

#### Conductor Score

- [ ] Open the conductor score PDF
  - Can you read the score at conductor desk distance? (yes / no)
  - Are instruments in standard big band order? (saxes, trumpets, trombones, rhythm)
  - Are system brackets and braces correct?
  - Notes: ___

#### Trumpet 1 Part

- [ ] Open the trumpet 1 part PDF
  - Can you sight-read this part? (yes / no)
  - Are dynamics visible and correctly placed?
  - Are rehearsal marks at logical places?
  - Are multi-bar rests consolidated correctly?
  - Does it feel like standard trumpet notation? (clef, key, range)
  - Notes: ___

#### Alto Sax 1 Part

- [ ] Open the alto sax 1 part PDF
  - Is it transposed to Eb correctly? (compare a phrase against the concert pitch score)
  - Can you sight-read this part? (yes / no)
  - Notes: ___

#### Trombone 1 Part

- [ ] Open the trombone 1 part PDF
  - Bass clef? (yes / no)
  - Reading key correct (concert pitch)? (yes / no)
  - Notes: ___

#### Piano Part

- [ ] Open the piano part PDF
  - Grand staff? (yes / no)
  - Chord symbols above? (yes / no)
  - Notes: ___

#### MusicXML Import (if Dorico or MuseScore available)

- [ ] Import the .musicxml file into Dorico or MuseScore
  - Does it import without errors? (yes / no)
  - Do the parts match the PDFs? (yes / no)
  - Notes: ___

---

## Section 3: Audio Pipeline (Full Path)

For each test audio file, run the full pipeline through the web UI.

### Steps per audio file

**File name:** _______________

- [ ] Start the web UI: `engrave serve` (or ask Pat to start it for you)
- [ ] Open the browser to the URL shown in the terminal
- [ ] Upload the audio file
- [ ] Add any hints you think are helpful (tempo, key, instrumentation)
- [ ] Click "Engrave" and wait for it to finish (may take several minutes)
- [ ] Download the ZIP file

Now repeat the Section 2 checks on the output, plus these audio-specific checks:

- [ ] Does the generated music resemble the source recording?
  - Right instruments detected? (yes / no / partially)
  - Tempo approximately correct? (yes / no)
  - Notes: ___

---

## Section 4: Web UI Usability

Think about the experience of using the web interface.

- [ ] Could you figure out how to use the web UI without instructions? (yes / no)
- [ ] Was the upload process clear? (yes / no)
- [ ] Was the "Processing..." wait tolerable? (note how long it took: ___ minutes)
- [ ] Was the download link obvious when complete? (yes / no)
- [ ] If an error occurred, was the message understandable? (yes / no / N/A)
- [ ] Notes: ___

---

## Section 5: Overall Assessment

Step back and think about the big picture.

- [ ] Would you hand these parts to your musicians for rehearsal?
  - Yes, as-is
  - Yes, with minor edits (describe below)
  - No (describe why below)

- [ ] What is the single biggest issue that would prevent rehearsal use?

  ___

- [ ] What surprised you positively?

  ___

- [ ] Any other notes:

  ___

---

Submit this checklist with your notes to Pat. Scribble freely -- this is not a QA form, it is a conversation starter. Anything you notice is valuable.
