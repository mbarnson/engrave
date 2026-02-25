---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/research/STACK.md
  - .planning/research/ARCHITECTURE.md
  - .planning/REQUIREMENTS.md
  - .planning/PROJECT.md
autonomous: true
requirements: [AUDP-01]
must_haves:
  truths:
    - "STACK.md recommends audio-separator with per-stem model strategy instead of demucs-infer"
    - "ARCHITECTURE.md Stage 1 references audio-separator API instead of demucs.api.Separator"
    - "REQUIREMENTS.md AUDP-01 reflects best-available model strategy, not Demucs-only"
    - "PROJECT.md active requirements mention best-available model, not Demucs v4"
    - "demucs-infer is preserved in Alternatives Considered with rationale for when HTDemucs ft is still best"
  artifacts:
    - path: ".planning/research/STACK.md"
      provides: "Updated Source Separation (Stage 1) stack recommendation"
      contains: "audio-separator"
    - path: ".planning/research/ARCHITECTURE.md"
      provides: "Updated Stage 1 component description"
      contains: "audio-separator"
    - path: ".planning/REQUIREMENTS.md"
      provides: "Updated AUDP-01 requirement text"
      contains: "best-available model"
    - path: ".planning/PROJECT.md"
      provides: "Updated active requirements bullet"
      contains: "best-available model"
  key_links: []
---

<objective>
Update all planning documents to replace demucs-infer with audio-separator and per-stem SOTA model strategy (BS-RoFormer, Mel-Band RoFormer, HTDemucs ft, SCNet) for source separation.

Purpose: The stem-splitting field has advanced significantly. BS-RoFormer achieves ~12.9 dB SDR on vocals vs HTDemucs ft's ~9.0 dB. The `audio-separator` package wraps all SOTA models (BS-RoFormer, Mel-Band RoFormer, Demucs, MDX-NET, SCNet) under one API. Planning docs must reflect this to guide Phase 5 implementation correctly.

Output: Updated STACK.md, ARCHITECTURE.md, REQUIREMENTS.md, PROJECT.md
</objective>

<execution_context>
@/Users/patbarnson/.claude/get-shit-done/workflows/execute-plan.md
@/Users/patbarnson/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
@.planning/REQUIREMENTS.md
@.planning/PROJECT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update STACK.md source separation section and installation</name>
  <files>.planning/research/STACK.md</files>
  <action>
In STACK.md, make these specific changes:

1. **Source Separation (Stage 1) table** (line ~20-23): Replace the single `demucs-infer` row with a new `audio-separator` row:
   - Technology: `audio-separator`
   - Version: `latest`
   - Purpose: Audio source separation (multi-model)
   - Why Recommended: Wraps SOTA models (BS-RoFormer, Mel-Band RoFormer, Demucs HTDemucs, MDX-NET, SCNet) under one `pip install audio-separator` API. Enables per-stem model selection for optimal quality. PolUVR fork adds CoreML acceleration on Apple Silicon. Replaces `demucs-infer` which only supports HTDemucs (~9.0 dB SDR vocals) with access to BS-RoFormer (~12.9 dB SDR vocals).

2. **Model choice paragraph** (line ~25-26): Replace the `htdemucs_ft` paragraph with a per-stem strategy table:

   | Stem | Best Model | SDR | Why |
   |------|-----------|-----|-----|
   | Vocals | BS-RoFormer-Viperx-1297 | ~12.9 dB | Cleanest vocal isolation, won SDX23 |
   | Drums | Mel-Band RoFormer or HTDemucs ft | ~12.5 / ~9.0 dB | Mel-Band better for transients; HTDemucs ft solid fallback |
   | Bass | HTDemucs ft or SCNet XL | ~9.0 / ~10.7 dB | HTDemucs historically strongest on bass |
   | Other | Mel-Band RoFormer | ~12.5 dB | Better frequency separation via mel-scale subbands |

   Add note: "All models accessible via `audio-separator`. For offline pipeline (non-realtime), use highest-quality model per stem."

3. **Installation section** (line ~151): Change `uv add demucs-infer` to `uv add audio-separator`. Add comment: `# Wraps BS-RoFormer, Mel-Band RoFormer, Demucs, MDX-NET, SCNet`.

4. **Alternatives Considered table** (line ~203-206): Replace the `demucs-infer` vs `demucs (original)` row with:
   - Recommended: `audio-separator` | Alternative: `demucs-infer` | When: "If you only need HTDemucs and want a minimal dependency. demucs-infer is inference-only, lighter weight, but limited to HTDemucs family models (~9.0 dB SDR vocals)."
   - Keep the existing `demucs (original)` row as-is (still "Never" -- abandoned).

5. **What NOT to Use table** (line ~222): Change the `demucs (original PyPI package)` row's "Use Instead" column from `demucs-infer 4.1.2` to `audio-separator (or demucs-infer for HTDemucs-only)`.

6. **Stack Patterns by Variant** (line ~234-236): Change "Demucs" references to "audio-separator" in the audio input pipeline flow.

7. **Memory budget section** (line ~249): Update `Demucs (~4GB)` to `audio-separator/BS-RoFormer (~4-6GB)` in the M4 Max memory budget calculation.

8. **Version Compatibility** (line ~259): Replace `demucs-infer 4.1.2` row with `audio-separator latest` compatible with `PyTorch 2.x, Python 3.9+`.

9. **Scaling Considerations** (line ~589): Update "Demucs memory usage" references to "audio-separator model memory usage".

10. **Sources section**: Add source for audio-separator PyPI and BS-RoFormer SDX23 results. Remove or update demucs-infer source entry.
  </action>
  <verify>
    grep -c "audio-separator" .planning/research/STACK.md | test $(cat) -ge 5
    grep -c "BS-RoFormer" .planning/research/STACK.md | test $(cat) -ge 2
    grep -c "demucs-infer" .planning/research/STACK.md | test $(cat) -ge 1  # Should still appear in Alternatives
    grep "uv add audio-separator" .planning/research/STACK.md
  </verify>
  <done>STACK.md Source Separation section recommends audio-separator with per-stem model strategy; demucs-infer preserved in Alternatives Considered; installation commands updated; memory budgets and compatibility tables reflect new package</done>
</task>

<task type="auto">
  <name>Task 2: Update ARCHITECTURE.md, REQUIREMENTS.md, PROJECT.md, and MEMORY.md</name>
  <files>.planning/research/ARCHITECTURE.md, .planning/REQUIREMENTS.md, .planning/PROJECT.md</files>
  <action>
**ARCHITECTURE.md changes:**

1. **Component Responsibilities table** (line ~69, Stage 1 row): Change "Typical Implementation" from `Demucs v4 Hybrid Transformer via demucs.api.Separator` to `audio-separator with per-stem model routing (BS-RoFormer for vocals, Mel-Band RoFormer for drums/other, HTDemucs ft for bass)`.

2. **ASCII diagram** (lines ~31-33): Change `Demucs` label in Stage 1 box to `audio-sep` (keep it short to fit the box). Change `v4 (HT)` to `RoFormer+`.

3. **Data Flow - Stage 1 section** (line ~411-412): Update the Stage 1 description to reference audio-separator and note that different models may be used per stem target. Keep the output format the same (4 stem WAVs).

4. **Pattern 1 example code comment** in orchestrator (line ~211): If any reference to Demucs exists in code comments, update to audio-separator.

5. **Integration Points - External Services table** (line ~524): No Demucs-specific entry exists here (it's in-process), but check and update any Demucs references.

6. **Build Order - Tier 2 item 4** (line ~604): Change "Demucs integration" to "audio-separator integration".

7. **Anti-Pattern 1 note or Scaling section** (line ~589-590): Update any "Demucs" memory references to "audio-separator/RoFormer".

8. **Sources section**: Update/add source for audio-separator. Remove demucs-specific source if it's only about the API.

**REQUIREMENTS.md changes:**

1. **AUDP-01** (line ~22): Change from:
   `System performs source separation on audio input via Demucs v4, producing drums, bass, vocals, and other stems`
   To:
   `System performs source separation on audio input via best-available model per stem (BS-RoFormer for vocals, Mel-Band RoFormer for drums/other, HTDemucs ft for bass) using audio-separator, producing drums, bass, vocals, and other stems`

**PROJECT.md changes:**

1. **Active requirements bullet** (line ~22): Change "Source separation via Demucs v4 (drums, bass, vocals, other stems)" to "Source separation via best-available model per stem (BS-RoFormer, Mel-Band RoFormer, HTDemucs ft) using audio-separator package"

Also update MEMORY.md (user's project memory):
- In "Key Decisions" section, replace the `demucs-infer` reference: change `demucs htdemucs_ft: UPSTREAM ABANDONED, no replacement -- use demucs-infer fork` in Model Currency to note that audio-separator is now the recommended package wrapping all SOTA models including HTDemucs ft.
- Update the `demucs-infer` reference under "Model Currency" to reflect that audio-separator supersedes it.
  </action>
  <verify>
    grep "best-available model" .planning/REQUIREMENTS.md
    grep "audio-separator" .planning/research/ARCHITECTURE.md
    grep "audio-separator" .planning/PROJECT.md
    ! grep -q "via Demucs v4" .planning/REQUIREMENTS.md  # Old text should be gone
    ! grep -q "Source separation via Demucs v4" .planning/PROJECT.md  # Old text should be gone
  </verify>
  <done>ARCHITECTURE.md Stage 1 references audio-separator API pattern; REQUIREMENTS.md AUDP-01 broadened to best-available model strategy; PROJECT.md active requirements updated; no remaining "via Demucs v4" references in requirements or project docs</done>
</task>

</tasks>

<verification>
After both tasks complete:
1. `grep -r "demucs-infer" .planning/` should only appear in Alternatives Considered contexts, not as primary recommendation
2. `grep -r "audio-separator" .planning/` should appear in STACK.md (primary), ARCHITECTURE.md (Stage 1), PROJECT.md (active requirements)
3. `grep "AUDP-01" .planning/REQUIREMENTS.md` should reference best-available model, not Demucs v4
4. No broken markdown formatting (tables, code blocks) in any modified file
</verification>

<success_criteria>
- All four planning docs updated to reflect audio-separator as the primary source separation package
- Per-stem model strategy documented in STACK.md with SDR numbers
- demucs-infer preserved as alternative (not deleted) with clear "when to use" guidance
- AUDP-01 requirement broadened from Demucs-specific to best-available-model
- Stage 1 architecture description uses audio-separator API pattern
- No remaining references to "Demucs v4" as the primary/only separation approach (Demucs/HTDemucs ft preserved as one model option among several)
</success_criteria>

<output>
After completion, create `.planning/quick/1-update-planning-docs-to-replace-demucs-w/1-SUMMARY.md`
</output>
