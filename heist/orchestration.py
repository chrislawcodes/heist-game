"""Game orchestration: auction coordinator, per-AI heist threads, startup recovery.

Spawns daemon threads; emits through gamestate.broadcast.
"""
from __future__ import annotations

import contextlib
import random
import threading
import time
import traceback

from heist import gamestate
from heist.ai import AgentTurn
from heist.content import ROSTER_BY_ID
from heist.logs import log
from heist.persist import (
    delete_runner_snapshot,
    list_pending_snapshots,
    load_game_records,
    save_game_record,
    save_runner_snapshot,
)


def _build_ai(agent: str, *, ai_idx: int = 0, auction_mode: bool = False):
    from heist.backends import CodexHeistAI, GeminiHeistAI
    from heist.stub_responses import build_stub_ai

    if agent == "stub":
        if not auction_mode:
            return build_stub_ai()
        return _AuctionAwareStubAI(ai_idx)
    if agent == "codex":
        return CodexHeistAI(model="gpt-5.4")
    if agent == "codex-mini":
        return CodexHeistAI(model="gpt-5.4-mini")
    if agent == "gemini":
        return GeminiHeistAI()
    raise RuntimeError(f"Unknown agent: {agent}")


class _AuctionAwareStubAI:
    """Stub AI that can handle both the legacy single-AI flow and the new
    auction bidding prompt used by the server smoke test."""

    _TARGET_SETS = [
        [2, 6, 8, 10],
        [9, 11, 12, 14],
        [3, 5, 8, 10],
        [4, 6, 8, 10],
    ]

    def __init__(self, ai_idx: int):
        from heist.stub_responses import build_stub_ai

        self._base = build_stub_ai()
        self._target_ids = self._TARGET_SETS[ai_idx % len(self._TARGET_SETS)]
        self.session_id = None

    @property
    def prompts_seen(self) -> list[str]:
        return self._base.prompts_seen

    def ask(self, prompt: str):
        if "round of crew bidding" not in prompt:
            return self._base.ask(prompt)

        import json
        import re

        available_ids = {
            int(m) for m in re.findall(r"id=(\d+)", prompt)
        }
        self._base._asked.append(prompt)
        bids = []
        for cid in self._target_ids:
            if cid not in available_ids:
                continue
            char = ROSTER_BY_ID[cid]
            bids.append({
                "character_id": cid,
                "bid": char.floor_cost,
                "rationale": f"Pre-planned smoke-test target {char.name}.",
            })
        payload = {
            "bids": bids,
            "pass": not bids,
            "reasoning": "Following the pre-planned smoke-test crew split.",
        }
        return AgentTurn(text=json.dumps(payload), session_id="stub-session")


def run_auction_coordinator(game_id: int) -> None:
    from heist.auction import run_auction

    def emit_tagged(ai_idx: int, evt: dict) -> None:
        gamestate.broadcast({**evt, "ai_idx": ai_idx, "game_id": game_id})

    def snapshot_cb(payload: dict) -> None:
        with gamestate.lock:
            game = gamestate.games.get(game_id)
            ais = list(game.get("ais", [])) if game else []
        for ai_idx, ai_cfg in enumerate(ais):
            try:
                save_runner_snapshot(
                    game_id,
                    ai_idx,
                    {
                        **payload,
                        "game_id": game_id,
                        "ai_idx": ai_idx,
                        "agent": ai_cfg.get("agent", "stub"),
                    },
                )
            except Exception as exc:
                log.warn(
                    "save_runner_snapshot_failed",
                    game_id=game_id,
                    ai_idx=ai_idx,
                    error=str(exc),
                )

    with gamestate.lock:
        game = gamestate.games.get(game_id)
        if not game:
            return
        ais_cfg = list(game.get("ais", []))
    try:
        ais = [
            _build_ai(cfg.get("agent", "stub"), ai_idx=ai_idx, auction_mode=True)
            for ai_idx, cfg in enumerate(ais_cfg)
        ]
        logs_per_ai: dict[int, list] = {i: [] for i in range(len(ais))}
        result = run_auction(
            ais,
            [cfg.get("prompt", "") for cfg in ais_cfg],
            logs_per_ai,
            emit_tagged,
            gamestate.broadcast,
            snapshot_fn=snapshot_cb,
        )
        for ai_idx, ai_cfg in enumerate(ais_cfg):
            t = threading.Thread(
                target=_run_game,
                args=(
                    ai_cfg.get("prompt", ""),
                    ai_cfg.get("agent", "stub"),
                    None,
                    game_id,
                    ai_idx,
                ),
                kwargs={
                    "crew": result.crews[ai_idx],
                    "ai_obj": ais[ai_idx],
                },
                daemon=True,
            )
            t.start()
    except Exception as exc:
        gamestate.broadcast({"type": "error", "message": str(exc)})
        log.error(
            "auction_coordinator_crashed",
            game_id=game_id,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        persist_game: dict | None = None
        with gamestate.lock:
            game = gamestate.games.get(game_id)
            if game:
                game["status"] = "done"
                game["ai_results"] = [
                    {"error": str(exc)} for _ in game.get("ais", [])
                ]
                game["ais_remaining"] = 0
                persist_game = dict(game)
            gamestate.runtime.game_running = False
        if persist_game is not None:
            try:
                save_game_record(persist_game)
            except Exception as save_exc:
                log.warn("save_game_record_failed", game_id=game_id,
                         error=str(save_exc))


def _run_game(
    strategy: str,
    agent: str,
    seed: int | None,
    game_id: int,
    ai_idx: int = 0,
    resume_snapshot: dict | None = None,
    crew=None,
    ai_obj=None,
) -> None:
    started_at = time.monotonic()
    log.info(
        "game_started" if resume_snapshot is None else "game_resumed",
        game_id=game_id,
        ai_idx=ai_idx,
        agent=agent,
        prompt_len=len(strategy),
        seed=seed,
    )

    def emit_tagged(evt: dict) -> None:
        gamestate.broadcast({**evt, "ai_idx": ai_idx, "game_id": game_id})

    def snapshot_cb(payload: dict) -> None:
        payload = {**payload, "game_id": game_id, "ai_idx": ai_idx, "agent": agent}
        try:
            save_runner_snapshot(game_id, ai_idx, payload)
        except Exception as exc:
            log.warn("save_runner_snapshot_failed",
                     game_id=game_id, ai_idx=ai_idx, error=str(exc))

    def _record_result(result: dict) -> None:
        """Stash this AI's outcome in game["ai_results"][ai_idx]; flip game-level
        status to "done" once every AI has finished."""
        persist_game: dict | None = None
        with gamestate.lock:
            game = gamestate.games.get(game_id)
            if not game:
                return
            results = game.setdefault("ai_results", [None] * len(game.get("ais", [])))
            if ai_idx < len(results):
                results[ai_idx] = result
            # Keep top-level summary fields backed by AI 0 (for lobby display).
            if ai_idx == 0 and "error" not in result:
                game.update({
                    "job": result.get("job"),
                    "take": result.get("take"),
                    "aborted": result.get("aborted"),
                    "escape_success": result.get("escape_success"),
                })
            game["ais_remaining"] = max(0, game.get("ais_remaining", 1) - 1)
            if game["ais_remaining"] == 0:
                game["status"] = "done"
                gamestate.runtime.game_running = False
            persist_game = dict(game)
        if persist_game is not None:
            try:
                save_game_record(persist_game)
            except Exception as exc:
                log.warn("save_game_record_failed",
                         game_id=game_id, error=str(exc))

    try:
        from heist.runner import resume_heist, run_heist
        from heist.serialize import state_to_dict

        ai = ai_obj
        if ai is None:
            try:
                ai = _build_ai(agent)
            except RuntimeError as exc:
                err = str(exc)
                emit_tagged({"type": "error", "message": err})
                log.error("game_crashed", game_id=game_id, ai_idx=ai_idx, error=err)
                _record_result({"error": err})
                return

        if resume_snapshot is not None:
            # Re-attach the codex session so the CLI picks up the in-flight
            # conversation. If the session has expired on disk, the next AI
            # call will fail and we mark this AI errored — same path as any
            # other AI failure, no special-case logic needed.
            sid = resume_snapshot.get("session_id")
            if sid and hasattr(ai, "session_id"):
                ai.session_id = sid
            state, extras = resume_heist(
                resume_snapshot, ai, emit=emit_tagged, snapshot_fn=snapshot_cb,
            )
        else:
            # Different seed per AI so parallel runs diverge meaningfully.
            rng_seed = seed if seed is not None else random.randint(0, 1 << 30) + ai_idx
            rng = random.Random(rng_seed)
            state, extras = run_heist(
                strategy, ai, crew=crew, rng=rng, emit=emit_tagged, snapshot_fn=snapshot_cb,
            )

        emit_tagged({
            "type": "game_done",
            "state": state_to_dict(state),
            "extras": {
                "casting_summary": extras.get("casting_summary", ""),
                "epilogue": extras.get("epilogue", ""),
                "strategy": extras.get("strategy", ""),
            },
        })
        log.info(
            "game_ended",
            game_id=game_id,
            ai_idx=ai_idx,
            take=state.final_take,
            aborted=state.aborted,
            escape_success=state.escape_success,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        _record_result({
            "job": state.job.name,
            "take": state.final_take,
            "aborted": state.aborted,
            "escape_success": state.escape_success,
        })
        # Snapshot served its purpose — clean up so the recovery path doesn't
        # try to re-resume a finished game.
        try:
            delete_runner_snapshot(game_id, ai_idx)
        except Exception as exc:
            log.warn("delete_snapshot_failed",
                     game_id=game_id, ai_idx=ai_idx, error=str(exc))
    except Exception as exc:
        emit_tagged({"type": "error", "message": str(exc)})
        log.error(
            "game_crashed",
            game_id=game_id,
            ai_idx=ai_idx,
            error=str(exc),
            traceback=traceback.format_exc(),
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        _record_result({"error": str(exc)})
        with contextlib.suppress(Exception):
            delete_runner_snapshot(game_id, ai_idx)


def recover_games() -> tuple[int, int]:
    """Reload games + snapshots from ``./state/``, spawn resume threads for
    any AI that was mid-run when the server stopped. Returns
    (games_recovered, ai_threads_resuming)."""
    records = load_game_records()
    if not records:
        return (0, 0)

    games_recovered = 0
    ai_resuming = 0
    auction_restart: list[int] = []
    pending: list[tuple[int, int, dict, dict]] = []  # (gid, ai_idx, snap, ai_cfg)

    with gamestate.lock:
        for gid, record in records.items():
            gamestate.games[gid] = record
            gamestate.runtime.next_id = max(gamestate.runtime.next_id, gid + 1)
            games_recovered += 1

            if record.get("status") != "running":
                continue

            ais = record.get("ais", [])
            results = record.get("ai_results") or [None] * len(ais)
            # Pad in case of a stale file.
            if len(results) < len(ais):
                results = results + [None] * (len(ais) - len(results))

            snapshots = list_pending_snapshots(gid)
            if not snapshots or any(
                snap.get("stage", "").startswith("auction_round_")
                or snap.get("stage") == "auction_complete"
                for snap in snapshots.values()
            ):
                auction_restart.append(gid)
                gamestate.runtime.game_running = True
                continue

            still_remaining = 0
            for ai_idx, ai_cfg in enumerate(ais):
                if results[ai_idx] is not None:
                    continue
                if ai_idx in snapshots:
                    pending.append((gid, ai_idx, snapshots[ai_idx], ai_cfg))
                    still_remaining += 1
                else:
                    # No snapshot — game crashed before this AI made any
                    # observable progress. Mark it errored and move on.
                    results[ai_idx] = {"error": "no snapshot — crashed before first turn"}

            record["ai_results"] = results
            record["ais_remaining"] = still_remaining
            if still_remaining == 0:
                record["status"] = "done"
            else:
                gamestate.runtime.game_running = True

            ai_resuming += still_remaining

    # Persist any status flips we made above (errored AIs, status→done).
    for gid in records:
        try:
            with gamestate.lock:
                snap = dict(gamestate.games[gid])
            save_game_record(snap)
        except Exception as exc:
            log.warn("save_game_record_failed", game_id=gid, error=str(exc))

    for gid in auction_restart:
        log.info("game_recovered_auction", game_id=gid)
        t = threading.Thread(
            target=run_auction_coordinator,
            args=(gid,),
            daemon=True,
        )
        t.start()

    for gid, ai_idx, snap, ai_cfg in pending:
        log.info("game_recovered", game_id=gid, ai_idx=ai_idx,
                 stage=snap.get("stage"), scene_idx=snap.get("scene_idx"))
        t = threading.Thread(
            target=_run_game,
            args=(ai_cfg.get("prompt", ""), ai_cfg.get("agent", "stub"),
                  None, gid, ai_idx),
            kwargs={"resume_snapshot": snap},
            daemon=True,
        )
        t.start()

    return (games_recovered, ai_resuming)
