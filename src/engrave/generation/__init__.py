"""LilyPond generation infrastructure: coherence, templates, prompts, failure logging.

Public API::

    from engrave.generation import CoherenceState
    from engrave.generation import build_score_template, build_instrument_variable
    from engrave.generation import parse_instrument_blocks
    from engrave.generation import build_section_prompt, PromptBudget
    from engrave.generation import FailureRecord, log_failure, load_failure_log
"""

from engrave.generation.coherence import CoherenceState
from engrave.generation.failure_log import FailureRecord, load_failure_log, log_failure
from engrave.generation.prompts import PromptBudget, build_section_prompt
from engrave.generation.templates import (
    build_instrument_variable,
    build_score_template,
    parse_instrument_blocks,
)

__all__ = [
    "CoherenceState",
    "FailureRecord",
    "PromptBudget",
    "build_instrument_variable",
    "build_score_template",
    "build_section_prompt",
    "load_failure_log",
    "log_failure",
    "parse_instrument_blocks",
]
