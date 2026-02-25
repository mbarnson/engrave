"""Rendering package -- ensemble presets, LilyPond file generation, and output packaging."""

from engrave.rendering.articulation import (
    apply_articulation_defaults,
    apply_section_consistency,
)
from engrave.rendering.ensemble import (
    BIG_BAND,
    BigBandPreset,
    InstrumentSpec,
    StaffGroupType,
)
from engrave.rendering.generator import (
    generate_conductor_score,
    generate_music_definitions,
    generate_part,
    restate_dynamics,
)
from engrave.rendering.packager import RenderPipeline, RenderResult
from engrave.rendering.stylesheet import (
    CONDUCTOR_SCORE_HEADER,
    CONDUCTOR_SCORE_LAYOUT,
    CONDUCTOR_SCORE_PAPER,
    CONDUCTOR_STAFF_SIZE,
    LILYPOND_VERSION,
    PART_HEADER,
    PART_LAYOUT,
    PART_PAPER,
    PART_STAFF_SIZE,
    STUDIO_LAYOUT,
    VERSION_HEADER,
)

__all__ = [
    "BIG_BAND",
    "CONDUCTOR_SCORE_HEADER",
    "CONDUCTOR_SCORE_LAYOUT",
    "CONDUCTOR_SCORE_PAPER",
    "CONDUCTOR_STAFF_SIZE",
    "LILYPOND_VERSION",
    "PART_HEADER",
    "PART_LAYOUT",
    "PART_PAPER",
    "PART_STAFF_SIZE",
    "STUDIO_LAYOUT",
    "VERSION_HEADER",
    "BigBandPreset",
    "InstrumentSpec",
    "RenderPipeline",
    "RenderResult",
    "StaffGroupType",
    "apply_articulation_defaults",
    "apply_section_consistency",
    "generate_conductor_score",
    "generate_music_definitions",
    "generate_part",
    "restate_dynamics",
]
