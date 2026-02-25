"""Integration tests for the minimal Engrave web UI.

Uses ``httpx.AsyncClient`` with ``ASGITransport`` for async testing
of the FastAPI app endpoints: index page, file upload, status polling,
download, and error states.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from engrave.web.app import JobStatus, create_app, jobs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a fresh FastAPI app and clear the global jobs dict."""
    jobs.clear()
    return create_app()


@pytest.fixture()
async def client(app):
    """Provide an async httpx client bound to the ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _minimal_midi_bytes() -> bytes:
    """Return minimal valid MIDI file bytes (type 0, 0 tracks header + empty track).

    This is the smallest valid Standard MIDI File: header chunk + one track
    chunk with just an end-of-track event.
    """
    # MThd: header chunk
    header = (
        b"MThd"  # chunk id
        b"\x00\x00\x00\x06"  # chunk size = 6
        b"\x00\x00"  # format 0
        b"\x00\x01"  # 1 track
        b"\x00\x60"  # 96 ticks per quarter note
    )
    # MTrk: single track with end-of-track meta event
    track_data = b"\x00\xff\x2f\x00"  # delta=0, meta FF 2F 00
    track = b"MTrk" + len(track_data).to_bytes(4, "big") + track_data
    return header + track


def _create_test_zip(tmp_path: Path) -> Path:
    """Create a minimal test ZIP file and return its path."""
    zip_path = tmp_path / "test_output.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("score.pdf", b"fake pdf content")
        zf.writestr("score.ly", '\\version "2.24.4"\n{ c\' }')
    return zip_path


# ---------------------------------------------------------------------------
# Test 1: Index page
# ---------------------------------------------------------------------------


async def test_index_page(client: httpx.AsyncClient) -> None:
    """GET / returns 200 with HTML containing Engrave title and file upload form."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "<title>Engrave</title>" in html
    assert 'type="file"' in html
    assert 'name="file"' in html
    assert "hx-post" in html
    assert "htmx.org" in html


# ---------------------------------------------------------------------------
# Test 2: Upload returns job ID (with mocked pipeline)
# ---------------------------------------------------------------------------


async def test_upload_returns_job_id(client: httpx.AsyncClient, monkeypatch) -> None:
    """POST /engrave with a MIDI file returns HTML with hx-get status URL."""

    # Mock the pipeline to avoid real LLM calls.
    async def _mock_run_pipeline(job_id, input_path, hints, job_dir):
        jobs[job_id]["status"] = JobStatus.COMPLETE
        jobs[job_id]["zip_path"] = str(job_dir / "output.zip")

    import engrave.web.app as web_module

    monkeypatch.setattr(web_module, "_run_pipeline", _mock_run_pipeline)

    midi_data = _minimal_midi_bytes()
    files = {"file": ("test.mid", io.BytesIO(midi_data), "audio/midi")}
    resp = await client.post("/engrave", files=files, data={"hints": "swing feel"})

    assert resp.status_code == 200
    html = resp.text
    assert 'hx-get="/status/' in html
    assert "Processing..." in html

    # Verify job was created.
    assert len(jobs) == 1
    job_id = next(iter(jobs))
    assert jobs[job_id]["hints"] == "swing feel"


# ---------------------------------------------------------------------------
# Test 3: Status while processing
# ---------------------------------------------------------------------------


async def test_status_processing(client: httpx.AsyncClient) -> None:
    """GET /status/{id} for a PROCESSING job returns polling HTML."""
    import time

    job_id = "testproc"
    jobs[job_id] = {
        "status": JobStatus.PROCESSING,
        "input_path": Path("/tmp/test.mid"),
        "hints": "",
        "zip_path": None,
        "error": None,
        "start_time": time.monotonic() - 135,  # 2m 15s ago
    }

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "Processing..." in html
    assert "hx-trigger" in html
    assert "every 3s" in html
    # Elapsed time should show minutes.
    assert "2m" in html


# ---------------------------------------------------------------------------
# Test 4: Status when complete
# ---------------------------------------------------------------------------


async def test_status_complete(client: httpx.AsyncClient, tmp_path: Path) -> None:
    """GET /status/{id} for a COMPLETE job returns 286 with download link."""
    import time

    zip_path = _create_test_zip(tmp_path)
    job_id = "testdone"
    jobs[job_id] = {
        "status": JobStatus.COMPLETE,
        "input_path": Path("/tmp/test.mid"),
        "hints": "",
        "zip_path": str(zip_path),
        "error": None,
        "start_time": time.monotonic(),
    }

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 286
    html = resp.text
    assert "Complete!" in html
    assert f"/download/{job_id}" in html


# ---------------------------------------------------------------------------
# Test 5: Status when failed
# ---------------------------------------------------------------------------


async def test_status_failed(client: httpx.AsyncClient) -> None:
    """GET /status/{id} for a FAILED job returns 286 with error message."""
    import time

    job_id = "testfail"
    jobs[job_id] = {
        "status": JobStatus.FAILED,
        "input_path": Path("/tmp/test.mid"),
        "hints": "",
        "zip_path": None,
        "error": "Generation failed at section 1/3",
        "start_time": time.monotonic(),
    }

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 286
    html = resp.text
    assert "Generation failed at section 1/3" in html


# ---------------------------------------------------------------------------
# Test 6: Download ZIP
# ---------------------------------------------------------------------------


async def test_download_zip(client: httpx.AsyncClient, tmp_path: Path) -> None:
    """GET /download/{id} for a COMPLETE job returns the ZIP file."""
    import time

    zip_path = _create_test_zip(tmp_path)
    job_id = "testdl"
    jobs[job_id] = {
        "status": JobStatus.COMPLETE,
        "input_path": Path("/tmp/test.mid"),
        "hints": "",
        "zip_path": str(zip_path),
        "error": None,
        "start_time": time.monotonic(),
    }

    resp = await client.get(f"/download/{job_id}")
    assert resp.status_code == 200
    # Verify it is a ZIP file by checking magic bytes.
    assert resp.content[:2] == b"PK"
    # Verify filename in content-disposition header.
    assert "test_output.zip" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# Test 7: Status not found
# ---------------------------------------------------------------------------


async def test_status_not_found(client: httpx.AsyncClient) -> None:
    """GET /status/nonexistent returns 404."""
    resp = await client.get("/status/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 8: Download not found
# ---------------------------------------------------------------------------


async def test_download_not_found(client: httpx.AsyncClient) -> None:
    """GET /download/nonexistent returns 404."""
    resp = await client.get("/download/nonexistent")
    assert resp.status_code == 404
