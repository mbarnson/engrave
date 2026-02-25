"""Describer protocol and concrete audio LM backends.

Defines a ``Protocol``-based contract for audio-in, ``AudioDescription``-out
analysis.  The primary backend (``GeminiDescriber``) sends audio to Gemini 3
Flash via ``litellm.acompletion`` with schema-enforced JSON output.

The Describer is async (I/O-bound audio LM calls) and bypasses the
``InferenceRouter`` -- different input modality, different API surface.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

import litellm

from engrave.audio.description import AudioDescription
from engrave.midi.sections import SectionBoundary

logger = logging.getLogger(__name__)


@runtime_checkable
class Describer(Protocol):
    """Audio-in, AudioDescription-out contract for pluggable audio LM backends."""

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
            tempo_bpm: Tempo from MIDI analysis for context.
            ticks_per_beat: MIDI resolution for context.

        Returns:
            AudioDescription with track-level and per-section annotations.
        """
        ...


class GeminiDescriber:
    """Audio description via Gemini 3 Flash with schema-enforced JSON.

    Sends base64-encoded audio to Gemini via LiteLLM and parses the
    schema-enforced JSON response into an ``AudioDescription``.  On
    validation failure, retries once with a simplified prompt.  On
    persistent failure or timeout, returns a minimal ``AudioDescription``
    with defaults.

    If the audio file exceeds ``max_file_size_mb``, it is downsampled to
    16 kHz before encoding (Gemini downsamples internally anyway).
    """

    def __init__(
        self,
        model: str = "gemini/gemini-3-flash",
        api_key: str | None = None,
        timeout: int = 120,
        max_file_size_mb: int = 15,
        max_retries: int = 1,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_file_size_mb = max_file_size_mb
        self.max_retries = max_retries

    async def describe(
        self,
        audio_path: Path,
        sections: list[SectionBoundary],
        tempo_bpm: int,
        ticks_per_beat: int,
    ) -> AudioDescription:
        """Analyse audio and return a structured AudioDescription."""
        prompt = self._build_prompt(sections, tempo_bpm)
        audio_bytes = self._prepare_audio(audio_path)
        messages = self._build_messages(audio_bytes, prompt)

        for attempt in range(1 + self.max_retries):
            try:
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
                    timeout=self.timeout,
                )
                raw_json = response.choices[0].message.content
                return AudioDescription.model_validate_json(raw_json)
            except Exception as exc:
                is_last = attempt >= self.max_retries
                if is_last:
                    logger.warning(
                        "Describer failed after %d attempt(s): %s. "
                        "Returning minimal AudioDescription.",
                        attempt + 1,
                        exc,
                    )
                    return AudioDescription()
                logger.info(
                    "Describer attempt %d failed (%s), retrying with simplified prompt.",
                    attempt + 1,
                    exc,
                )
                # Simplify prompt for retry
                messages = self._build_messages(
                    audio_bytes,
                    "Analyze this audio and return a JSON object with musical metadata "
                    "(tempo_bpm, time_signature, key, instruments, style_tags, energy_arc, sections).",
                )

        # Should not reach here, but satisfy type checker
        return AudioDescription()  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, sections: list[SectionBoundary], tempo_bpm: int) -> str:
        """Build the analysis prompt including section boundary info."""
        section_labels = []
        for i, s in enumerate(sections):
            end_bar = sections[i + 1].bar_number - 1 if i + 1 < len(sections) else "end"
            section_labels.append(
                f"  - Section {i + 1}: bars {s.bar_number}-{end_bar} (type: {s.boundary_type})"
            )

        section_text = (
            "\n".join(section_labels) if section_labels else "  (no section boundaries provided)"
        )

        return (
            "Analyze this audio recording and produce a structured musical description.\n\n"
            f"The MIDI analysis detected a tempo of approximately {tempo_bpm} BPM.\n\n"
            f"The recording has been segmented into {len(sections)} section(s):\n"
            f"{section_text}\n\n"
            "For the overall track, identify: tempo, time signature, key, instruments present, "
            "style tags, and energy arc.\n\n"
            "For each section, identify: which instruments are active, the musical texture, "
            "dynamics level, and any notable observations.\n\n"
            "Focus on musical structure and character, NOT individual note accuracy. "
            "High-value observations include things like:\n"
            '  - "This is a 12-bar blues in Bb"\n'
            '  - "Saxophone takes melody while piano comps"\n'
            '  - "Sounds like a Basie arrangement"\n'
            '  - "Drummer on brushes"\n'
        )

    def _prepare_audio(self, audio_path: Path) -> bytes:
        """Read audio bytes, downsampling if file exceeds size threshold."""
        audio_bytes = audio_path.read_bytes()
        size_mb = len(audio_bytes) / (1024 * 1024)

        if size_mb > self.max_file_size_mb:
            logger.info(
                "Audio file %.1f MB exceeds %d MB threshold, downsampling to 16kHz.",
                size_mb,
                self.max_file_size_mb,
            )
            try:
                from pydub import AudioSegment

                segment = AudioSegment.from_file(audio_path)
                segment = segment.set_frame_rate(16000)
                # Export to bytes in WAV format
                import io

                buf = io.BytesIO()
                segment.export(buf, format="wav")
                audio_bytes = buf.getvalue()
            except Exception:
                logger.warning(
                    "Downsampling failed, sending original audio (%.1f MB).",
                    size_mb,
                )

        return audio_bytes

    def _build_messages(self, audio_bytes: bytes, prompt: str) -> list[dict]:
        """Build LiteLLM-compatible messages with base64 audio content."""
        encoded = base64.b64encode(audio_bytes).decode("utf-8")
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {
                            "file_data": f"data:audio/wav;base64,{encoded}",
                        },
                    },
                ],
            }
        ]


def create_describer(config: object) -> Describer:
    """Factory: create a Describer from a DescriberConfig.

    Args:
        config: A ``DescriberConfig`` instance (or any object with
            ``model``, ``timeout``, ``max_file_size_mb``, ``max_retries``
            attributes).

    Returns:
        A ``GeminiDescriber`` configured per the supplied config.
    """
    return GeminiDescriber(
        model=getattr(config, "model", "gemini/gemini-3-flash"),
        api_key=getattr(config, "api_key", None),
        timeout=getattr(config, "timeout", 120),
        max_file_size_mb=getattr(config, "max_file_size_mb", 15),
        max_retries=getattr(config, "max_retries", 1),
    )
