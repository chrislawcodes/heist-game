from __future__ import annotations

import io
import json
import time
from types import SimpleNamespace

import pytest

import heist.persist as persist_mod
from heist import gamestate, orchestration
from heist import server as server_mod
from heist.content import JOBS, ROSTER
from heist.serialize import crew_to_dict
from heist.state import Crew, HeistState, HiddenDepthRoll

REAL_RUN_CAMPAIGN_CONDUCTOR = orchestration.run_campaign_conductor


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


def _wait_for(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("timed out waiting for background campaign to finish")


def test_setup_route_serves_new_campaign_html(fake_handler):
    status, body = _request_text(fake_handler, "GET", "/setup")
    assert status == 200
    assert "HEIST / New Campaign" in body
    assert "Launch Campaign" in body
    assert "Build a crew" in body


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
        "standing_crew": [],
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


def test_get_games_includes_campaign_sub_with_hidden_flag(fake_handler, monkeypatch):
    with gamestate.lock:
        gamestate.games[999] = {
            "id": 999,
            "created_at": 0.0,
            "status": "running",
            "is_campaign_sub": True,
            "campaign_id": 1,
            "parent_campaign_id": 1,
            "hidden_from_lobby": True,
            "ai_idx": 0,
            "events": [],
        }

    monkeypatch.setattr(persist_mod, "load_game_records", lambda: {})

    status, data = _request_json(fake_handler, "GET", "/api/games")
    assert status == 200
    games = {g["id"]: g for g in data}
    assert 999 in games
    assert games[999]["hidden_from_lobby"] is True
    assert games[999]["parent_campaign_id"] == 1


def test_campaign_round_heist_emits_crew_known_and_links_metadata(fake_handler, monkeypatch):
    def fake_run_auction(ais, strategies, logs_per_ai, emit_tagged, emit_and_save, **kwargs):
        crew = Crew(list(ROSTER[:4]))
        emit_and_save({
            "type": "auction_round_resolved",
            "crews_after": {str(i): [m.id for m in crew.members] for i in range(len(ais))},
        })
        return SimpleNamespace(
            crews={i: crew for i in range(len(ais))},
            bankrolls_spent={i: 0 for i in range(len(ais))},
        )

    def fake_run_one_job(strategy, ai, campaign, *, rng, emit=None, snapshot_fn=None,
                         board=None, assigned_job=None, slate_scores=None,
                         scout_state=None):
        job = assigned_job or JOBS[0]
        if emit is not None:
            emit({"type": "turn_start", "label": "job_pick", "prompt": "pick"})
            emit({"type": "job_known", "job": {"name": job.name}})
            emit({
                "type": "turn_end",
                "label": "job_pick",
                "seconds": 0.0,
                "response": "{}",
                "parsed": {"job_name": job.name},
            })
        state = HeistState(
            crew=Crew(list(campaign.standing_crew)),
            job=job,
            hidden_depth=HiddenDepthRoll(
                element=job.hidden_depth[0],
                reward_label="smoke",
                reward_amount=1234,
            ),
        )
        state.final_take = 1234
        state.escape_success = True
        state.secured_take = 1234
        state.heat = 0
        return state, {"epilogue": "done"}

    monkeypatch.setattr(orchestration, "run_campaign_conductor", REAL_RUN_CAMPAIGN_CONDUCTOR)
    monkeypatch.setattr("heist.auction.run_auction", fake_run_auction)
    monkeypatch.setattr("heist.runner.run_one_job", fake_run_one_job)
    monkeypatch.setattr("heist.campaign._opening_wire_call", lambda *args, **kwargs: None)
    monkeypatch.setattr("heist.campaign._reflection_call", lambda *args, **kwargs: None)

    status, data = _request_json(
        fake_handler,
        "POST",
        "/api/new-campaign",
        {
            "num_rounds": 1,
            "ais": [
                {"name": "Aegis", "prompt": "Play aggressively.", "agent": "stub"},
            ],
        },
    )
    assert status == 200
    campaign_id = data["campaign_id"]

    _wait_for(lambda: gamestate.get_game(campaign_id).get("status") == "done")

    with gamestate.lock:
        campaign = gamestate.games[campaign_id]
        game_state = campaign["game_states"][0]
        heist_id = game_state["round_game_ids"][0]
        hire_id = game_state["hiring_game_ids"][0]
        heist_game = gamestate.games[heist_id]
        hire_game = gamestate.games[hire_id]

    assert heist_game["parent_campaign_id"] == campaign_id
    assert heist_game["hidden_from_lobby"] is True
    assert heist_game["campaign_id"] == campaign_id
    assert heist_game["round_idx"] == 0
    assert heist_game["ai_idx"] == 0
    assert heist_game["ai_name"] == "Aegis"
    assert heist_game["hire_sub_game_id"] == hire_id
    assert heist_game["heist_sub_game_id"] == heist_id

    crew_events = [evt for evt in heist_game["events"] if evt["type"] == "crew_known"]
    assert crew_events, "expected crew_known at the start of the round heist sub-game"
    assert crew_events[0]["crew"] == crew_to_dict(Crew(list(ROSTER[:4])))

    assert hire_game["parent_campaign_id"] == campaign_id
    assert hire_game["hidden_from_lobby"] is True
    assert hire_game["campaign_id"] == campaign_id
    assert hire_game["round_idx"] == 0
    assert hire_game["hire_sub_game_id"] == hire_id
    assert hire_game["heist_sub_game_id"] == heist_id
    assert heist_id in hire_game["heist_sub_game_ids"]

    status, games = _request_json(fake_handler, "GET", "/api/games")
    assert status == 200
    indexed = {g["id"]: g for g in games}
    assert heist_id in indexed
    assert hire_id in indexed
    assert indexed[heist_id]["hidden_from_lobby"] is True
    assert indexed[heist_id]["parent_campaign_id"] == campaign_id
    assert "events" not in indexed[heist_id]
    assert "events" not in indexed[hire_id]


def test_campaign_journey_endpoint_returns_round_links_and_team_names(fake_handler, monkeypatch):
    def fake_run_auction(ais, strategies, logs_per_ai, emit_tagged, emit_and_save, **kwargs):
        crews = {
            0: Crew(list(ROSTER[:4])),
            1: Crew(list(ROSTER[4:8])),
        }
        emit_and_save({
            "type": "auction_round_resolved",
            "crews_after": {
                str(i): [m.id for m in crew.members]
                for i, crew in crews.items()
            },
        })
        return SimpleNamespace(
            crews=crews,
            bankrolls_spent={0: 0, 1: 0},
        )

    def fake_run_one_job(strategy, ai, campaign, *, rng, emit=None, snapshot_fn=None,
                         board=None, assigned_job=None, slate_scores=None,
                         scout_state=None):
        job = assigned_job or JOBS[0]
        if emit is not None:
            emit({"type": "turn_start", "label": "job_pick", "prompt": "pick"})
            emit({"type": "job_known", "job": {"name": job.name}})
            emit({
                "type": "turn_end",
                "label": "job_pick",
                "seconds": 0.0,
                "response": "{}",
                "parsed": {"job_name": job.name},
            })
        state = HeistState(
            crew=Crew(list(campaign.standing_crew)),
            job=job,
            hidden_depth=HiddenDepthRoll(
                element=job.hidden_depth[0],
                reward_label="smoke",
                reward_amount=2222,
            ),
        )
        state.final_take = 2222
        state.escape_success = True
        state.secured_take = 2222
        state.heat = 0
        return state, {"epilogue": "done"}

    monkeypatch.setattr(orchestration, "run_campaign_conductor", REAL_RUN_CAMPAIGN_CONDUCTOR)
    monkeypatch.setattr("heist.auction.run_auction", fake_run_auction)
    monkeypatch.setattr("heist.runner.run_one_job", fake_run_one_job)
    monkeypatch.setattr("heist.campaign._opening_wire_call", lambda *args, **kwargs: None)
    monkeypatch.setattr("heist.campaign._reflection_call", lambda *args, **kwargs: None)

    status, data = _request_json(
        fake_handler,
        "POST",
        "/api/new-campaign",
        {
            "num_rounds": 1,
            "ais": [
                {"name": "Aegis", "prompt": "Play aggressively.", "agent": "stub"},
                {"name": "Ghost", "prompt": "Play conservatively.", "agent": "stub"},
            ],
        },
    )
    assert status == 200
    campaign_id = data["campaign_id"]

    _wait_for(lambda: gamestate.get_game(campaign_id).get("status") == "done")

    status, journey = _request_json(
        fake_handler, "GET", f"/api/campaign-journey/{campaign_id}"
    )
    assert status == 200
    assert journey["campaign_id"] == campaign_id
    assert journey["num_rounds"] == 1
    assert len(journey["teams"]) == 2
    assert [team["team_name"] for team in journey["teams"]] == ["Aegis", "Ghost"]

    round0_hire_ids = {team["rounds"][0]["hire_sub_game_id"] for team in journey["teams"]}
    round0_heist_ids = {team["rounds"][0]["heist_sub_game_id"] for team in journey["teams"]}
    assert len(round0_hire_ids) == 1
    assert len(round0_heist_ids) == 2

    for team in journey["teams"]:
        assert team["rounds"][0]["round_idx"] == 0
        assert team["rounds"][0]["hire_sub_game_id"] in round0_hire_ids
        assert team["rounds"][0]["heist_sub_game_id"] in round0_heist_ids
        assert team["rounds"][0]["outcome"] == {
            "take": 2222,
            "escape_success": True,
            "aborted": False,
        }
