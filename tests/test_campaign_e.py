from __future__ import annotations

import io
import json

import pytest

import heist.persist as persist_mod
from heist import gamestate, orchestration, server as server_mod


@pytest.fixture()
def fake_handler(monkeypatch, tmp_path):
    monkeypatch.setenv("HEIST_STATE_DIR", str(tmp_path / "state"))

    with gamestate.lock:
        gamestate.games.clear()
        gamestate.event_history.clear()
        gamestate.subscribers.clear()
        gamestate.runtime.game_running = False
        gamestate.runtime.next_id = 1

    def noop_campaign_conductor(*args, **kwargs):
        return None

    monkeypatch.setattr(orchestration, "run_campaign_conductor", noop_campaign_conductor)

    class FakeHandler(server_mod._Handler):
        def __init__(self, path: str, body: bytes = b""):
            self.path = path
            self.rfile = io.BytesIO(body)
            self.wfile = io.BytesIO()
            self.headers = {"Content-Length": str(len(body))}
            self._status_code = None
            self.sent_headers: list[tuple[str, str]] = []

        def send_response(self, code, message=None):
            self._status_code = code

        def send_header(self, key, value):
            self.sent_headers.append((key, value))

        def end_headers(self):
            pass

    return FakeHandler


def _request_json(handler_cls, method: str, path: str, body: dict | None = None):
    payload = b"" if body is None else json.dumps(body).encode()
    handler = handler_cls(path, payload)
    getattr(handler, f"do_{method}")()
    raw = handler.wfile.getvalue()
    data = json.loads(raw.decode() or "{}") if raw else {}
    return handler._status_code, data


def _request_text(handler_cls, method: str, path: str):
    handler = handler_cls(path)
    getattr(handler, f"do_{method}")()
    return handler._status_code, handler.wfile.getvalue().decode()


def test_setup_route_serves_new_campaign_html(fake_handler):
    status, body = _request_text(fake_handler, "GET", "/setup")
    assert status == 200
    assert "HEIST / New Campaign" in body
    assert "Launch Campaign ->" in body


def test_new_campaign_creates_campaign_record(fake_handler):
    payload = {
        "num_rounds": 7,
        "ais": [
            {"name": "Aegis", "prompt": "Play aggressively.", "agent": "codex"},
            {"prompt": "Play conservatively."},
        ],
    }
    status, data = _request_json(fake_handler, "POST", "/api/new-campaign", payload)
    assert status == 200
    assert "campaign_id" in data

    with gamestate.lock:
        campaign = gamestate.games[data["campaign_id"]]
    assert campaign["is_campaign"] is True
    assert campaign["num_rounds"] == 7
    assert campaign["ais_remaining"] == 2
    assert campaign["campaign_state"] == {
        "rounds_total": 7,
        "banked_loot": 0,
        "bankroll": 0,
        "notoriety": 0,
        "standing_crew": [],
        "attempted_job_names": [],
        "round_results": [],
        "between_round_log": [],
    }
    assert len(campaign["game_states"]) == 2
    assert campaign["game_states"][0] == {
        "ai_idx": 0,
        "ai_name": "Aegis",
        "ai_game_id": None,
        "status": "waiting",
        "banked_loot": 0,
        "notoriety": 0,
        "standing_crew": [],
        "round_results": [],
    }
    assert campaign["game_states"][1]["ai_name"] == "AI 2"


def test_campaigns_only_returns_campaign_records_and_current_round(fake_handler):
    status, data = _request_json(
        fake_handler,
        "POST",
        "/api/new-campaign",
        {
            "num_rounds": 5,
            "ais": [
                {"name": "Aegis", "prompt": "Play aggressively."},
                {"name": "Phantom", "prompt": "Play conservatively."},
            ],
        },
    )
    assert status == 200
    campaign_id = data["campaign_id"]

    with gamestate.lock:
        gamestate.games[999] = {
            "id": 999,
            "created_at": 0.0,
            "status": "done",
            "is_campaign": False,
            "ais": [],
        }
        gamestate.games[998] = {
            "id": 998,
            "created_at": 0.0,
            "status": "running",
            "is_campaign_sub": True,
            "campaign_id": campaign_id,
            "ai_idx": 0,
            "events": [],
        }

        gamestate.games[campaign_id]["game_states"][0]["round_results"] = [{"round_idx": 0}]
        gamestate.games[campaign_id]["game_states"][1]["round_results"] = [
            {"round_idx": 0},
            {"round_idx": 1},
            {"round_idx": 2},
        ]

    status, campaigns = _request_json(fake_handler, "GET", "/api/campaigns")
    assert status == 200
    assert [row["id"] for row in campaigns] == [campaign_id]
    assert campaigns[0]["current_round"] == 3
    assert campaigns[0]["ais"] == [
        {"ai_idx": 0, "ai_name": "Aegis", "banked": 0, "status": "waiting"},
        {"ai_idx": 1, "ai_name": "Phantom", "banked": 0, "status": "waiting"},
    ]


def test_invalid_num_rounds_returns_400(fake_handler):
    status, data = _request_json(
        fake_handler,
        "POST",
        "/api/new-campaign",
        {
            "num_rounds": 0,
            "ais": [{"prompt": "Play aggressively."}],
        },
    )
    assert status == 400
    assert "error" in data


def test_invalid_ais_empty_list_returns_400(fake_handler):
    status, data = _request_json(
        fake_handler,
        "POST",
        "/api/new-campaign",
        {
            "num_rounds": 5,
            "ais": [],
        },
    )
    assert status == 400
    assert "error" in data


def test_get_games_excludes_campaign_sub(fake_handler, monkeypatch):
    """Sub-games created for per-AI campaign viewers should not appear in
    the GET /api/games listing."""
    with gamestate.lock:
        gamestate.games[999] = {
            "id": 999,
            "created_at": 0.0,
            "status": "running",
            "is_campaign_sub": True,
            "campaign_id": 1,
            "ai_idx": 0,
            "events": [],
        }

    monkeypatch.setattr(persist_mod, "load_game_records", lambda: {})

    status, data = _request_json(fake_handler, "GET", "/api/games")
    assert status == 200
    ids = [g["id"] for g in data]
    assert 999 not in ids
