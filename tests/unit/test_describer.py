"""Unit tests for the Describer protocol and GeminiDescriber (mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from engrave.audio.describer import Describer, GeminiDescriber, create_describer
from engrave.audio.description import AudioDescription
from engrave.config.settings import DescriberConfig
from engrave.midi.sections import SectionBoundary

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DESCRIPTION_JSON = json.dumps(
    {
        "tempo_bpm": 142,
        "tempo_variable": False,
        "time_signature": "4/4",
        "key": "Bb major",
        "instruments": ["trumpet", "piano", "bass", "drums"],
        "style_tags": ["swing", "big band"],
        "energy_arc": "mp -> mf -> f",
        "sections": [
            {
                "label": "intro",
                "start_bar": 1,
                "end_bar": 8,
                "key": "Bb major",
                "active_instruments": ["piano"],
                "texture": "solo piano",
                "dynamics": "mp",
                "notes": None,
            },
            {
                "label": "verse-1",
                "start_bar": 9,
                "end_bar": 24,
                "key": None,
                "active_instruments": ["trumpet", "piano", "bass", "drums"],
                "texture": "walking bass under trumpet melody",
                "dynamics": "mf",
                "notes": "sounds like a Basie arrangement",
            },
        ],
    }
)


def _make_mock_response(content: str) -> AsyncMock:
    """Build a mock litellm response with the given content."""
    response = AsyncMock()
    choice = AsyncMock()
    choice.message.content = content
    response.choices = [choice]
    return response


@pytest.fixture
def sections() -> list[SectionBoundary]:
    """Sample section boundaries."""
    return [
        SectionBoundary(bar_number=1, boundary_type="start", tick=0),
        SectionBoundary(bar_number=9, boundary_type="rehearsal", tick=3840),
    ]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestDescriberProtocol:
    """GeminiDescriber satisfies the Describer protocol."""

    def test_describer_protocol_conformance(self) -> None:
        """GeminiDescriber is a Describer per runtime_checkable."""
        d = GeminiDescriber()
        assert isinstance(d, Describer)


# ---------------------------------------------------------------------------
# GeminiDescriber functionality
# ---------------------------------------------------------------------------


class TestGeminiDescriber:
    """GeminiDescriber with mocked litellm.acompletion."""

    @pytest.mark.asyncio
    async def test_gemini_describer_builds_audio_message(
        self, sample_wav: Path, sections: list[SectionBoundary]
    ) -> None:
        """describe() sends base64-encoded audio and section info to litellm."""
        mock = AsyncMock(return_value=_make_mock_response(SAMPLE_DESCRIPTION_JSON))

        with patch("engrave.audio.describer.litellm") as mock_litellm:
            mock_litellm.acompletion = mock
            d = GeminiDescriber(model="gemini/gemini-3-flash")
            await d.describe(sample_wav, sections, tempo_bpm=142, ticks_per_beat=480)

        # Verify acompletion was called
        mock.assert_called_once()
        call_kwargs = mock.call_args[1]

        # Check message structure
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        assert any(item.get("type") == "text" for item in content)
        assert any(item.get("type") == "file" for item in content)

        # Verify prompt mentions sections
        text_content = next(item["text"] for item in content if item.get("type") == "text")
        assert "Section" in text_content
        assert "142 BPM" in text_content

        # Verify base64 audio
        file_content = next(item for item in content if item.get("type") == "file")
        assert file_content["file"]["file_data"].startswith("data:audio/wav;base64,")

    @pytest.mark.asyncio
    async def test_gemini_describer_returns_audio_description(
        self, sample_wav: Path, sections: list[SectionBoundary]
    ) -> None:
        """describe() returns a valid AudioDescription from mocked response."""
        mock = AsyncMock(return_value=_make_mock_response(SAMPLE_DESCRIPTION_JSON))

        with patch("engrave.audio.describer.litellm") as mock_litellm:
            mock_litellm.acompletion = mock
            d = GeminiDescriber()
            result = await d.describe(sample_wav, sections, tempo_bpm=142, ticks_per_beat=480)

        assert isinstance(result, AudioDescription)
        assert result.tempo_bpm == 142
        assert result.key == "Bb major"
        assert len(result.sections) == 2
        assert result.sections[0].label == "intro"
        assert result.sections[1].notes == "sounds like a Basie arrangement"

    @pytest.mark.asyncio
    async def test_gemini_describer_retry_on_validation_error(
        self, sample_wav: Path, sections: list[SectionBoundary]
    ) -> None:
        """describe() retries once on validation error, returns valid result on second try."""
        invalid_response = _make_mock_response("not valid json {{{")
        valid_response = _make_mock_response(SAMPLE_DESCRIPTION_JSON)
        mock = AsyncMock(side_effect=[invalid_response, valid_response])

        with patch("engrave.audio.describer.litellm") as mock_litellm:
            mock_litellm.acompletion = mock
            d = GeminiDescriber(max_retries=1)
            result = await d.describe(sample_wav, sections, tempo_bpm=142, ticks_per_beat=480)

        assert isinstance(result, AudioDescription)
        assert result.tempo_bpm == 142
        assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_gemini_describer_fallback_on_persistent_failure(
        self, sample_wav: Path, sections: list[SectionBoundary]
    ) -> None:
        """describe() returns minimal AudioDescription when all retries fail."""
        invalid_response = _make_mock_response("not valid json {{{")
        mock = AsyncMock(return_value=invalid_response)

        with patch("engrave.audio.describer.litellm") as mock_litellm:
            mock_litellm.acompletion = mock
            d = GeminiDescriber(max_retries=1)
            result = await d.describe(sample_wav, sections, tempo_bpm=142, ticks_per_beat=480)

        assert isinstance(result, AudioDescription)
        # Minimal defaults
        assert result.tempo_bpm == 120
        assert result.key == "C major"
        assert result.sections == []

    @pytest.mark.asyncio
    async def test_gemini_describer_timeout_returns_minimal(
        self, sample_wav: Path, sections: list[SectionBoundary]
    ) -> None:
        """describe() returns minimal AudioDescription on timeout."""
        mock = AsyncMock(side_effect=TimeoutError("Request timed out"))

        with patch("engrave.audio.describer.litellm") as mock_litellm:
            mock_litellm.acompletion = mock
            d = GeminiDescriber(max_retries=1)
            result = await d.describe(sample_wav, sections, tempo_bpm=142, ticks_per_beat=480)

        assert isinstance(result, AudioDescription)
        assert result.tempo_bpm == 120
        assert result.sections == []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    """create_describer factory function."""

    def test_create_describer_factory(self) -> None:
        """create_describer(DescriberConfig()) returns a GeminiDescriber."""
        config = DescriberConfig()
        d = create_describer(config)
        assert isinstance(d, GeminiDescriber)
        assert isinstance(d, Describer)

    def test_create_describer_passes_config(self) -> None:
        """create_describer forwards config values to the GeminiDescriber."""
        config = DescriberConfig(
            model="gemini/gemini-3-pro",
            timeout=60,
            max_file_size_mb=10,
            max_retries=2,
        )
        d = create_describer(config)
        assert isinstance(d, GeminiDescriber)
        assert d.model == "gemini/gemini-3-pro"
        assert d.timeout == 60
        assert d.max_file_size_mb == 10
        assert d.max_retries == 2
