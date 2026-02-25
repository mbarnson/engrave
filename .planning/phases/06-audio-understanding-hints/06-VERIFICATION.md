---
phase: 06-audio-understanding-hints
verified: 2026-02-24T19:55:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 6: Audio Understanding & Hints Verification Report

**Phase Goal:** The system understands musical character beyond pitch and rhythm, and the user can guide generation with natural language descriptions

**Verified:** 2026-02-24T19:55:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Audio LM produces structured descriptions capturing key, tempo, style, dynamics, articulation intent, and structural form | ✓ VERIFIED | AudioDescription Pydantic model with all fields present; GeminiDescriber sends to Gemini 3 Flash with schema-enforced JSON; 55 tests passing |
| 2 | User can type natural language hints and the system encodes them as structural metadata for generation | ✓ VERIFIED | load_hints() auto-detects inline vs file; --hints CLI flag; hints flow to DEFINITIVE section of three-tier prompt |
| 3 | User hints are treated as authoritative when they conflict with audio inference | ✓ VERIFIED | Three-tier prompt structure with DEFINITIVE (user hints) before CONTEXTUAL (audio); authority labels explicit in prompt text |
| 4 | Generated LilyPond output reflects audio understanding (tempo markings, style indications, dynamic contours) | ✓ VERIFIED | render_full_description() converts AudioDescription to natural language; flows to CONTEXTUAL section; prompt contains tempo/style/dynamics from audio |
| 5 | Pure MIDI input (no audio, no hints) works with the three-tier template | ✓ VERIFIED | Backward compatibility maintained; empty sections show placeholders "No user hints provided." and "No audio analysis available." |
| 6 | Audit log records per-field source resolution as structured JSON | ✓ VERIFIED | AuditLog, AuditEntry, FieldResolution dataclasses; write() produces valid JSON; 5 audit tests passing |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| src/engrave/audio/description.py | AudioDescription and SectionDescription Pydantic models | ✓ VERIFIED | 81 lines, both classes present with all user-decided fields, no confidence scores |
| src/engrave/audio/describer.py | Describer protocol, GeminiDescriber, create_describer factory | ✓ VERIFIED | 234 lines, Protocol with async describe(), GeminiDescriber with litellm.acompletion, retry/fallback logic |
| src/engrave/audio/templates.py | Natural language template rendering | ✓ VERIFIED | 100 lines, render_track_summary(), render_section_description(), render_full_description() |
| src/engrave/hints/loader.py | Hint loading with inline text vs file path auto-detection | ✓ VERIFIED | 42 lines, load_hints() with Path.is_file() check |
| src/engrave/generation/audit.py | Audit log with FieldResolution, AuditEntry, AuditLog | ✓ VERIFIED | 110 lines, dataclasses with JSON write(), per-field source tracking |
| src/engrave/generation/prompts.py | Three-tier prompt builder with audio_description and user_hints parameters | ✓ VERIFIED | build_section_prompt() signature extended, DEFINITIVE/CONTEXTUAL/RAW INPUT sections present |
| src/engrave/generation/pipeline.py | Pipeline integration with audio description and user hints | ✓ VERIFIED | generate_section() and generate_from_midi() accept audio_description and user_hints; render_section_description() imported and used |
| src/engrave/cli.py | CLI --hints flag on generate command | ✓ VERIFIED | --hints option present, load_hints() called, user_hints passed to generate_from_midi() |
| tests/unit/test_audio_description.py | Tests for AudioDescription schema | ✓ VERIFIED | 8 tests passing |
| tests/unit/test_describer.py | Tests for Describer protocol and GeminiDescriber | ✓ VERIFIED | 8 tests passing (mocked) |
| tests/unit/test_audio_templates.py | Tests for NL template rendering | ✓ VERIFIED | 9 tests passing |
| tests/unit/test_hint_loader.py | Tests for hint loading | ✓ VERIFIED | 6 tests passing |
| tests/unit/test_audit.py | Tests for audit log | ✓ VERIFIED | 5 tests passing |
| tests/unit/test_prompt_budget.py | Extended tests for three-tier prompt | ✓ VERIFIED | 7 new three-tier tests added, all passing |
| tests/integration/test_audio_generation.py | Integration tests for description + hints in pipeline | ✓ VERIFIED | 3 integration tests passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| src/engrave/audio/describer.py | src/engrave/audio/description.py | GeminiDescriber returns AudioDescription | ✓ WIRED | AudioDescription.model_validate_json() called at line 107 |
| src/engrave/audio/templates.py | src/engrave/audio/description.py | render functions accept SectionDescription/AudioDescription | ✓ WIRED | Type hints present, imports verified |
| src/engrave/audio/describer.py | litellm | litellm.acompletion for Gemini API calls | ✓ WIRED | litellm.acompletion called at line 92 with schema-enforced JSON |
| src/engrave/config/settings.py | src/engrave/audio/describer.py | DescriberConfig consumed by create_describer factory | ✓ WIRED | DescriberConfig class present, nested under AudioConfig |
| src/engrave/cli.py | src/engrave/hints/loader.py | CLI loads hints via load_hints() | ✓ WIRED | load_hints imported at line 330, called at line 339 |
| src/engrave/generation/prompts.py | generation pipeline | build_section_prompt accepts audio_description and user_hints | ✓ WIRED | Signature at line 142 includes both parameters |
| src/engrave/generation/pipeline.py | src/engrave/generation/audit.py | Pipeline writes audit log after generation | ✓ WIRED | AuditLog imported at line 24, used in pipeline |
| src/engrave/generation/pipeline.py | src/engrave/audio/templates.py | Pipeline renders audio description to NL text | ✓ WIRED | render_section_description imported at line 509, called at line 523 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AUDP-03 | 06-01-PLAN.md | System produces structured musical descriptions from audio via audio LM (Qwen3-Omni-30B-A3B-Instruct locally, Gemini 3 Flash for long-form), capturing key, tempo, style, dynamics, articulation intent, and structural form | ✓ SATISFIED | AudioDescription model with all fields; GeminiDescriber with schema-enforced JSON; create_describer factory supports pluggable backends |
| AUDP-04 | 06-02-PLAN.md | User can provide natural language hints describing ensemble composition, style, structural markers, and articulation intent -- hints are treated as authoritative when conflicting with audio inference | ✓ SATISFIED | load_hints() with auto-detection; --hints CLI flag; three-tier prompt with DEFINITIVE section labeled "always authoritative" |

No orphaned requirements found. All requirements mapped in REQUIREMENTS.md to Phase 6 are covered by plans.

### Anti-Patterns Found

No anti-patterns detected. All files are substantive implementations with no TODO/FIXME/placeholder comments, no stub implementations, and complete wiring.

### Human Verification Required

None required for goal verification. All observable truths can be programmatically verified.

Optional smoke test for end-to-end flow:
1. Run `engrave generate --audio test.mp3 --hints "swing feel, shout chorus at bar 33"` on a real recording
2. Verify audit_log.json contains per-field source resolution entries
3. Verify generated LilyPond contains tempo/style markings from audio analysis

---

## Summary

Phase 6 goal **ACHIEVED**. The system understands musical character beyond pitch and rhythm through:

1. **Structured audio descriptions** via AudioDescription Pydantic model with schema-enforced JSON output to Gemini 3 Flash
2. **Natural language hints** via load_hints() with CLI integration
3. **Three-tier prompt authority** (DEFINITIVE > CONTEXTUAL > RAW INPUT) making user hints authoritative
4. **Natural language rendering** of audio descriptions for CONTEXTUAL prompt injection
5. **Audit log infrastructure** for per-field source resolution tracking
6. **Backward compatibility** maintained — pure MIDI path works with three-tier template

All must-haves verified. All requirements satisfied. 55 tests passing (8 audio description + 8 describer + 9 templates + 6 hint loader + 5 audit + 16 prompt budget + 3 integration). No gaps, no stubs, no anti-patterns.

Ready to proceed to Phase 7 (Convergent Sight-Reading).

---

_Verified: 2026-02-24T19:55:00Z_
_Verifier: Claude (gsd-verifier)_
