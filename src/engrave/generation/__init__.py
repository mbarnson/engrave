"""LilyPond generation infrastructure: coherence, templates, prompts, failure logging.

Public API::

    from engrave.generation import CoherenceState
    from engrave.generation import build_score_template, build_instrument_variable
    from engrave.generation import parse_instrument_blocks
    from engrave.generation import build_section_prompt, PromptBudget
    from engrave.generation import FailureRecord, log_failure, load_failure_log
"""

from engrave.generation.coherence import CoherenceState
from engrave.generation.templates import (
    build_instrument_variable,
    build_score_template,
    parse_instrument_blocks,
)

__all__ = [
    "CoherenceState",
    "build_instrument_variable",
    "build_score_template",
    "parse_instrument_blocks",
]
