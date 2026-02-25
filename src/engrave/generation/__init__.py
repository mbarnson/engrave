"""LilyPond generation infrastructure: pipeline, coherence, templates, prompts, failure logging, audit.

Public API::

    from engrave.generation import generate_from_midi, GenerationResult, GenerationHaltError
    from engrave.generation import assemble_sections
    from engrave.generation import CoherenceState
    from engrave.generation import build_score_template, build_instrument_variable
    from engrave.generation import parse_instrument_blocks
    from engrave.generation import build_section_prompt, PromptBudget
    from engrave.generation import build_json_generation_suffix, extract_json_from_response
    from engrave.generation import FailureRecord, log_failure, load_failure_log
    from engrave.generation import AuditLog, AuditEntry, FieldResolution
"""

from engrave.generation.assembler import assemble_sections
from engrave.generation.audit import AuditEntry, AuditLog, FieldResolution
from engrave.generation.coherence import CoherenceState
from engrave.generation.failure_log import FailureRecord, load_failure_log, log_failure
from engrave.generation.pipeline import (
    GenerationHaltError,
    GenerationResult,
    generate_from_midi,
)
from engrave.generation.prompts import (
    PromptBudget,
    build_json_generation_suffix,
    build_section_prompt,
    extract_json_from_response,
)
from engrave.generation.templates import (
    build_instrument_variable,
    build_score_template,
    parse_instrument_blocks,
)

__all__ = [
    "AuditEntry",
    "AuditLog",
    "CoherenceState",
    "FailureRecord",
    "FieldResolution",
    "GenerationHaltError",
    "GenerationResult",
    "PromptBudget",
    "assemble_sections",
    "build_instrument_variable",
    "build_json_generation_suffix",
    "build_score_template",
    "build_section_prompt",
    "extract_json_from_response",
    "generate_from_midi",
    "load_failure_log",
    "log_failure",
    "parse_instrument_blocks",
]
