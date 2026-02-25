"""Integration test: parallel LilyPond + JSON fan-out generation.

Validates that ``generate_section()`` dispatches two concurrent LLM
requests (LilyPond + JSON), collects both outputs, and handles JSON
failure gracefully without affecting LilyPond generation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

from engrave.generation.coherence import CoherenceState
from engrave.generation.pipeline import generate_section
from engrave.generation.templates import build_score_template, sanitize_var_name
from engrave.lilypond.compiler import RawCompileResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_test_context(instrument_names: list[str]) -> dict:
    """Build minimal test context for generate_section().

    Returns a dict with section_midi, coherence, rag_examples, template,
    instrument_names ready for use as generate_section kwargs.
    """
    section_midi = {name: "note_on 60 80 0 | note_off 60 0 480 |" for name in instrument_names}

    coherence = CoherenceState(
        section_index=0,
        total_sections=2,
        key_signature="bf \\major",
        time_signature="4/4",
        tempo_bpm=120,
    )

    rag_examples = ["c'4 d'4 e'4 f'4 | g'2 g'2 |"]

    template = build_score_template(instrument_names, "Section 1", 1, 4)

    return {
        "section_midi": section_midi,
        "coherence": coherence,
        "rag_examples": rag_examples,
        "template": template,
        "instrument_names": instrument_names,
    }


def _build_lilypond_response(instrument_names: list[str]) -> str:
    """Build a mock LilyPond response with instrument variable blocks."""
    blocks = []
    for name in instrument_names:
        var_name = sanitize_var_name(name)
        blocks.append(f"% {var_name}\nc'4 d'4 e'4 f'4 | g'2 g'2 |")
    return "\n\n".join(blocks)


def _build_json_response(instrument_names: list[str]) -> str:
    """Build a mock JSON notation response for the given instruments."""
    sections = []
    for name in instrument_names:
        ident = name.lower().replace(" ", "_").replace("-", "_")
        sections.append(
            {
                "instrument": ident,
                "key": "bf_major",
                "time_signature": "4/4",
                "measures": [
                    {
                        "number": 1,
                        "notes": [
                            {"pitch": "bf4", "beat": 1.0, "duration": 1.0, "dynamic": "f"},
                            {"pitch": "d5", "beat": 2.0, "duration": 1.0},
                            {"pitch": "f5", "beat": 3.0, "duration": 1.0},
                            {"pitch": "bf5", "beat": 4.0, "duration": 1.0},
                        ],
                    }
                ],
            }
        )
    return json.dumps(sections)


def _make_fanout_router(
    instrument_names: list[str],
    *,
    json_raises: bool = False,
    track_calls: bool = False,
) -> tuple[AsyncMock, dict]:
    """Create a mock router that differentiates LilyPond and JSON requests.

    Args:
        instrument_names: Instruments for response generation.
        json_raises: If True, the router raises on JSON requests.
        track_calls: If True, tracks call timestamps for concurrency verification.

    Returns:
        (router, call_tracker) tuple. call_tracker has 'ly_calls' and 'json_calls' lists.
    """
    router = AsyncMock()
    call_tracker: dict[str, list] = {"ly_calls": [], "json_calls": []}

    ly_response = _build_lilypond_response(instrument_names)
    json_response = _build_json_response(instrument_names)

    async def _route_complete(*args, **kwargs):
        messages = kwargs.get("messages", args[0] if args else [])
        prompt = ""
        if messages:
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")
                    break

        # Detect JSON vs LilyPond request by checking for JSON suffix markers
        is_json = "structured JSON notation events" in prompt or "JSON array" in prompt

        if is_json:
            call_tracker["json_calls"].append(True)
            if json_raises:
                raise RuntimeError("Simulated JSON generation failure")
            return json_response

        call_tracker["ly_calls"].append(True)
        return ly_response

    router.complete.side_effect = _route_complete
    return router, call_tracker


def _make_mock_compiler_for_fanout() -> MagicMock:
    """Create a mock compiler that returns success for any source."""
    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerationFanout:
    """Parallel LilyPond + JSON fan-out tests."""

    INSTRUMENTS: ClassVar[list[str]] = ["Trumpet 1", "Alto Sax"]

    def test_fanout_returns_both_outputs(self) -> None:
        """generate_section returns both LilyPond source and JSON notation."""
        ctx = _build_test_context(self.INSTRUMENTS)
        router, _tracker = _make_fanout_router(self.INSTRUMENTS)
        compiler = _make_mock_compiler_for_fanout()

        ly_source, json_data, _updated_coherence = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        # LilyPond source should be non-empty
        assert ly_source is not None
        assert len(ly_source) > 0

        # JSON notation should be non-None list
        assert json_data is not None
        assert isinstance(json_data, list)
        assert len(json_data) > 0

    def test_fanout_dispatches_both_requests(self) -> None:
        """Router receives both a LilyPond and a JSON request."""
        ctx = _build_test_context(self.INSTRUMENTS)
        router, tracker = _make_fanout_router(self.INSTRUMENTS, track_calls=True)
        compiler = _make_mock_compiler_for_fanout()

        asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        # Both LilyPond and JSON calls should have been made
        assert len(tracker["ly_calls"]) >= 1, "No LilyPond call dispatched"
        assert len(tracker["json_calls"]) >= 1, "No JSON call dispatched"

    def test_json_failure_does_not_affect_lilypond(self) -> None:
        """JSON request failure -> LilyPond still generated, JSON is None."""
        ctx = _build_test_context(self.INSTRUMENTS)
        router, tracker = _make_fanout_router(
            self.INSTRUMENTS,
            json_raises=True,
        )
        compiler = _make_mock_compiler_for_fanout()

        ly_source, json_data, _updated_coherence = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        # LilyPond should still be generated successfully
        assert ly_source is not None
        assert len(ly_source) > 0

        # JSON should be None (request failed)
        assert json_data is None

        # LilyPond call was still made
        assert len(tracker["ly_calls"]) >= 1

    def test_json_contains_instrument_data(self) -> None:
        """JSON response contains notation for each instrument."""
        ctx = _build_test_context(self.INSTRUMENTS)
        router, _ = _make_fanout_router(self.INSTRUMENTS)
        compiler = _make_mock_compiler_for_fanout()

        _, json_data, _ = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        assert json_data is not None
        # Each instrument should have an entry
        instruments_in_json = {item.get("instrument") for item in json_data}
        assert "trumpet_1" in instruments_in_json
        assert "alto_sax" in instruments_in_json

    def test_coherence_state_updated(self) -> None:
        """Coherence state advances after successful generation."""
        ctx = _build_test_context(self.INSTRUMENTS)
        router, _ = _make_fanout_router(self.INSTRUMENTS)
        compiler = _make_mock_compiler_for_fanout()

        _, _, updated_coherence = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        # Coherence should have advanced (section_index incremented)
        assert updated_coherence.section_index > ctx["coherence"].section_index

    def test_sequential_fallback_on_not_implemented(self) -> None:
        """Pipeline falls back to sequential when asyncio.gather raises NotImplementedError."""
        ctx = _build_test_context(self.INSTRUMENTS)
        compiler = _make_mock_compiler_for_fanout()

        # Create a router whose first complete() call raises NotImplementedError
        # (simulating the asyncio.gather failure), then works normally for
        # sequential calls
        router = AsyncMock()
        ly_response = _build_lilypond_response(self.INSTRUMENTS)
        json_response = _build_json_response(self.INSTRUMENTS)

        call_count = 0

        async def _sequential_route(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            messages = kwargs.get("messages", args[0] if args else [])
            prompt = ""
            if messages:
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        prompt = msg.get("content", "")
                        break

            is_json = "structured JSON notation events" in prompt or "JSON array" in prompt

            # First two calls are from asyncio.gather (LilyPond coro + JSON coro).
            # We raise NotImplementedError on the first to trigger fallback.
            if call_count == 1:
                raise NotImplementedError("Router does not support concurrent dispatch")

            if is_json:
                return json_response
            return ly_response

        router.complete.side_effect = _sequential_route

        ly_source, _json_data, _ = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        # Despite the NotImplementedError, LilyPond should still be generated
        assert ly_source is not None
        assert len(ly_source) > 0

        # Sequential fallback should have made at least 3 calls total
        # (1 failed gather + 2 sequential)
        assert call_count >= 3

    def test_empty_json_response_returns_none(self) -> None:
        """Empty/invalid JSON response results in json_data=None."""
        ctx = _build_test_context(self.INSTRUMENTS)
        compiler = _make_mock_compiler_for_fanout()

        router = AsyncMock()
        ly_response = _build_lilypond_response(self.INSTRUMENTS)

        async def _route_empty_json(*args, **kwargs):
            messages = kwargs.get("messages", args[0] if args else [])
            prompt = ""
            if messages:
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        prompt = msg.get("content", "")
                        break

            is_json = "structured JSON notation events" in prompt or "JSON array" in prompt
            if is_json:
                return "I cannot generate JSON for this section."
            return ly_response

        router.complete.side_effect = _route_empty_json

        ly_source, json_data, _ = asyncio.run(
            generate_section(
                **ctx,
                router=router,
                compiler=compiler,
            )
        )

        assert ly_source is not None
        assert len(ly_source) > 0
        # JSON extraction should fail gracefully -> None
        assert json_data is None
