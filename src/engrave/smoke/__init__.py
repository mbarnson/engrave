"""Automated smoke test harness for the Engrave pipeline.

Discovers audio and MIDI test inputs by file extension, runs them through
the appropriate pipeline path (audio-in or MIDI-only), performs 9 structural
checks on the output, and reports results as human-readable terminal output
plus structured JSON.

Public API
----------
- ``run_smoke_test`` -- orchestrate a full smoke test run
- ``SmokeResult`` -- aggregate result of a smoke test run
- ``InputResult`` -- result for a single test input file
- ``CheckResult`` -- result of a single check on pipeline output
"""

from engrave.smoke.runner import CheckResult, InputResult, SmokeResult, run_smoke_test

__all__ = [
    "CheckResult",
    "InputResult",
    "SmokeResult",
    "run_smoke_test",
]
