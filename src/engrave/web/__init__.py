"""Minimal web UI for UAT testing.

Provides a single-page FastAPI app with file upload, polling status,
and ZIP download for the full Engrave pipeline.

Public API
----------
- ``create_app`` -- factory function returning a configured FastAPI instance
"""

from engrave.web.app import create_app

__all__ = ["create_app"]
