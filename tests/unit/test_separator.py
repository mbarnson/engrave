"""Tests for source separation cascade logic with mocked audio-separator.

All tests mock audio_separator.separator.Separator entirely -- the real
library is never imported or used in tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engrave.audio.separator import (
    SeparationStep,
    StemOutput,
    _map_stem_names,
    get_default_steps,
    run_separation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_audio(tmp_path: Path) -> Path:
    """Create a fake WAV file for testing (empty -- Separator is mocked)."""
    wav = tmp_path / "song.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 100)
    return wav


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create an output directory for separation results."""
    d = tmp_path / "separation_output"
    d.mkdir()
    return d


def _make_mock_separator(step_subdir: Path, stem_names: list[str]) -> MagicMock:
    """Create a mock Separator that writes fake output files and returns their paths.

    The mock creates empty files in step_subdir with names matching stem_names,
    simulating audio-separator's file output convention.
    """
    mock_sep = MagicMock()

    def fake_separate(input_path: str) -> list[str]:
        output_files = []
        for stem in stem_names:
            out_file = step_subdir / f"song_(_{stem}).wav"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(b"fake")
            output_files.append(str(out_file))
        return output_files

    mock_sep.separate.side_effect = fake_separate
    return mock_sep


# ---------------------------------------------------------------------------
# run_separation: single step
# ---------------------------------------------------------------------------


class TestRunSeparationSingleStep:
    """Test run_separation() with a single 4-stem separation step."""

    def test_single_step_four_stems(self, fake_audio: Path, output_dir: Path) -> None:
        """Single step produces 4 StemOutput objects with correct attributes."""
        steps = [
            SeparationStep(
                model="htdemucs_ft.yaml",
                input_stem="mix",
                output_stems=["drums", "bass", "vocals", "other"],
            )
        ]
        step_subdir = output_dir / "step-00_htdemucs_ft"

        mock_sep = _make_mock_separator(step_subdir, ["drums", "bass", "vocals", "other"])

        with patch("engrave.audio.separator.Separator", return_value=mock_sep) as mock_cls:
            results = run_separation(fake_audio, steps, output_dir)

        # Separator instantiated with correct args
        mock_cls.assert_called_once_with(
            output_dir=str(step_subdir),
            output_format="WAV",
            sample_rate=44100,
        )
        # load_model called with correct model name
        mock_sep.load_model.assert_called_once_with(model_filename="htdemucs_ft.yaml")
        # separate called with correct input path
        mock_sep.separate.assert_called_once_with(str(fake_audio))

        # Outputs mapped correctly
        assert len(results) == 4
        stem_names = [r.stem_name for r in results]
        assert stem_names == ["drums", "bass", "vocals", "other"]
        for r in results:
            assert r.model_used == "htdemucs_ft.yaml"
            assert r.step_index == 0
            assert r.path.exists()

    def test_separator_instantiated_per_step(self, fake_audio: Path, output_dir: Path) -> None:
        """Each step gets its own Separator instance (memory safety)."""
        steps = [
            SeparationStep(
                model="model_a.yaml", input_stem="mix", output_stems=["vocals", "instrumental"]
            ),
            SeparationStep(
                model="model_b.ckpt", input_stem="vocals", output_stems=["clean", "reverb"]
            ),
        ]

        call_count = 0

        def make_sep(*args, **kwargs):
            nonlocal call_count
            step_idx = call_count
            call_count += 1
            if step_idx == 0:
                subdir = output_dir / "step-00_model_a"
                return _make_mock_separator(subdir, ["vocals", "instrumental"])
            else:
                subdir = output_dir / "step-01_model_b"
                return _make_mock_separator(subdir, ["clean", "reverb"])

        with patch("engrave.audio.separator.Separator", side_effect=make_sep) as mock_cls:
            results = run_separation(fake_audio, steps, output_dir)

        # Two separate Separator instances created
        assert mock_cls.call_count == 2
        assert len(results) == 4


# ---------------------------------------------------------------------------
# run_separation: two-step cascade
# ---------------------------------------------------------------------------


class TestRunSeparationCascade:
    """Test run_separation() with a two-step hierarchical cascade."""

    def test_second_step_uses_prior_output(self, fake_audio: Path, output_dir: Path) -> None:
        """Second step receives the output from the first step as its input."""
        steps = [
            SeparationStep(
                model="htdemucs_ft.yaml",
                input_stem="mix",
                output_stems=["drums", "bass", "vocals", "other"],
            ),
            SeparationStep(
                model="model_bs_roformer_ep_317_sdr_12.9755.ckpt",
                input_stem="other",
                output_stems=["piano", "residual"],
            ),
        ]

        call_count = 0
        captured_inputs: list[str] = []

        def make_sep(*args, **kwargs):
            nonlocal call_count
            step_idx = call_count
            call_count += 1

            mock_sep = MagicMock()

            if step_idx == 0:
                subdir = output_dir / "step-00_htdemucs_ft"

                def fake_sep_0(input_path: str) -> list[str]:
                    captured_inputs.append(input_path)
                    files = []
                    for stem in ["drums", "bass", "vocals", "other"]:
                        f = subdir / f"song_(_{stem}).wav"
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_bytes(b"fake")
                        files.append(str(f))
                    return files

                mock_sep.separate.side_effect = fake_sep_0
            else:
                subdir = output_dir / "step-01_model_bs_roformer_ep_317_sdr_12"

                def fake_sep_1(input_path: str) -> list[str]:
                    captured_inputs.append(input_path)
                    files = []
                    for stem in ["piano", "residual"]:
                        f = subdir / f"song_(_{stem}).wav"
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_bytes(b"fake")
                        files.append(str(f))
                    return files

                mock_sep.separate.side_effect = fake_sep_1

            return mock_sep

        with patch("engrave.audio.separator.Separator", side_effect=make_sep):
            results = run_separation(fake_audio, steps, output_dir)

        # First step uses original audio
        assert captured_inputs[0] == str(fake_audio)
        # Second step uses the "other" stem from step 0 -- NOT the original audio
        assert "other" in captured_inputs[1]
        assert captured_inputs[1] != str(fake_audio)

        # Total outputs: 4 from step 0 + 2 from step 1
        assert len(results) == 6
        stem_names = [r.stem_name for r in results]
        assert "drums" in stem_names
        assert "bass" in stem_names
        assert "vocals" in stem_names
        assert "other" in stem_names
        assert "piano" in stem_names
        assert "residual" in stem_names


# ---------------------------------------------------------------------------
# _map_stem_names
# ---------------------------------------------------------------------------


class TestMapStemNames:
    """Test _map_stem_names() with various model output naming conventions."""

    def test_htdemucs_style_output(self, tmp_path: Path) -> None:
        """HTDemucs-style output filenames (containing drums, bass, etc.) are matched."""
        output_files = [
            str(tmp_path / "song_(Drums).wav"),
            str(tmp_path / "song_(Bass).wav"),
            str(tmp_path / "song_(Vocals).wav"),
            str(tmp_path / "song_(Other).wav"),
        ]
        # Create the files
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["drums", "bass", "vocals", "other"],
            model="htdemucs_ft.yaml",
            step_index=0,
        )

        assert len(results) == 4
        assert results[0].stem_name == "drums"
        assert results[1].stem_name == "bass"
        assert results[2].stem_name == "vocals"
        assert results[3].stem_name == "other"
        for r in results:
            assert r.model_used == "htdemucs_ft.yaml"
            assert r.step_index == 0

    def test_roformer_style_output(self, tmp_path: Path) -> None:
        """RoFormer-style output filenames (Vocals/Instrumental) are matched."""
        output_files = [
            str(tmp_path / "song_(Vocals).wav"),
            str(tmp_path / "song_(Instrumental).wav"),
        ]
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["vocals", "instrumental"],
            model="model_bs_roformer.ckpt",
            step_index=1,
        )

        assert len(results) == 2
        assert results[0].stem_name == "vocals"
        assert results[1].stem_name == "instrumental"

    def test_case_insensitive_matching(self, tmp_path: Path) -> None:
        """Stem name matching is case-insensitive."""
        output_files = [
            str(tmp_path / "track_DRUMS_output.wav"),
            str(tmp_path / "track_bass_output.wav"),
        ]
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["drums", "bass"],
            model="test_model.yaml",
            step_index=0,
        )

        assert len(results) == 2
        assert results[0].stem_name == "drums"
        assert results[1].stem_name == "bass"

    def test_positional_fallback_when_names_dont_match(self, tmp_path: Path) -> None:
        """Falls back to positional assignment when filename matching fails."""
        # Files with cryptic names that don't match expected stems
        output_files = [
            str(tmp_path / "output_001.wav"),
            str(tmp_path / "output_002.wav"),
        ]
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["piano", "residual"],
            model="mystery_model.ckpt",
            step_index=2,
        )

        assert len(results) == 2
        assert results[0].stem_name == "piano"
        assert results[0].path == Path(output_files[0])
        assert results[1].stem_name == "residual"
        assert results[1].path == Path(output_files[1])

    def test_partial_match_triggers_fallback(self, tmp_path: Path) -> None:
        """If only some stems match by name, positional fallback is used."""
        output_files = [
            str(tmp_path / "song_drums.wav"),
            str(tmp_path / "output_unknown.wav"),
            str(tmp_path / "output_another.wav"),
        ]
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["drums", "bass", "vocals"],
            model="test.yaml",
            step_index=0,
        )

        # Only 1/3 matched by name -> fallback to positional
        assert len(results) == 3
        assert results[0].stem_name == "drums"
        assert results[1].stem_name == "bass"
        assert results[2].stem_name == "vocals"

    def test_fewer_outputs_than_expected_stems(self, tmp_path: Path) -> None:
        """When fewer output files exist than expected stems, only available are mapped."""
        output_files = [
            str(tmp_path / "output_001.wav"),
        ]
        for f in output_files:
            Path(f).write_bytes(b"fake")

        results = _map_stem_names(
            output_files=output_files,
            expected_stems=["piano", "residual"],
            model="test.ckpt",
            step_index=0,
        )

        # Positional fallback: only 1 file for 2 expected stems
        assert len(results) == 1
        assert results[0].stem_name == "piano"


# ---------------------------------------------------------------------------
# get_default_steps
# ---------------------------------------------------------------------------


class TestGetDefaultSteps:
    """Test get_default_steps() returns the expected cascade structure."""

    def test_returns_two_steps(self) -> None:
        """Default cascade has exactly two steps."""
        steps = get_default_steps()
        assert len(steps) == 2

    def test_first_step_is_htdemucs(self) -> None:
        """First step uses HTDemucs ft on the original mix."""
        steps = get_default_steps()
        step0 = steps[0]
        assert step0.model == "htdemucs_ft.yaml"
        assert step0.input_stem == "mix"
        assert step0.output_stems == ["drums", "bass", "vocals", "other"]

    def test_second_step_is_roformer_on_other(self) -> None:
        """Second step uses BS-RoFormer on the 'other' stem."""
        steps = get_default_steps()
        step1 = steps[1]
        assert step1.model == "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
        assert step1.input_stem == "other"
        assert step1.output_stems == ["piano", "residual"]

    def test_steps_are_frozen(self) -> None:
        """SeparationStep instances are frozen dataclasses (immutable)."""
        steps = get_default_steps()
        with pytest.raises(AttributeError):
            steps[0].model = "different.yaml"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling in run_separation()."""

    def test_missing_input_file_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when audio_path does not exist."""
        nonexistent = tmp_path / "does_not_exist.wav"
        steps = [
            SeparationStep(model="test.yaml", input_stem="mix", output_stems=["a"]),
        ]

        with pytest.raises(FileNotFoundError, match=r"does_not_exist\.wav"):
            run_separation(nonexistent, steps, tmp_path / "out")

    def test_missing_prior_stem_raises(self, fake_audio: Path, output_dir: Path) -> None:
        """ValueError raised when a step references a stem no prior step produced."""
        steps = [
            SeparationStep(
                model="htdemucs_ft.yaml",
                input_stem="mix",
                output_stems=["drums", "bass", "vocals", "other"],
            ),
            SeparationStep(
                model="test.ckpt",
                input_stem="guitar",  # No prior step produced "guitar"
                output_stems=["clean_guitar"],
            ),
        ]

        # Mock first step to produce the 4 standard stems
        mock_sep = _make_mock_separator(
            output_dir / "step-00_htdemucs_ft",
            ["drums", "bass", "vocals", "other"],
        )

        with (
            patch("engrave.audio.separator.Separator", return_value=mock_sep),
            pytest.raises(ValueError, match="guitar"),
        ):
            run_separation(fake_audio, steps, output_dir)

    def test_empty_steps_list_returns_empty(self, fake_audio: Path, output_dir: Path) -> None:
        """An empty steps list returns an empty results list."""
        results = run_separation(fake_audio, [], output_dir)
        assert results == []


# ---------------------------------------------------------------------------
# StemOutput dataclass
# ---------------------------------------------------------------------------


class TestStemOutput:
    """Test StemOutput frozen dataclass properties."""

    def test_frozen(self, tmp_path: Path) -> None:
        """StemOutput instances are immutable."""
        so = StemOutput(
            stem_name="vocals",
            path=tmp_path / "vocals.wav",
            model_used="test.yaml",
            step_index=0,
        )
        with pytest.raises(AttributeError):
            so.stem_name = "other"  # type: ignore[misc]

    def test_equality(self, tmp_path: Path) -> None:
        """Two StemOutput instances with the same values are equal."""
        path = tmp_path / "vocals.wav"
        a = StemOutput(stem_name="vocals", path=path, model_used="m.yaml", step_index=0)
        b = StemOutput(stem_name="vocals", path=path, model_used="m.yaml", step_index=0)
        assert a == b
