# Phase 6: Audio Understanding & Hints - Research

**Researched:** 2026-02-24
**Domain:** Audio LM integration for structured musical description + natural language hint system
**Confidence:** MEDIUM-HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Two-tier audio description schema:** track-level metadata + per-section annotations
- **Track-level fields:** tempo (BPM, variable flag), time signature, key (root + mode), instrument presence list, style tags, overall energy arc
- **Per-section fields:** label, start/end time, key (if changes), active instruments list, texture descriptor, dynamics, notes (nullable free text)
- **No confidence scores.** Audio LM outputs treated as suggestions -- disagreement itself is the signal
- **Section boundaries come from MIDI** (Phase 3's `midi/sections.py`), NOT from audio LM timestamps. Audio LM receives bar-based section boundaries and labels each one
- **Per-section `notes` field** separate from `texture`. Texture = musical texture. Notes = catch-all for stray observations. Nullable
- **Model-dependent dual path:** local Qwen3-Omni-Instruct produces JSON via structured prompting with Pydantic validation on output. Cloud Gemini 3 Flash uses schema-enforced JSON via `response_mime_type="application/json"` + `response_schema`
- **Describer protocol** abstracts the model difference, same pattern as Transcriber in Phase 5
- **Audio LM purpose:** structure and context, NOT note accuracy
- **Free text hints, no DSL.** LLM is the parser. No structured markers, no regex extraction for v1
- **CLI input:** `--hints` flag accepts inline text or file path (auto-detect). File path supports batch runs
- **Web UI input:** textarea ("Tell us anything about this recording that would help")
- **No hint routing to sections.** Full hint block goes into every section's generation prompt
- **No echo/confirmation.** Hints flow silently into prompt. Interpretation logged for audit only
- **Fresh each run.** No application-level hint persistence. `.hints` sidecar file is user's persistence mechanism
- **Three-tier priority, hardcoded:** (1) User hints = DEFINITIVE, (2) Audio description = CONTEXTUAL, (3) MIDI transcription = RAW INPUT
- **Implementation is prompt construction, not a merge algorithm.** Generation prompt labels each source with authority level
- **Self-contradictory hints pass through verbatim.** Generation LLM has section context to interpret
- **Audit log:** structured JSON, per-field override tracking. Fields: {field, midi_value, audio_value, hint_value, resolved_to, source}
- **Audio description injected as natural language summary**, not raw JSON. Template converts structured fields to readable sentences
- **Same three-tier template always**, even for pure MIDI input (CONTEXTUAL section empty/absent)
- **Prompt structure per section:** compact global header + per-section audio description summary + user hints (full block) + current section MIDI data + coherence state

### Claude's Discretion
- Exact Pydantic model field types and validation rules for AudioDescription
- Natural language template wording for prompt injection
- Describer protocol API design details
- Audit log storage format (file per run, append log, etc.)
- How to handle audio LM errors/timeouts (retry vs skip with warning)

### Deferred Ideas (OUT OF SCOPE)
- STACK.md update: GPT-4/4o references -> GPT-5.2 Thinking/Pro
- Per-note override tracking in audit log -- Phase 9
- Human-readable conflict reports rendered from JSON -- Phase 10
- Hint echo/interpretation confirmation -- explicitly rejected for v1
- Hint routing to specific sections via LLM pre-pass -- rejected for v1
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDP-03 | System produces structured musical descriptions from audio via audio LM (Qwen3-Omni-30B-A3B-Captioner for local inference, Gemini 3 Flash for cloud/long-form), capturing key, tempo, style, dynamics, articulation intent, and structural form | Describer protocol pattern (mirrors Transcriber), Pydantic AudioDescription schema, dual-path LLM integration via LiteLLM (Gemini) and mlx-vlm (local), natural language template rendering |
| AUDP-04 | User can provide natural language hints describing ensemble composition, style, structural markers, and articulation intent -- hints are treated as authoritative when conflicting with audio inference | Three-tier prompt template with authority labels, CLI --hints flag with path/inline auto-detection, audit log with per-field override tracking, generation pipeline integration |
</phase_requirements>

## Summary

Phase 6 introduces Stage 3 of the pipeline: audio understanding via audio LMs, plus a user hint ingestion system. The phase builds two independent but convergent subsystems: (1) a `Describer` protocol with dual backends (local Qwen3-Omni via mlx-vlm or vllm-mlx, cloud Gemini 3 Flash via LiteLLM) that produces structured `AudioDescription` objects from audio files, and (2) a hint system that accepts free-text user input via CLI `--hints` flag and injects it into the generation prompt as authoritative context. Both feed into a restructured three-tier generation prompt that labels sources by authority (DEFINITIVE/CONTEXTUAL/RAW INPUT).

The core technical work is: defining the AudioDescription Pydantic schema, implementing the Describer protocol with two backends, building the natural language template that converts structured descriptions into prompt-ready text, restructuring the existing `build_section_prompt` to accept the three-tier format, implementing hint ingestion (CLI + file path detection), and building the audit log that tracks per-field source resolution.

The local audio LM path (Qwen3-Omni) is the least mature component. As of February 2026, mlx-vlm supports omni models with audio input, but Qwen3-Omni support is actively being added and may require the mlx-vlm generate API with audio parameters. The Gemini 3 Flash path is straightforward: LiteLLM supports base64 audio content and response_schema for structured JSON output. The Describer protocol abstracts this difference behind a common interface.

**Primary recommendation:** Build the Describer protocol with the Gemini 3 Flash backend first (well-supported, documented API), then add the local Qwen3-Omni backend. The hint system and three-tier prompt restructuring are independent of the audio LM choice and can proceed in parallel.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.0 | AudioDescription schema, validation | Already used project-wide for BaseModel/BaseSettings |
| litellm | latest | Gemini 3 Flash audio LM calls with structured output | Already integrated as InferenceRouter backend |
| mlx-vlm | latest | Local Qwen3-Omni inference with audio input on Apple Silicon | Supports omni models (VLMs with audio), native MLX backend |
| google-genai | latest | Direct Gemini API for `response_mime_type` + `response_schema` (if LiteLLM structured output insufficient) | Official Google Python SDK, supports Pydantic schema |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typer | existing | CLI `--hints` flag extension | Already the CLI framework |
| rich | existing | Audit log display in verbose mode | Already used for CLI output |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mlx-vlm for local Qwen3-Omni | vllm-mlx OpenAI-compatible server | vllm-mlx provides a persistent server endpoint (good for development), but adds operational complexity of managing a separate process. mlx-vlm is simpler for one-shot inference. Recommend mlx-vlm for batch, vllm-mlx if a persistent server is preferred |
| LiteLLM for Gemini | google-genai SDK directly | LiteLLM already handles Gemini well for text. For audio+structured output, LiteLLM's `response_format` with `json_schema` + base64 audio content works. Direct google-genai SDK is a fallback if LiteLLM's handling of audio+schema has edge cases |
| Pydantic validation on output | Manual JSON parsing | Pydantic provides type safety, default values for missing fields, and clear error messages. No reason to hand-roll |

**Installation:**
```bash
uv add mlx-vlm google-genai
```
Note: `litellm`, `pydantic`, `pydantic-settings`, `typer`, `rich` are already in `pyproject.toml` dependencies.

## Architecture Patterns

### Recommended Project Structure
```
src/engrave/
├── audio/
│   ├── describer.py       # Describer protocol + GeminiDescriber + QwenDescriber
│   ├── description.py     # AudioDescription, SectionDescription Pydantic models
│   └── templates.py       # Natural language template rendering
├── hints/
│   ├── __init__.py        # Public API: load_hints()
│   └── loader.py          # CLI hint loading (inline text vs file path)
├── generation/
│   ├── prompts.py         # MODIFIED: three-tier prompt builder
│   ├── audit.py           # NEW: audit log for per-field resolution tracking
│   └── pipeline.py        # MODIFIED: integrate description + hints into pipeline
├── config/
│   └── settings.py        # MODIFIED: add DescriberConfig
└── cli.py                 # MODIFIED: add --hints flag to generate command
```

### Pattern 1: Describer Protocol (mirrors Transcriber)
**What:** A `Protocol` class defining the `describe(wav_path, sections) -> AudioDescription` contract, with concrete implementations for each backend.
**When to use:** Always -- this is the core abstraction for Phase 6.
**Example:**
```python
# src/engrave/audio/describer.py
from typing import Protocol, runtime_checkable
from pathlib import Path
from engrave.audio.description import AudioDescription
from engrave.midi.sections import SectionBoundary

@runtime_checkable
class Describer(Protocol):
    """Audio-in, AudioDescription-out contract."""

    async def describe(
        self,
        audio_path: Path,
        sections: list[SectionBoundary],
        tempo_bpm: int,
        ticks_per_beat: int,
    ) -> AudioDescription:
        """Produce a structured musical description from audio.

        Args:
            audio_path: Path to WAV file (full mix or individual stem).
            sections: Section boundaries from MIDI analysis.
            tempo_bpm: Tempo from MIDI analysis for bar-to-time conversion.
            ticks_per_beat: MIDI resolution for bar-to-time conversion.

        Returns:
            AudioDescription with track-level and per-section annotations.
        """
        ...
```

### Pattern 2: Three-Tier Prompt Template
**What:** The generation prompt is restructured to label each information source with its authority level.
**When to use:** Every section generation call -- even pure MIDI input uses this template with an empty CONTEXTUAL section.
**Example:**
```python
# Prompt structure per section
"""
=== DEFINITIVE (User Hints -- always authoritative) ===
{user_hints_text or "No user hints provided."}

=== CONTEXTUAL (Audio Analysis) ===
{audio_description_summary or "No audio analysis available."}

=== RAW INPUT (MIDI Transcription -- treat as noisy suggestion) ===
{midi_content}

=== CURRENT MUSICAL STATE ===
{coherence_state}
"""
```

### Pattern 3: Natural Language Template Rendering
**What:** Convert structured AudioDescription JSON into readable natural language for the generation prompt. The LLM receives sentences, not JSON.
**When to use:** Before injecting audio description into the generation prompt.
**Example:**
```python
# src/engrave/audio/templates.py
def render_section_description(section: SectionDescription) -> str:
    """Convert structured section data to natural language summary."""
    parts = []
    parts.append(f"Section: {section.label}")
    if section.key:
        parts.append(f"Key: {section.key}")
    if section.active_instruments:
        parts.append(f"Active instruments: {', '.join(section.active_instruments)}")
    if section.texture:
        parts.append(f"Texture: {section.texture}")
    if section.dynamics:
        parts.append(f"Dynamics: {section.dynamics}")
    if section.notes:
        parts.append(f"Notes: {section.notes}")
    return ". ".join(parts) + "."
```

### Pattern 4: Audio Content via LiteLLM (Gemini)
**What:** Send audio as base64-encoded content in OpenAI message format via LiteLLM.
**When to use:** GeminiDescriber backend.
**Example:**
```python
import base64
from pathlib import Path

def _build_audio_message(audio_path: Path, prompt: str) -> list[dict]:
    """Build LiteLLM-compatible message with audio content."""
    audio_bytes = audio_path.read_bytes()
    encoded = base64.b64encode(audio_bytes).decode("utf-8")
    mime_type = "audio/wav"  # Normalized in Phase 5

    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "file",
                "file": {
                    "file_data": f"data:{mime_type};base64,{encoded}"
                },
            },
        ],
    }]
```

### Pattern 5: Structured Output via LiteLLM (Gemini)
**What:** Use LiteLLM's `response_format` with `json_schema` type to get schema-enforced JSON from Gemini.
**When to use:** GeminiDescriber backend to ensure valid AudioDescription JSON.
**Example:**
```python
import litellm
from engrave.audio.description import AudioDescription

response = await litellm.acompletion(
    model="gemini/gemini-3-flash",
    messages=messages,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "AudioDescription",
            "schema": AudioDescription.model_json_schema(),
        },
    },
)
# Parse response text as AudioDescription
desc = AudioDescription.model_validate_json(response.choices[0].message.content)
```

### Pattern 6: Hint Loading with Path/Inline Auto-Detection
**What:** The `--hints` flag accepts either inline text or a file path. Auto-detect by checking if the value is an existing file path.
**When to use:** CLI hint ingestion.
**Example:**
```python
# src/engrave/hints/loader.py
from pathlib import Path

def load_hints(raw: str | None) -> str:
    """Load hints from inline text or file path.

    If raw is None, returns empty string.
    If raw is an existing file path, reads and returns file content.
    Otherwise, treats raw as inline hint text.
    """
    if raw is None:
        return ""
    path = Path(raw)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return raw.strip()
```

### Anti-Patterns to Avoid
- **Routing hints to sections via LLM pre-pass:** Adds a fragile routing step. Typical hints are ~200 tokens; the 32K prompt budget has ample room to include them in every section. The generation LLM naturally ignores irrelevant hints per section.
- **Building a merge algorithm for conflict resolution:** The user decided this is prompt construction, not a merge algorithm. The generation LLM reconciles sources based on authority labels and musical context.
- **Using audio LM for section boundary detection:** Section boundaries come from MIDI (Phase 3). The audio LM labels pre-existing sections, not detects them.
- **Storing audio description as JSON in the generation prompt:** The user explicitly decided: natural language summary, not raw JSON. JSON stays in audit log and job artifacts.
- **Adding confidence scores to audio LM outputs:** Explicitly rejected. Disagreement between systems IS the signal.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio-to-JSON description | Custom audio analysis pipeline | Audio LM (Qwen3-Omni, Gemini 3 Flash) | Audio understanding requires neural models; hand-rolled feature extraction cannot capture style, texture, or articulation intent |
| JSON schema enforcement (Gemini) | Custom JSON parsing + validation | LiteLLM `response_format` with `json_schema` | Schema enforcement is native to Gemini API; reimplementing it adds complexity and loses model-level guarantees |
| JSON validation (local model) | Custom JSON extraction regex | Pydantic `model_validate_json()` with lenient parsing | Pydantic handles missing fields, type coercion, and clear error messages |
| Hint parsing / NLP | Custom regex or NLU pipeline | Pass raw text to generation LLM | The user explicitly decided: "the LLM is the parser." No structured markers, no regex extraction for v1 |
| Base64 audio encoding for API | Manual encoding logic | LiteLLM's file content format | LiteLLM standardizes the OpenAI-format message with audio content |

**Key insight:** The audio LM IS the feature extractor. The hint system IS just string passing. The conflict resolution IS just prompt construction. This phase is simpler than it appears because the "intelligence" lives in the generation LLM's interpretation of a well-structured prompt, not in custom algorithms.

## Common Pitfalls

### Pitfall 1: Audio LM Produces Invalid or Incomplete JSON
**What goes wrong:** Local Qwen3-Omni model produces malformed JSON, missing fields, or hallucinated field names that don't match the AudioDescription schema.
**Why it happens:** Structured JSON output from local models is less reliable than from Gemini's schema enforcement. The model may produce partial JSON, wrap it in markdown code blocks, or omit nullable fields entirely.
**How to avoid:**
1. Pydantic validation with `model_validate_json()` and lenient defaults: missing optional fields get default values, not exceptions.
2. Pre-processing: strip markdown code fences, extract JSON from mixed text/JSON responses.
3. Retry with simplified prompt on validation failure (max 2 retries).
4. Fallback: if local model fails after retries, produce a minimal AudioDescription with only MIDI-derived fields (key, tempo, time signature) and log a warning.
**Warning signs:** >20% of local model calls producing invalid JSON in testing.

### Pitfall 2: Audio File Too Large for Inline Base64 (Gemini)
**What goes wrong:** A 5-minute WAV file at 44.1kHz mono 16-bit is ~26MB. Base64 encoding inflates this by ~33% to ~35MB, exceeding Gemini's 20MB inline request size limit.
**Why it happens:** The Gemini API limits inline data to 20MB total request size. Audio files from Phase 5 can easily exceed this, especially for longer recordings.
**How to avoid:**
1. Use Gemini's Files API (`client.files.upload()`) for audio files >15MB. Upload first, then reference the file ID in the request.
2. Alternatively, downsample to 16kHz (Gemini downsamples internally anyway) before sending, reducing file size by ~63%.
3. Set a file size threshold in DescriberConfig: inline for <15MB, Files API for >15MB.
**Warning signs:** 413 or request size errors from Gemini API on longer recordings.

### Pitfall 3: Prompt Budget Exhaustion with Three-Tier Template
**What goes wrong:** Adding user hints (up to ~200 tokens) and audio description (300-500 tokens per section) to the existing prompt pushes close to the 32K budget, leaving less room for MIDI content and RAG examples.
**Why it happens:** The existing prompt budget (build_section_prompt) allocates 2000 for system instructions, 500 for template, 500 for coherence, 3000 for RAG, 4000 for MIDI, 8000 for output, and 4000 safety margin. Adding ~700 tokens of audio description + hints requires rebalancing.
**How to avoid:**
1. Audio description is compact by design (~300 tokens for a section summary sentence).
2. User hints are typically ~200 tokens.
3. Add a `description_tokens` allocation (~800 tokens) to PromptBudget by reducing safety_margin from 4000 to 3200.
4. The truncation priority (RAG > coherence > MIDI) remains unchanged; audio description and user hints are never truncated (they are small and high-authority).
**Warning signs:** RAG examples being aggressively truncated after adding audio description.

### Pitfall 4: Forgetting Pure MIDI Path
**What goes wrong:** The three-tier prompt template breaks when no audio exists (MIDI-only input). The CONTEXTUAL section is empty/missing, confusing the generation LLM.
**Why it happens:** Code paths diverge for audio vs. MIDI input but the prompt template is only tested with audio.
**How to avoid:**
1. The user explicitly decided: "Same three-tier template always, even for pure MIDI input. When no audio exists, the CONTEXTUAL section is empty/absent."
2. Test with both paths: audio+MIDI and MIDI-only.
3. When AudioDescription is None, the CONTEXTUAL block says "No audio analysis available. MIDI analysis provides the structural context."
**Warning signs:** Generation quality regression on MIDI-only input after Phase 6 changes.

### Pitfall 5: Qwen3-Omni Audio Inference Crashes or Hangs on Apple Silicon
**What goes wrong:** The local Qwen3-Omni model fails to load, hangs during audio processing, or produces empty output on Apple Silicon.
**Why it happens:** As of February 2026, mlx-vlm's Qwen3-Omni audio support is being actively added. The model may require specific quantization, have memory issues with long audio, or have unsupported audio preprocessing steps.
**How to avoid:**
1. Build the Gemini backend first. It is well-documented and fully supported.
2. Make the local backend optional: if `mlx-vlm` is not installed or the model is not available, skip local inference with a warning.
3. Set a timeout on local inference (e.g., 120 seconds). If it times out, fall back to Gemini or skip with warning.
4. Log memory usage during local inference to detect OOM risk.
**Warning signs:** Import errors for mlx-vlm, model loading taking >60 seconds, empty responses.

## Code Examples

### AudioDescription Pydantic Schema
```python
# src/engrave/audio/description.py
from pydantic import BaseModel, Field

class SectionDescription(BaseModel):
    """Audio LM annotations for a single section."""
    label: str = ""                           # e.g., "intro", "verse-1", "chorus-1"
    start_bar: int = 1
    end_bar: int = 1
    key: str | None = None                    # e.g., "Bb major" -- None if no change
    active_instruments: list[str] = Field(default_factory=list)
    texture: str = ""                         # e.g., "solo piano", "full ensemble block chords"
    dynamics: str = ""                        # e.g., "mf", "ff", "building from mp to f"
    notes: str | None = None                  # Nullable catch-all for stray observations

class AudioDescription(BaseModel):
    """Two-tier structured description from audio LM."""
    # Track-level metadata
    tempo_bpm: int = 120
    tempo_variable: bool = False              # True if tempo changes detected
    time_signature: str = "4/4"
    key: str = "C major"                      # Root + mode
    instruments: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)  # e.g., ["swing", "big band", "blues"]
    energy_arc: str = ""                      # e.g., "mp -> mf -> f -> ff -> mf"

    # Per-section annotations
    sections: list[SectionDescription] = Field(default_factory=list)
```

### GeminiDescriber Implementation
```python
# src/engrave/audio/describer.py (GeminiDescriber)
import base64
import json
from pathlib import Path

import litellm
from engrave.audio.description import AudioDescription

class GeminiDescriber:
    """Audio description via Gemini 3 Flash with schema-enforced JSON."""

    def __init__(self, model: str = "gemini/gemini-3-flash", api_key: str | None = None):
        self.model = model
        self.api_key = api_key

    async def describe(
        self,
        audio_path: Path,
        sections: list,
        tempo_bpm: int,
        ticks_per_beat: int,
    ) -> AudioDescription:
        prompt = self._build_prompt(sections, tempo_bpm)
        messages = self._build_messages(audio_path, prompt)

        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "AudioDescription",
                    "schema": AudioDescription.model_json_schema(),
                },
            },
            temperature=0.2,
        )

        raw_json = response.choices[0].message.content
        return AudioDescription.model_validate_json(raw_json)

    def _build_prompt(self, sections: list, tempo_bpm: int) -> str:
        section_labels = [
            f"Section {i+1}: bars {s.bar_number}-{sections[i+1].bar_number - 1 if i+1 < len(sections) else 'end'}"
            for i, s in enumerate(sections)
        ]
        return (
            "Analyze this audio recording and produce a structured musical description.\n\n"
            f"The recording has been segmented into {len(sections)} sections:\n"
            + "\n".join(f"  - {label}" for label in section_labels)
            + "\n\n"
            "For the overall track, identify: tempo, time signature, key, instruments present, "
            "style tags, and energy arc.\n\n"
            "For each section, identify: which instruments are active, the musical texture, "
            "dynamics level, and any notable observations.\n\n"
            "Focus on musical structure and character, NOT individual note accuracy. "
            "High-value observations include things like:\n"
            "  - 'This is a 12-bar blues in Bb'\n"
            "  - 'Saxophone takes melody while piano comps'\n"
            "  - 'Sounds like a Basie arrangement'\n"
            "  - 'Drummer on brushes'\n"
        )

    def _build_messages(self, audio_path: Path, prompt: str) -> list[dict]:
        audio_bytes = audio_path.read_bytes()
        encoded = base64.b64encode(audio_bytes).decode("utf-8")
        return [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "file": {
                        "file_data": f"data:audio/wav;base64,{encoded}"
                    },
                },
            ],
        }]
```

### Audit Log Structure
```python
# src/engrave/generation/audit.py
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

@dataclass
class FieldResolution:
    """Resolution record for a single field where sources might disagree."""
    field: str
    midi_value: str | None = None
    audio_value: str | None = None
    hint_value: str | None = None
    resolved_to: str = ""
    source: str = ""  # "hint", "audio", "midi"

@dataclass
class AuditEntry:
    """Per-section audit record tracking source resolution."""
    section_index: int
    section_label: str
    timestamp: str = ""
    resolutions: list[FieldResolution] = field(default_factory=list)

@dataclass
class AuditLog:
    """Full run audit log for per-field override tracking."""
    job_id: str = ""
    entries: list[AuditEntry] = field(default_factory=list)

    def write(self, output_dir: Path) -> Path:
        """Write audit log as JSON file in the output directory."""
        path = output_dir / "audit_log.json"
        path.write_text(json.dumps(asdict(self), indent=2))
        return path
```

### Three-Tier Prompt Integration
```python
# Modification to build_section_prompt in generation/prompts.py
def build_section_prompt_v2(
    section_midi: dict[str, str],
    coherence: CoherenceState,
    rag_examples: list[str],
    template: str,
    audio_description: str = "",    # NEW: rendered natural language summary
    user_hints: str = "",           # NEW: raw user hint text
    budget: PromptBudget | None = None,
) -> str:
    """Build three-tier section generation prompt."""
    if budget is None:
        budget = PromptBudget()

    # ... (budget fitting as before) ...

    # Three-tier authority structure
    hints_block = user_hints if user_hints else "No user hints provided."
    audio_block = audio_description if audio_description else "No audio analysis available."

    return f"""Generate LilyPond music content for the following section.

RULES:
1. Use ABSOLUTE pitch mode (no \\relative). Every note must have explicit octave marks.
2. Generate ONLY the music content for each instrument variable.
3. All pitches must be in CONCERT PITCH. Do not transpose for any instrument.
4. Preserve all musical content from the MIDI input: pitches, rhythms, dynamics.
5. Add appropriate articulations, dynamics, and expression marks based on the musical context.
6. Output each instrument's music as a separate block labeled with the variable name.

=== DEFINITIVE (User Hints -- always authoritative) ===
{hints_block}

=== CONTEXTUAL (Audio Analysis -- structural observations) ===
{audio_block}

=== CURRENT MUSICAL STATE ===
{fitted_coherence}

LILYPOND TEMPLATE (fill in the instrument variables):
{template}

SIMILAR EXAMPLES FROM CORPUS:
{rag_text}

=== RAW INPUT (MIDI Transcription -- treat as noisy suggestion) ===
{fitted_midi}

Generate the LilyPond music content for each instrument variable:"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qwen2-Audio-7B for audio understanding | Qwen3-Omni-30B-A3B-Captioner (MoE) | Sep 2025 | 4x parameter efficiency via MoE, SOTA on 32/36 audio benchmarks, designed for captioning |
| Gemini 2.5 Flash for cloud audio | Gemini 3 Flash | Dec 2025 | 1M token context, native structured output with JSON Schema, improved audio understanding |
| Manual JSON parsing of LLM output | Schema-enforced JSON (Gemini) + Pydantic validation (local) | 2025-2026 | Near-zero JSON format errors on Gemini path; robust fallback on local path |
| Direct API calls per provider | LiteLLM unified interface | Already in use | Same abstraction handles both providers |

**Deprecated/outdated:**
- Qwen2-Audio-7B-Instruct: OBSOLETE (Aug 2024, 2 generations behind)
- Qwen2.5-Omni-7B: SUPERSEDED (Mar 2025)
- Gemini 2.5 Flash: OUTDATED -- Gemini 3 Flash is current

## Open Questions

1. **Qwen3-Omni via mlx-vlm: audio input support readiness**
   - What we know: mlx-vlm supports "omni models with audio and video support" and Qwen3-VL is supported. A GitHub issue (ml-explore/mlx-lm#497) shows text generation for Qwen3-Omni works, but full multimodal audio input is being actively added via mlx-vlm.
   - What's unclear: Whether Qwen3-Omni-30B-A3B-Captioner specifically works with audio input via mlx-vlm's Python API as of February 2026. The model loads, but audio preprocessing may not be fully implemented.
   - Recommendation: Build Gemini backend first. Add local backend when mlx-vlm audio support is confirmed. Make local backend import-guarded so it fails gracefully.

2. **LiteLLM audio + structured output combination for Gemini**
   - What we know: LiteLLM supports both audio content (base64 in messages) and structured output (response_format with json_schema) separately. Gemini 3 Flash supports both natively.
   - What's unclear: Whether LiteLLM correctly passes both audio content AND response_format in a single request. The Gemini API has a limitation that function calling cannot be combined with response_mime_type, but json_schema response_format is different.
   - Recommendation: Test this combination early. If it fails, fall back to: (a) prompt-based JSON instruction without schema enforcement + Pydantic validation, or (b) use google-genai SDK directly for the Gemini path.

3. **Audio file size handling for Gemini inline vs Files API**
   - What we know: Gemini inline data limit is 20MB total request size. A 5-minute 44.1kHz mono WAV is ~26MB. Base64 inflates by 33%.
   - What's unclear: Whether LiteLLM has built-in support for the Gemini Files API, or if we need to use google-genai SDK for file uploads.
   - Recommendation: For v1, downsample audio to 16kHz before sending to Gemini (Gemini downsamples internally anyway). This reduces a 5-min file from ~26MB to ~9.6MB, well within the inline limit. Add Files API support later if needed.

4. **Describer role configuration**
   - What we know: The existing `engrave.toml` has a `[roles.describer]` configured for `anthropic/claude-opus-4-6`. Phase 6 needs a separate role for audio LM calls (Gemini or local Qwen3-Omni).
   - What's unclear: Whether to reuse the existing `describer` role or add a new `audio_describer` role.
   - Recommendation: Add a new `[roles.audio_describer]` role for the audio LM. The existing `describer` role serves a different purpose (text description). The audio describer needs multimodal capability. The Describer protocol implementation selects the backend based on model prefix (gemini/* = Gemini, local/* = mlx-vlm).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/unit/ -x --timeout=30` |
| Full suite command | `pytest tests/ --timeout=120` |
| Estimated runtime | ~15 seconds (unit), ~45 seconds (full) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDP-03 | AudioDescription schema validates correctly | unit | `pytest tests/unit/test_description.py -x` | No -- Wave 0 gap (name will not conflict with existing test_description.py in corpus; use test_audio_description.py) |
| AUDP-03 | GeminiDescriber produces valid AudioDescription from audio | unit (mocked) | `pytest tests/unit/test_describer.py -x` | No -- Wave 0 gap |
| AUDP-03 | Natural language template renders section description | unit | `pytest tests/unit/test_audio_templates.py -x` | No -- Wave 0 gap |
| AUDP-03 | Describer handles errors/timeouts gracefully | unit (mocked) | `pytest tests/unit/test_describer.py::test_error_handling -x` | No -- Wave 0 gap |
| AUDP-04 | Hint loader auto-detects inline vs file path | unit | `pytest tests/unit/test_hint_loader.py -x` | No -- Wave 0 gap |
| AUDP-04 | Three-tier prompt contains all authority sections | unit | `pytest tests/unit/test_prompt_budget.py::test_three_tier -x` | No -- Wave 0 gap |
| AUDP-04 | User hints override audio description in prompt | unit | `pytest tests/unit/test_prompt_budget.py::test_hint_authority -x` | No -- Wave 0 gap |
| AUDP-04 | Audit log records per-field resolution | unit | `pytest tests/unit/test_audit.py -x` | No -- Wave 0 gap |
| AUDP-03+04 | Pipeline integrates description + hints into generation | integration (mocked LLM) | `pytest tests/integration/test_audio_generation.py -x` | No -- Wave 0 gap |
| AUDP-04 | CLI --hints flag accepts inline and file path | unit | `pytest tests/unit/test_hint_loader.py -x` | No -- Wave 0 gap |
| AUDP-03+04 | Pure MIDI path works with three-tier template (no audio) | integration | `pytest tests/integration/test_audio_generation.py::test_midi_only -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `pytest tests/unit/ -x --timeout=30`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_audio_description.py` -- covers AUDP-03 (schema validation)
- [ ] `tests/unit/test_describer.py` -- covers AUDP-03 (protocol, GeminiDescriber mocked)
- [ ] `tests/unit/test_audio_templates.py` -- covers AUDP-03 (NL template rendering)
- [ ] `tests/unit/test_hint_loader.py` -- covers AUDP-04 (inline vs file path)
- [ ] `tests/unit/test_audit.py` -- covers AUDP-04 (audit log format)
- [ ] `tests/integration/test_audio_generation.py` -- covers AUDP-03+04 (pipeline integration, MIDI-only regression)
- [ ] Existing `tests/unit/test_prompt_budget.py` extended -- covers AUDP-04 (three-tier prompt)

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/engrave/audio/transcriber.py` -- Transcriber Protocol pattern to mirror
- Project codebase: `src/engrave/generation/prompts.py` -- existing prompt builder to modify
- Project codebase: `src/engrave/generation/coherence.py` -- CoherenceState integration point
- Project codebase: `src/engrave/generation/pipeline.py` -- generation pipeline to integrate with
- Project codebase: `src/engrave/config/settings.py` -- settings pattern to extend
- Project codebase: `src/engrave/midi/sections.py` -- section boundaries (consumed by Describer)
- [LiteLLM Gemini docs](https://docs.litellm.ai/docs/providers/gemini) -- audio content format, structured output
- [LiteLLM Structured Outputs docs](https://docs.litellm.ai/docs/completion/json_mode) -- response_format with json_schema
- [Gemini API Audio Understanding docs](https://ai.google.dev/gemini-api/docs/audio) -- formats, limits, token costs
- [Gemini API Structured Output docs](https://ai.google.dev/gemini-api/docs/structured-output) -- response_mime_type, response_schema

### Secondary (MEDIUM confidence)
- [Qwen3-Omni GitHub](https://github.com/QwenLM/Qwen3-Omni) -- model capabilities, usage patterns
- [Qwen3-Omni-30B-A3B-Captioner HuggingFace](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Captioner) -- model card, captioning specialization
- [mlx-vlm GitHub](https://github.com/Blaizzy/mlx-vlm) -- omni model support with audio, Python API
- [mlx-lm#497 Qwen3-Omni support issue](https://github.com/ml-explore/mlx-lm/issues/497) -- status of audio input support
- [LiteLLM Gemini 3 day-0 support](https://docs.litellm.ai/blog/gemini_3) -- Gemini 3 Flash integration

### Tertiary (LOW confidence)
- vllm-mlx audio support status -- inferred from README, not verified for Qwen3-Omni audio input specifically
- mlx-vlm Qwen3-Omni audio inference on Apple Silicon -- community status indicates active development; actual readiness needs hands-on validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - LiteLLM, Pydantic, and existing project patterns are well-understood and documented
- Architecture: HIGH - Describer protocol mirrors established Transcriber pattern; prompt restructuring is a modification of existing code
- Pitfalls: MEDIUM-HIGH - Gemini path well-documented; local Qwen3-Omni path has uncertainty around mlx-vlm audio readiness
- Audio LM integration: MEDIUM - Gemini path is HIGH confidence; local Qwen3-Omni path is MEDIUM-LOW due to evolving mlx-vlm support

**Research date:** 2026-02-24
**Valid until:** 2026-03-10 (Gemini API stable; mlx-vlm audio support may change rapidly)
