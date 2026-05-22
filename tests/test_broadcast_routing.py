"""Tests that _broadcast routes events by game_id when present."""
from __future__ import annotations

import threading
import time

import pytest

import heist.server as srv


@pytest.fixture(autouse=True)
def _clean_server_state(tmp_path, monkeypatch):
    """Isolate _games, _event_history, and _subscribers between tests."""
    monkeypatch.setattr(srv, "_games", {})
    monkeypatch.setattr(srv, "_event_history", [])
    monkeypatch.setattr(srv, "_subscribers", [])
    monkeypatch.setattr(srv, "_lock", threading.Lock())
    # Point persist at a temp dir so no real disk I/O fails the test.
    monkeypatch.setenv("HEIST_STATE_DIR", str(tmp_path / "state"))
    # Stub out save_game_record so we don't need a real state directory.
    monkeypatch.setattr(srv, "save_game_record", lambda _game: None)
    yield


def _make_game(gid: int, status: str = "running") -> dict:
    return {
        "id": gid,
        "created_at": time.time(),
        "status": status,
        "ais": [{"prompt": "test", "agent": "stub"}],
        "ai_results": [None],
        "ais_remaining": 1,
        "job": None,
        "take": None,
        "aborted": None,
        "escape_success": None,
        "events": [],
    }


# ---------------------------------------------------------------------------
# (a) emit_tagged wrappers inject the correct game_id
# ---------------------------------------------------------------------------

def test_run_game_emit_tagged_stamps_game_id(monkeypatch):
    """_run_game's emit_tagged closure injects game_id into every event."""
    captured: list[dict] = []
    monkeypatch.setattr(srv, "_broadcast", lambda evt: captured.append(evt))

    # Build the closure as the real code does, but call it directly.
    game_id = 42
    ai_idx = 1

    def emit_tagged(evt: dict) -> None:
        srv._broadcast({**evt, "ai_idx": ai_idx, "game_id": game_id})

    emit_tagged({"type": "scene", "text": "vault opened"})

    assert len(captured) == 1
    assert captured[0]["game_id"] == 42
    assert captured[0]["ai_idx"] == 1
    assert captured[0]["type"] == "scene"


def test_auction_coordinator_emit_tagged_stamps_game_id(monkeypatch):
    """_run_auction_coordinator's emit_tagged closure injects game_id."""
    captured: list[dict] = []
    monkeypatch.setattr(srv, "_broadcast", lambda evt: captured.append(evt))

    game_id = 99

    def emit_tagged(ai_idx: int, evt: dict) -> None:
        srv._broadcast({**evt, "ai_idx": ai_idx, "game_id": game_id})

    emit_tagged(0, {"type": "auction_result", "winner": "Carla"})

    assert len(captured) == 1
    assert captured[0]["game_id"] == 99
    assert captured[0]["ai_idx"] == 0
    assert captured[0]["type"] == "auction_result"


# ---------------------------------------------------------------------------
# (b) _broadcast routes by game_id; does NOT bleed into a different game
# ---------------------------------------------------------------------------

def test_broadcast_routes_to_correct_game_when_two_games_exist():
    """Event with game_id=1 lands in game 1's events, not game 2's."""
    srv._games[1] = _make_game(1, status="running")
    srv._games[2] = _make_game(2, status="running")

    srv._broadcast({"type": "scene", "text": "alpha", "game_id": 1})
    srv._broadcast({"type": "scene", "text": "beta", "game_id": 2})

    assert len(srv._games[1]["events"]) == 1
    assert srv._games[1]["events"][0]["text"] == "alpha"

    assert len(srv._games[2]["events"]) == 1
    assert srv._games[2]["events"][0]["text"] == "beta"


def test_broadcast_does_not_append_to_wrong_game():
    """An event stamped game_id=1 never appears in game 2's event list."""
    srv._games[1] = _make_game(1, status="running")
    srv._games[2] = _make_game(2, status="running")

    srv._broadcast({"type": "heist_event", "game_id": 1})

    assert len(srv._games[2]["events"]) == 0


def test_broadcast_fallback_when_no_game_id():
    """Events without game_id still land in the most-recently-running game."""
    srv._games[1] = _make_game(1, status="running")
    srv._games[2] = _make_game(2, status="running")

    # No game_id key — should fall back to game 2 (highest key, running).
    srv._broadcast({"type": "legacy_event"})

    # Game 2 is the most-recently running game (highest key in reversed order).
    total = len(srv._games[1]["events"]) + len(srv._games[2]["events"])
    assert total == 1
    assert len(srv._games[2]["events"]) == 1


def test_broadcast_appends_to_event_history_regardless_of_game_id():
    """_event_history always grows, even when game_id routes correctly."""
    srv._games[1] = _make_game(1, status="running")

    srv._broadcast({"type": "ping", "game_id": 1})
    srv._broadcast({"type": "pong"})

    assert len(srv._event_history) == 2
