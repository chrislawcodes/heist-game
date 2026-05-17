"""Server tests: smoke-check the FastAPI app boots, serves the index page,
exposes the default-prompt endpoint, and streams a heist end-to-end through
the stub backend (so this stays CI-friendly — no real model calls)."""

import json

import pytest
from fastapi.testclient import TestClient

from heist.server import build_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


def test_index_page_served(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "Heist Game" in body
    assert "<textarea" in body
    assert "Run heist" in body


def test_default_prompt_endpoint(client: TestClient):
    resp = client.get("/api/default-prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert "prompt" in data
    assert "professional" in data["prompt"].lower()


def test_heist_stream_with_stub(client: TestClient):
    resp = client.post(
        "/api/heist",
        json={"prompt": "test", "agent": "stub", "seed": 7},
    )
    assert resp.status_code == 200
    # NDJSON: one event per line
    events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert types[0] == "started"
    assert "scene" in types
    assert types[-1] == "done"
    # The done event carries the outcome + timing
    done = events[-1]
    assert "outcome" in done and "timing" in done
    assert done["outcome"]["job_name"]  # nonempty
    assert done["timing"]["rounds"]  # at least one round logged


def test_heist_stream_rejects_unknown_agent(client: TestClient):
    resp = client.post(
        "/api/heist",
        json={"prompt": "test", "agent": "bogus"},
    )
    # The stream starts then errors out
    events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    # First event is started, then an error event from the worker
    error_events = [e for e in events if e["type"] == "error"]
    assert error_events, f"expected an error event, got {events}"
    assert "unknown agent" in error_events[0]["message"].lower()
