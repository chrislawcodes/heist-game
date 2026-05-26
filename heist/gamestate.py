"""Process-wide in-memory game store, guarded by a lock.

The HTTP handler and the orchestration threads both read/write through this module.
"""
from __future__ import annotations

import queue
import threading

from heist.logs import log
from heist.persist import save_game_record

# ── shared state ──────────────────────────────────────────────────────────────

lock = threading.Lock()
event_history: list[dict] = []
subscribers: set[queue.Queue] = set()

# All games: staged, running, done, error
# {id, created_at, status, ais:[{prompt,agent}], job, take, aborted, escape_success}
games: dict[int, dict] = {}


class _Runtime:
    game_running: bool = False
    next_id: int = 1

    def __init__(self) -> None:
        # Campaign ids with a live conductor thread in THIS process. Used to
        # guard campaign resume against spawning a second conductor.
        self.active_campaigns: set[int] = set()


runtime = _Runtime()


def broadcast(event: dict) -> None:
    persist_game: dict | None = None
    with lock:
        event_history.append(event)
        # Mirror into the relevant game's persistent event log so we can replay
        # it later via /api/games/{id}/events. Route by game_id when present.
        # Campaign-conductor events (campaign_stage / campaign_round_done /
        # campaign_done) carry only a campaign_id and no game_id — file those
        # into the campaign's own log, never into a heist sub-game's stream
        # (which would corrupt that sub-game's step-by-step replay). Only events
        # with neither id fall back to the most-recently-running game.
        target_gid = None
        stamped_gid = event.get("game_id")
        campaign_gid = event.get("campaign_id")
        if stamped_gid is not None and stamped_gid in games:
            target_gid = stamped_gid
        elif campaign_gid is not None and campaign_gid in games:
            target_gid = campaign_gid
        else:
            for gid in reversed(list(games.keys())):
                if games[gid].get("status") in ("running", "done"):
                    target_gid = gid
                    break
        if target_gid is not None:
            games[target_gid].setdefault("events", []).append(event)
            # Snapshot the dict inside the lock; persist outside it so we
            # don't hold the lock during file I/O.
            persist_game = dict(games[target_gid])
        subs = list(subscribers)
    log.info("broadcast", payload=event)
    if persist_game is not None:
        try:
            save_game_record(persist_game)
        except Exception as exc:
            log.warn("save_game_record_failed", error=str(exc))
    for q in subs:
        q.put(event)


def get_game(game_id: int) -> dict | None:
    with lock:
        return games.get(game_id)


def update_game(game_id: int, **fields) -> None:
    persist_game: dict | None = None
    with lock:
        if game_id in games:
            games[game_id].update(fields)
            persist_game = dict(games[game_id])
    if persist_game is not None:
        try:
            save_game_record(persist_game)
        except Exception as exc:
            log.warn("save_game_record_failed", error=str(exc))
