"""Source separation engine: hierarchical cascade with per-stem model routing.

Separates mixed audio into individual instrument stems using audio-separator.
The hierarchical cascade enables progressive refinement -- first split into
4 stems (drums/bass/vocals/other), then further separate the "other" stem
into piano/residual using dedicated models.

Memory-safe: one Separator instance at a time. Each step instantiates its own
Separator, processes, and lets GC reclaim before the next step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from audio_separator.separator import Separator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeparationStep:
    """One step in a hierarchical separation cascade.

    Attributes:
        model: Model filename for audio-separator (e.g. "htdemucs_ft.yaml").
        input_stem: Which stem to process. "mix" means the original audio file;
            any other value matches a stem name from a prior step's output.
        output_stems: Expected output stem names in the order the model produces them.
    """

    model: str
    input_stem: str
    output_stems: list[str]


@dataclass(frozen=True)
class StemOutput:
    """A single separated stem artifact.

    Attributes:
        stem_name: Standardized stem name (e.g. "drums", "bass", "vocals").
        path: Path to the output WAV file.
        model_used: Model filename that produced this stem.
        step_index: Index of the cascade step that produced this stem.
    """

    stem_name: str
    path: Path
    model_used: str
    step_index: int


def run_separation(
    audio_path: Path,
    steps: list[SeparationStep],
    output_dir: Path,
) -> list[StemOutput]:
    """Run a hierarchical separation cascade on the given audio file.

    For each step in the cascade:
    1. Determine input: "mix" uses the original audio; otherwise find the
       matching stem output from a prior step.
    2. Instantiate a fresh Separator (one at a time for memory safety).
    3. Load the model, run separation, map outputs to standardized names.
    4. Collect all StemOutput objects across all steps.

    Args:
        audio_path: Path to the input audio file.
        steps: Ordered list of SeparationStep defining the cascade.
        output_dir: Base directory for separation outputs.

    Returns:
        List of StemOutput objects for all stems across all steps.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        ValueError: If a step references a non-existent prior stem.
    """
    if not audio_path.exists():
        msg = f"Input audio file not found: {audio_path}"
        raise FileNotFoundError(msg)

    all_outputs: list[StemOutput] = []

    for step_index, step in enumerate(steps):
        # Determine input file for this step
        if step.input_stem == "mix":
            input_file = audio_path
        else:
            # Find matching output from a prior step
            prior = [o for o in all_outputs if o.stem_name == step.input_stem]
            if not prior:
                msg = (
                    f"Step {step_index} references stem '{step.input_stem}' "
                    f"but no prior step produced it. "
                    f"Available stems: {[o.stem_name for o in all_outputs]}"
                )
                raise ValueError(msg)
            input_file = prior[-1].path

        # Create step output subdirectory
        model_prefix = step.model.split(".")[0]
        step_subdir = output_dir / f"step-{step_index:02d}_{model_prefix}"
        step_subdir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Separation step %d: model=%s, input=%s, expected=%s",
            step_index,
            step.model,
            input_file.name,
            step.output_stems,
        )

        # Instantiate Separator per-step to avoid memory exhaustion.
        # Do NOT keep multiple Separator instances alive.
        separator = Separator(
            output_dir=str(step_subdir),
            output_format="WAV",
            sample_rate=44100,
        )
        separator.load_model(model_filename=step.model)
        output_files = separator.separate(str(input_file))

        # Map output files to standardized stem names
        step_outputs = _map_stem_names(
            output_files=output_files,
            expected_stems=step.output_stems,
            model=step.model,
            step_index=step_index,
        )
        all_outputs.extend(step_outputs)

        logger.info(
            "Step %d produced %d stems: %s",
            step_index,
            len(step_outputs),
            [o.stem_name for o in step_outputs],
        )

    return all_outputs


def _map_stem_names(
    output_files: list[str],
    expected_stems: list[str],
    model: str,
    step_index: int,
) -> list[StemOutput]:
    """Map audio-separator output filenames to standardized stem names.

    audio-separator naming varies by model architecture:
    - HTDemucs outputs: files containing "drums", "bass", "vocals", "other"
      (or "no_vocals" / "instrumental")
    - BS-RoFormer outputs: files containing "Vocals" / "Instrumental" or
      stem-specific names

    Uses case-insensitive substring matching to associate output files with
    expected_stems. Falls back to positional assignment if name matching fails.

    Args:
        output_files: List of output file paths from separator.separate().
        expected_stems: Expected stem names from the SeparationStep config.
        model: Model filename (for StemOutput metadata).
        step_index: Cascade step index (for StemOutput metadata).

    Returns:
        List of StemOutput with standardized stem names.
    """
    # Build a mapping from expected stem name -> output file path
    matched: dict[str, str] = {}
    unmatched_files = list(output_files)

    for stem_name in expected_stems:
        for filepath in unmatched_files:
            filename_lower = Path(filepath).stem.lower()
            if stem_name.lower() in filename_lower:
                matched[stem_name] = filepath
                unmatched_files.remove(filepath)
                break

    # If we matched all expected stems, use the matches
    if len(matched) == len(expected_stems):
        return [
            StemOutput(
                stem_name=stem_name,
                path=Path(matched[stem_name]),
                model_used=model,
                step_index=step_index,
            )
            for stem_name in expected_stems
        ]

    # Fallback: positional assignment
    logger.warning(
        "Name matching incomplete for step %d (matched %d/%d). "
        "Falling back to positional assignment.",
        step_index,
        len(matched),
        len(expected_stems),
    )
    results: list[StemOutput] = []
    for i, stem_name in enumerate(expected_stems):
        if i < len(output_files):
            results.append(
                StemOutput(
                    stem_name=stem_name,
                    path=Path(output_files[i]),
                    model_used=model,
                    step_index=step_index,
                )
            )
    return results


def get_default_steps() -> list[SeparationStep]:
    """Return the big band default separation cascade.

    1. HTDemucs ft: split mix into drums, bass, vocals, other
    2. BS-RoFormer: split "other" into piano, residual

    These defaults are overridable via engrave.toml.
    """
    return [
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
