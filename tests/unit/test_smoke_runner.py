"""Unit tests for smoke test runner: input discovery, data model serialization.

Does NOT use pytest-bdd/Gherkin -- straightforward unit tests.
Does NOT test pipeline execution (that requires real LLM/audio infrastructure).
"""

from __future__ import annotations

import json
from pathlib import Path

from engrave.smoke.runner import (
    CheckResult,
    InputResult,
    SmokeResult,
    discover_inputs,
    smoke_result_to_dict,
)

# ---------------------------------------------------------------------------
# discover_inputs
# ---------------------------------------------------------------------------


class TestDiscoverInputs:
    def test_discovers_audio_files(self, tmp_path: Path) -> None:
        """Audio extensions are recognized and tagged as 'audio'."""
        (tmp_path / "song.wav").touch()
        (tmp_path / "track.mp3").touch()
        (tmp_path / "recording.flac").touch()
        (tmp_path / "sample.aiff").touch()

        inputs = discover_inputs(tmp_path)
        assert len(inputs) == 4
        for _path, ptype in inputs:
            assert ptype == "audio"

    def test_discovers_midi_files(self, tmp_path: Path) -> None:
        """MIDI extensions are recognized and tagged as 'midi'."""
        (tmp_path / "blue-train.mid").touch()
        (tmp_path / "all-blues.midi").touch()

        inputs = discover_inputs(tmp_path)
        assert len(inputs) == 2
        for _path, ptype in inputs:
            assert ptype == "midi"

    def test_ignores_non_audio_midi_files(self, tmp_path: Path) -> None:
        """Non-audio/MIDI files are ignored."""
        (tmp_path / "readme.txt").touch()
        (tmp_path / "notes.pdf").touch()
        (tmp_path / "data.json").touch()

        inputs = discover_inputs(tmp_path)
        assert inputs == []

    def test_mixed_extensions(self, tmp_path: Path) -> None:
        """Mix of audio, MIDI, and other files returns only audio/MIDI."""
        (tmp_path / "audio.wav").touch()
        (tmp_path / "midi.mid").touch()
        (tmp_path / "readme.txt").touch()

        inputs = discover_inputs(tmp_path)
        assert len(inputs) == 2
        paths_and_types = {(p.name, t) for p, t in inputs}
        assert ("audio.wav", "audio") in paths_and_types
        assert ("midi.mid", "midi") in paths_and_types

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        inputs = discover_inputs(tmp_path)
        assert inputs == []

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Results are sorted by filename."""
        (tmp_path / "z-last.wav").touch()
        (tmp_path / "a-first.mid").touch()
        (tmp_path / "m-middle.mp3").touch()

        inputs = discover_inputs(tmp_path)
        names = [p.name for p, _ in inputs]
        assert names == sorted(names)

    def test_case_insensitive_extensions(self, tmp_path: Path) -> None:
        """Extensions are matched case-insensitively."""
        (tmp_path / "song.WAV").touch()
        (tmp_path / "track.MID").touch()

        inputs = discover_inputs(tmp_path)
        assert len(inputs) == 2

    def test_skips_directories(self, tmp_path: Path) -> None:
        """Directories in the test dir are skipped."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "song.wav").touch()

        inputs = discover_inputs(tmp_path)
        assert len(inputs) == 1
        assert inputs[0][0].name == "song.wav"


# ---------------------------------------------------------------------------
# Data model serialization
# ---------------------------------------------------------------------------


class TestDataModelSerialization:
    def test_check_result_to_dict(self) -> None:
        """CheckResult converts to dict with all fields."""
        cr = CheckResult(
            name="test_check",
            passed=True,
            message="all good",
            details={"count": 5},
        )
        d = smoke_result_to_dict(
            SmokeResult(
                inputs=[
                    InputResult(
                        input_path=Path("/tmp/test.mid"),
                        pipeline_path="midi",
                        checks=[cr],
                    )
                ]
            )
        )
        check_dict = d["inputs"][0]["checks"][0]
        assert check_dict["name"] == "test_check"
        assert check_dict["passed"] is True
        assert check_dict["details"]["count"] == 5

    def test_smoke_result_serializes_to_json(self) -> None:
        """SmokeResult serializes to valid JSON."""
        result = SmokeResult(
            inputs=[
                InputResult(
                    input_path=Path("/tmp/test.mid"),
                    pipeline_path="midi",
                    checks=[
                        CheckResult(name="no_exceptions", passed=True),
                        CheckResult(name="valid_pdfs", passed=False, message="No PDFs"),
                    ],
                    elapsed_seconds=1.5,
                    error=None,
                ),
            ],
            total_passed=1,
            total_failed=1,
            total_errors=0,
            elapsed_seconds=1.5,
        )
        d = smoke_result_to_dict(result)
        json_str = json.dumps(d)
        # Round-trip: parse it back
        parsed = json.loads(json_str)
        assert parsed["total_passed"] == 1
        assert parsed["total_failed"] == 1
        assert len(parsed["inputs"]) == 1
        assert parsed["inputs"][0]["input_path"] == "/tmp/test.mid"

    def test_path_objects_converted_to_strings(self) -> None:
        """Path objects in the result are converted to strings for JSON."""
        result = SmokeResult(
            inputs=[
                InputResult(
                    input_path=Path("/some/path/file.wav"),
                    pipeline_path="audio",
                )
            ]
        )
        d = smoke_result_to_dict(result)
        assert isinstance(d["inputs"][0]["input_path"], str)
        assert d["inputs"][0]["input_path"] == "/some/path/file.wav"

    def test_empty_smoke_result(self) -> None:
        """Empty SmokeResult serializes correctly."""
        result = SmokeResult()
        d = smoke_result_to_dict(result)
        assert d["inputs"] == []
        assert d["total_passed"] == 0
        json_str = json.dumps(d)
        assert json.loads(json_str) is not None
