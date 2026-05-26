"""Game orchestration: auction coordinator, per-AI heist threads, startup recovery.

Spawns daemon threads; emits through gamestate.broadcast.
"""
from __future__ import annotations

import contextlib
import random
import threading
import time
import traceback
from typing import Any

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


def _build_ai(agent: str, *, ai_idx: int = 0, auction_mode: bool = False, progress_cb=None):
    from heist.backends import CodexHeistAI, GeminiHeistAI
    from heist.stub_responses import build_stub_ai

    if agent == "stub":
        if not auction_mode:
            return build_stub_ai()
        return _AuctionAwareStubAI(ai_idx)
    if agent == "codex":
        return CodexHeistAI(model="gpt-5.4", progress_cb=progress_cb)
    if agent == "codex-mini":
        return CodexHeistAI(model="gpt-5.4-mini", progress_cb=progress_cb)
    if agent == "gemini":
        return GeminiHeistAI(progress_cb=progress_cb)
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
        if "round of crew bidding" not in prompt and "bid was rejected" not in prompt:
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

        with gamestate.lock:
            _campaign_id = gamestate.games.get(game_id, {}).get("campaign_id")
        emit_tagged({
            "type": "game_done",
            "game_id": game_id,
            "campaign_id": _campaign_id,
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


# ── campaign conductor ────────────────────────────────────────────────────────

# Order of the four per-round stages. Used by resume to skip stages already
# completed before a crash (resume re-enters at the persisted stage boundary).
_STAGE_ORDER = {"opening_wire": 0, "hiring": 1, "heist": 2, "reflection": 3}


def _campaign_ended(camp: Any) -> bool:
    return len(camp.standing_crew) == 0


def _crew_from_game_state(gs: dict) -> list:
    """Extract Character objects from a game_state dict (post-auction snapshot)."""
    from heist.content import ROSTER_BY_ID as _RBI
    from heist.state import Character as _Char
    crew_raw = gs.get("crew", {})
    if isinstance(crew_raw, dict):
        members_raw = crew_raw.get("members", [])
    else:
        members_raw = list(crew_raw or [])
    result: list[Any] = []
    for m in members_raw:
        if isinstance(m, _Char):
            result.append(m)
        elif isinstance(m, dict):
            cid = m.get("char_id") or m.get("id")
            if cid is not None:
                char = _RBI.get(int(cid))
                if char:
                    result.append(char)
    return result


def _rehire_pool(campaigns: list, roster: list) -> list:
    """Characters available to re-hire in a rehire auction.

    Excludes anyone currently on a standing crew AND anyone who has ever been
    caught — a caught crew member is out of the game for good and never returns
    to the pool, even though they were removed from their team's standing crew.
    """
    excluded: set[int] = set()
    for camp in campaigns:
        if camp is None:
            continue
        for member in camp.standing_crew:
            excluded.add(member.id)
        for rr in camp.round_results:
            excluded.update(rr.caught_member_ids)
    return [c for c in roster if c.id not in excluded]


def _build_game_states_snapshot(
    campaign_id: int,
    campaigns: list,
    ais_cfg: list[dict],
    ais: list,
    round_gids_per_ai: list,
    heist_states: list,
) -> list[dict]:
    """Build a list of per-AI state snapshots for passing to wire/reflection calls."""
    from heist.serialize import campaign_to_dict
    result: list[dict] = []
    for i, camp in enumerate(campaigns):
        if camp is None:
            result.append({
                "ai_idx": i,
                "ai_name": ais_cfg[i].get("name", f"AI {i + 1}"),
                "ai": ais[i] if i < len(ais) else None,
                "standing_crew": [],
                "banked_loot": 0,
                "notoriety": 0,
                "round_results": [],
            })
        else:
            d = campaign_to_dict(camp)
            state = heist_states[i] if i < len(heist_states) else None
            if state is not None:
                d["job_name"] = state.job.name
                d["take"] = state.final_take
                d["escape_success"] = state.escape_success
                d["caught_member_ids"] = list(state.caught_member_ids)
            d["ai_idx"] = i
            d["ai_name"] = ais_cfg[i].get("name", f"AI {i + 1}")
            d["ai"] = ais[i] if i < len(ais) else None
            d["round_game_ids"] = list(round_gids_per_ai[i])
            result.append(d)
    return result


def run_campaign_conductor(
    campaign_id: int, num_rounds: int, resume: bool = False,
) -> None:
    """One thread that runs all AIs through each round in lockstep.

    Stages per round: opening_wire → hiring → heist → reflection.
    Updates game['current_stage'] and game['current_round_idx'] after each stage.

    When ``resume=True``, rebuilds each team's Campaign from the persisted
    ``game_states`` and re-enters the loop at the first un-settled round, at the
    stage boundary recorded in ``current_stage`` — without re-running completed
    stages (see campaign-resume spec). Idempotent: never double-banks loot.
    """
    from heist.campaign import (
        _opening_wire_call,
        _reflection_call,
        _settle_round_core,
        settle_round,
    )
    from heist.content import BANKROLL, ROSTER  # noqa: F401 used below
    from heist.persist import save_game_record
    from heist.runner import TurnLog, run_one_job
    from heist.serialize import campaign_from_dict, campaign_to_dict, crew_to_dict
    from heist.state import Campaign as CampaignType
    from heist.state import Crew as CrewType
    from heist.state import HeistState

    with gamestate.lock:
        game = gamestate.games.get(campaign_id)
        if not game:
            return
        ais_cfg = list(game.get("ais_cfg", []))

    num_ais = len(ais_cfg)
    strategies = [cfg.get("prompt", "") for cfg in ais_cfg]

    def _beat(*, ai_name=None, attempt=None, max_attempts=None):
        with gamestate.lock:
            g = gamestate.games.get(campaign_id)
            if not g:
                return
            g["progress"] = {
                "round": int(g.get("current_round_idx", 0) or 0),
                "total_rounds": int(num_rounds),
                "stage": g.get("current_stage"),
                "ai_name": ai_name,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "updated_at": time.time(),
            }

    try:
        ais = []
        for i, cfg in enumerate(ais_cfg):
            ai_name = cfg.get("name", f"AI {i + 1}")
            ais.append(
                _build_ai(
                    cfg.get("agent", "stub"),
                    ai_idx=i,
                    progress_cb=(
                        lambda attempt, mx, _name=ai_name:
                        _beat(ai_name=_name, attempt=attempt, max_attempts=mx)
                    ),
                )
            )
    except Exception as exc:
        log.error(
            "campaign_conductor_build_failed",
            campaign_id=campaign_id,
            error=str(exc),
        )
        persist_game: dict = {}
        with gamestate.lock:
            game = gamestate.games.get(campaign_id)
            if game:
                game["status"] = "done"
                game["ais_remaining"] = 0
                persist_game = dict(game)
        import contextlib as _cl
        with _cl.suppress(Exception):
            save_game_record(persist_game)
        gamestate.broadcast({"type": "campaign_done", "campaign_id": campaign_id})
        return

    campaigns: list[CampaignType | None] = [None] * num_ais
    heist_states: list[HeistState | None] = [None] * num_ais
    # Per-team heist-take checkpoint (Decision 3 / Option B): the heist's outcome
    # lives only in memory until reflection settles it, so we persist a minimal
    # snapshot after the heist join and clear it once settle_round consumes it.
    # On resume this lets reflection settle without re-running the heist.
    pending_heist_per_ai: list[dict | None] = [None] * num_ais
    logs_per_ai: list[list[TurnLog]] = [[] for _ in range(num_ais)]
    round_gids_per_ai: list[list[int]] = [[] for _ in range(num_ais)]
    current_round_sub_gids: list[int | None] = [None] * num_ais
    hiring_gids: list[int | None] = [None] * num_rounds

    def emit_for_ai(ai_idx: int, evt: dict) -> None:
        gamestate.broadcast({**evt, "ai_idx": ai_idx, "campaign_id": campaign_id})

    def set_stage(stage: str, round_idx: int) -> None:
        gamestate.update_game(campaign_id, current_stage=stage, current_round_idx=round_idx)
        _beat()
        gamestate.broadcast({
            "type": "campaign_stage",
            "campaign_id": campaign_id,
            "stage": stage,
            "round_idx": round_idx,
        })

    def snapshot_all(*, finished: bool = False) -> None:
        persist_game_snap: dict | None = None
        with gamestate.lock:
            game = gamestate.games.get(campaign_id)
            if not game:
                return
            # Mark this campaign as resumable under the new checkpointing model.
            # Absent ⇒ a pre-existing stall ⇒ recover_games marks it interrupted.
            game["checkpoint_version"] = 1
            for i, camp in enumerate(campaigns):
                if camp is None:
                    continue
                entry = {
                    **campaign_to_dict(camp),
                    "ai_idx": i,
                    "ai_name": ais_cfg[i].get("name", f"AI {i + 1}"),
                    "round_game_ids": list(round_gids_per_ai[i]),
                    "hiring_game_ids": list(hiring_gids),
                    "ai_game_id": round_gids_per_ai[i][-1] if round_gids_per_ai[i] else None,
                    "pending_heist": pending_heist_per_ai[i],
                    "status": "done" if finished else "running",
                }
                game["game_states"][i] = entry
            if finished:
                game["status"] = "done"
                game["ais_remaining"] = 0
            persist_game_snap = dict(game)
        if persist_game_snap is not None:
            try:
                save_game_record(persist_game_snap)
            except Exception as exc:
                log.warn("save_game_record_failed", game_id=campaign_id, error=str(exc))

    def open_round_sub_game(ai_idx: int, round_idx: int) -> int:
        with gamestate.lock:
            rgid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            current_round_sub_gids[ai_idx] = rgid
            gamestate.games[rgid] = {
                "id": rgid,
                "created_at": time.time(),
                "status": "running",
                "is_campaign_sub": True,
                "campaign_id": campaign_id,
                "parent_campaign_id": campaign_id,
                "hidden_from_lobby": True,
                "ai_idx": ai_idx,
                "ai_name": ais_cfg[ai_idx].get("name", f"AI {ai_idx + 1}"),
                "round_idx": round_idx,
                "hire_sub_game_id": hiring_gids[round_idx],
                "heist_sub_game_id": rgid,
                "events": [],
            }
        hgid = hiring_gids[round_idx]
        if hgid is not None:
            with gamestate.lock:
                sub = gamestate.games.get(hgid)
                if sub is not None:
                    heist_ids = list(sub.get("heist_sub_game_ids", []))
                    heist_ids.append(rgid)
                    sub["heist_sub_game_ids"] = heist_ids
                    if sub.get("heist_sub_game_id") is None:
                        sub["heist_sub_game_id"] = rgid
                    persist = dict(sub)
                else:
                    persist = None
            if persist is not None:
                try:
                    save_game_record(persist)
                except Exception as exc:
                    log.warn("save_game_record_failed", game_id=hgid, error=str(exc))
        return rgid

    def close_round_sub_game(ai_idx: int) -> int | None:
        rgid = current_round_sub_gids[ai_idx]
        if rgid is None:
            return None
        persist: dict | None = None
        with gamestate.lock:
            sub = gamestate.games.get(rgid)
            if sub:
                sub["status"] = "done"
                persist = dict(sub)
        current_round_sub_gids[ai_idx] = None
        if persist is not None:
            try:
                save_game_record(persist)
            except Exception as exc:
                log.warn("save_game_record_failed", game_id=rgid, error=str(exc))
        round_gids_per_ai[ai_idx].append(rgid)
        return rgid

    def open_hiring_sub_game(round_idx: int) -> int:
        with gamestate.lock:
            hgid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            hiring_gids[round_idx] = hgid
            gamestate.games[hgid] = {
                "id": hgid,
                "created_at": time.time(),
                "status": "running",
                "is_hiring_sub": True,
                "campaign_id": campaign_id,
                "parent_campaign_id": campaign_id,
                "hidden_from_lobby": True,
                "round_idx": round_idx,
                "hire_sub_game_id": hgid,
                "heist_sub_game_id": None,
                "heist_sub_game_ids": [],
                "ai_idx": None,
                "ai_name": None,
                # Shell.js reads `ais` to populate aiList → chip columns.
                # Without this field, Shell.aiList stays [] and no bid
                # markers or crew columns render in the hiring viewer.
                "ais": [
                    {"name": cfg.get("name", f"AI {i + 1}")}
                    for i, cfg in enumerate(ais_cfg)
                ],
                "events": [],
            }
        return hgid

    def close_hiring_sub_game(round_idx: int) -> None:
        hgid = hiring_gids[round_idx]
        if hgid is None:
            return
        persist: dict | None = None
        with gamestate.lock:
            sub = gamestate.games.get(hgid)
            if sub:
                sub["status"] = "done"
                persist = dict(sub)
        if persist is not None:
            try:
                save_game_record(persist)
            except Exception as exc:
                log.warn("save_hiring_sub_game_failed", game_id=hgid, error=str(exc))

    def make_emit_fn(ai_idx: int):
        def emit_fn(evt: dict) -> None:
            rgid = current_round_sub_gids[ai_idx]
            tagged = {**evt, "ai_idx": ai_idx, "campaign_id": campaign_id}
            if rgid is not None:
                tagged["game_id"] = rgid
            gamestate.broadcast(tagged)
        return emit_fn

    def run_initial_auction() -> None:
        from heist.auction import run_auction

        def emit_tagged(ai_idx: int, evt: dict) -> None:
            hgid = hiring_gids[0]
            tagged = {**evt, "ai_idx": ai_idx, "campaign_id": campaign_id}
            if hgid is not None:
                tagged["game_id"] = hgid
            gamestate.broadcast(tagged)

        def emit_and_save(evt: dict) -> None:
            hgid = hiring_gids[0]
            broadcast_evt = {**evt, "campaign_id": campaign_id}
            if hgid is not None:
                broadcast_evt["game_id"] = hgid
            gamestate.broadcast(broadcast_evt)
            if evt.get("type") == "auction_round_resolved":
                with gamestate.lock:
                    game = gamestate.games.get(campaign_id)
                    if game:
                        for i_str, char_ids in evt.get("crews_after", {}).items():
                            idx = int(i_str)
                            if idx < len(game["game_states"]):
                                game["game_states"][idx]["standing_crew"] = char_ids
                snapshot_all()

        result = run_auction(
            ais, strategies,
            {i: list(logs_per_ai[i]) for i in range(num_ais)},
            emit_tagged, emit_and_save,
        )
        with gamestate.lock:
            game = gamestate.games.get(campaign_id)
            if not game:
                return
            for i in range(num_ais):
                crew = result.crews.get(i)
                if crew is not None:
                    game["game_states"][i]["crew"] = crew_to_dict(crew)
                    game["game_states"][i]["standing_crew"] = [m.id for m in crew.members]
        # Initialize Campaign objects from hired crews
        for i in range(num_ais):
            with gamestate.lock:
                game = gamestate.games.get(campaign_id)
                gs = game["game_states"][i] if game else {}
            crew_members = _crew_from_game_state(gs)
            crew_cost = sum(c.floor_cost for c in crew_members)
            campaigns[i] = CampaignType(
                rounds_total=num_rounds,
                bankroll=BANKROLL - crew_cost,
                banked_loot=0,
                standing_crew=list(crew_members),
                round_results=[],
            )

    def run_rehire_auction() -> None:
        from heist.auction import run_auction

        available_pool = _rehire_pool(campaigns, ROSTER)

        initial_crews_map: dict[int, list] = {}
        initial_bankrolls_map: dict[int, int] = {}
        for i, camp in enumerate(campaigns):
            if camp is not None:
                initial_crews_map[i] = list(camp.standing_crew)
                initial_bankrolls_map[i] = camp.banked_loot
            else:
                initial_crews_map[i] = []
                initial_bankrolls_map[i] = 0

        def emit_tagged(ai_idx: int, evt: dict) -> None:
            hgid = hiring_gids[last_round_idx]
            tagged = {**evt, "ai_idx": ai_idx, "campaign_id": campaign_id}
            if hgid is not None:
                tagged["game_id"] = hgid
            gamestate.broadcast(tagged)

        def emit_and_save(evt: dict) -> None:
            hgid = hiring_gids[last_round_idx]
            broadcast_evt = {**evt, "campaign_id": campaign_id}
            if hgid is not None:
                broadcast_evt["game_id"] = hgid
            gamestate.broadcast(broadcast_evt)
            if evt.get("type") == "auction_round_resolved":
                with gamestate.lock:
                    game = gamestate.games.get(campaign_id)
                    if game:
                        for i_str, char_ids in evt.get("crews_after", {}).items():
                            idx = int(i_str)
                            if idx < len(game["game_states"]):
                                game["game_states"][idx]["standing_crew"] = char_ids
                snapshot_all()

        result = run_auction(
            ais, strategies,
            {i: list(logs_per_ai[i]) for i in range(num_ais)},
            emit_tagged, emit_and_save,
            initial_crews=initial_crews_map,
            initial_bankrolls=initial_bankrolls_map,
            pool_override=available_pool,
        )
        for i, camp in enumerate(campaigns):
            if camp is None:
                continue
            newly_hired_crew = result.crews.get(i)
            if newly_hired_crew is None:
                continue
            spent = result.bankrolls_spent.get(i, 0)
            camp.standing_crew = list(newly_hired_crew.members)
            camp.banked_loot -= spent
            with gamestate.lock:
                game = gamestate.games.get(campaign_id)
                if game:
                    game["game_states"][i]["crew"] = crew_to_dict(newly_hired_crew)
                    game["game_states"][i]["standing_crew"] = [
                        m.id for m in newly_hired_crew.members
                    ]

    # Guard against a second conductor for this campaign in THIS process
    # (manual resume checks active_campaigns before spawning). Added here, once
    # the AI backends built cleanly; removed in the finally below.
    with gamestate.lock:
        gamestate.runtime.active_campaigns.add(campaign_id)

    last_round_idx = 0
    try:
        # ── Resume reconstruction ────────────────────────────────────────────
        # Rebuild each team's Campaign + per-round sub-game id lists from the
        # persisted game_states, then compute where to re-enter the round loop.
        start_round = 0
        resume_stage_idx = 0
        if resume:
            with gamestate.lock:
                game = gamestate.games.get(campaign_id)
                persisted_states = list(game.get("game_states", [])) if game else []
                persisted_round = int(game.get("current_round_idx", 0) or 0) if game else 0
                persisted_stage = (
                    (game.get("current_stage") if game else None) or "opening_wire"
                )
            for i in range(num_ais):
                gs = persisted_states[i] if i < len(persisted_states) else None
                if not isinstance(gs, dict) or not gs:
                    continue
                campaigns[i] = campaign_from_dict(gs)
                round_gids_per_ai[i] = list(gs.get("round_game_ids", []) or [])
                ph = gs.get("pending_heist")
                pending_heist_per_ai[i] = dict(ph) if isinstance(ph, dict) else None
            # hiring_gids is the same list across teams — restore from any team
            # that recorded it.
            for i in range(num_ais):
                gs = persisted_states[i] if i < len(persisted_states) else None
                if isinstance(gs, dict) and gs.get("hiring_game_ids"):
                    for r, hg in enumerate(gs.get("hiring_game_ids", []) or []):
                        if r < len(hiring_gids):
                            hiring_gids[r] = hg
                    break
            # Settle-once reconciliation: a round is settled iff its RoundResult
            # is present in every active team's round_results.
            active_lens = [
                len(c.round_results)
                for c in campaigns
                if c is not None and not _campaign_ended(c)
            ]
            if active_lens:
                min_settled = min(active_lens)
                if min_settled == persisted_round:
                    # Conductor was mid-round at the persisted stage.
                    start_round = persisted_round
                    resume_stage_idx = _STAGE_ORDER.get(persisted_stage, 0)
                else:
                    # Either the persisted round already settled everywhere
                    # (crash after the post-reflection snapshot) or a team lags
                    # the stage marker — restart the earliest unsettled round.
                    start_round = min_settled
                    resume_stage_idx = 0
            else:
                start_round = persisted_round
                resume_stage_idx = 0
            log.info(
                "campaign_resume",
                campaign_id=campaign_id,
                start_round=start_round,
                resume_stage_idx=resume_stage_idx,
                persisted_round=persisted_round,
                persisted_stage=persisted_stage,
            )

        for round_idx in range(start_round, num_rounds):
            last_round_idx = round_idx
            # For the resume round, skip stages already completed; later rounds
            # run every stage.
            rs = resume_stage_idx if round_idx == start_round else 0

            # ── Stage 1: Opening Wire ────────────────────────────────────────
            if rs <= _STAGE_ORDER["opening_wire"]:
                set_stage("opening_wire", round_idx)
                game_states_snapshot = _build_game_states_snapshot(
                    campaign_id, campaigns, ais_cfg, ais, round_gids_per_ai, heist_states,
                )
                for i in range(num_ais):
                    camp = campaigns[i]
                    if camp is not None and not _campaign_ended(camp):
                        _opening_wire_call(
                            camp, i, round_idx, ais[i],
                            game_states_snapshot, logs_per_ai[i],
                            make_emit_fn(i),
                        )
                    elif camp is None and round_idx == 0:
                        # Before first auction, campaigns are None — still generate wire
                        pass
                snapshot_all()

            # ── Stage 2: Hiring ──────────────────────────────────────────────
            if rs <= _STAGE_ORDER["hiring"]:
                set_stage("hiring", round_idx)
                open_hiring_sub_game(round_idx)
                if round_idx == 0:
                    run_initial_auction()
                else:
                    run_rehire_auction()
                close_hiring_sub_game(round_idx)
                snapshot_all()

            # ── Stage 3: Heist (parallel — each AI's heist is independent) ────
            # Each AI runs its own crew/job/scenes against its own Campaign
            # object and its own backend instance, writing only to its own
            # per-AI index (sub-game, logs, heist_states) under gamestate.lock.
            # So the heists run concurrently; we join them all before moving on,
            # which keeps the stage barrier (reflection waits for every heist).
            if rs <= _STAGE_ORDER["heist"]:
                set_stage("heist", round_idx)

                def _run_heist(i: int, round_idx: int = round_idx) -> None:
                    camp = campaigns[i]
                    if camp is None or _campaign_ended(camp) or not camp.standing_crew:
                        return
                    # Resume idempotency: if this team's heist already completed
                    # and was checkpointed before a crash, don't re-run it —
                    # reflection will settle from the persisted pending_heist. In
                    # live play this is always None at heist start (the prior
                    # round's settle cleared it).
                    if pending_heist_per_ai[i] is not None:
                        return
                    rng = random.Random()
                    rgid = open_round_sub_game(i, round_idx)
                    emit_fn = make_emit_fn(i)
                    crew_evt = {
                        "type": "crew_known",
                        "crew": crew_to_dict(CrewType(members=list(camp.standing_crew))),
                        "game_id": rgid,
                        "campaign_id": campaign_id,
                        "ai_idx": i,
                    }
                    gamestate.broadcast(crew_evt)
                    try:
                        result = run_one_job(
                            strategies[i], ais[i], camp, rng=rng, emit=emit_fn,
                        )
                    except Exception as exc:
                        log.error(
                            "campaign_conductor_heist_failed",
                            campaign_id=campaign_id,
                            ai_idx=i,
                            round=round_idx,
                            error=str(exc),
                            traceback=traceback.format_exc(),
                        )
                        result = None
                    close_round_sub_game(i)
                    heist_states[i] = result[0] if result is not None else None

                heist_threads = [
                    threading.Thread(
                        target=_run_heist,
                        args=(i,),
                        name=f"heist-c{campaign_id}-r{round_idx}-ai{i}",
                    )
                    for i in range(num_ais)
                ]
                for t in heist_threads:
                    t.start()
                for t in heist_threads:
                    t.join()

            # Heist-take checkpoint (Option B): persist each team's heist result
            # so reflection can settle without re-running the heist on resume.
            # Runs whether or not the heist stage executed this iteration — for a
            # resumed reflection (heist skipped) it keeps the reconstructed
            # pending_heist; for a fresh heist it records the new result.
            for i in range(num_ais):
                st = heist_states[i]
                if st is not None:
                    pending_heist_per_ai[i] = {
                        "final_take": st.final_take,
                        "heat": st.heat,
                        "caught_member_ids": list(st.caught_member_ids),
                        "job_name": st.job.name,
                        "aborted": st.aborted,
                        "escape_success": st.escape_success,
                    }
            snapshot_all()

            # ── Stage 4: Reflection + settle ─────────────────────────────────
            set_stage("reflection", round_idx)
            game_states_after = _build_game_states_snapshot(
                campaign_id, campaigns, ais_cfg, ais, round_gids_per_ai, heist_states,
            )
            any_ended = False
            for i in range(num_ais):
                camp = campaigns[i]
                if camp is None or _campaign_ended(camp):
                    continue
                # Settle-once: skip any team whose RoundResult for this round was
                # already banked on a prior (crashed) attempt.
                if len(camp.round_results) > round_idx:
                    pending_heist_per_ai[i] = None
                    continue
                state = heist_states[i]
                ph = pending_heist_per_ai[i]
                if state is None and ph is None:
                    # No heist happened for this team this round — nothing to settle.
                    continue
                if state is not None:
                    _reflection_call(
                        camp, i, round_idx, ais[i],
                        game_states_after, logs_per_ai[i],
                        make_emit_fn(i),
                    )
                    ended = settle_round(camp, state)
                elif ph is not None:
                    # Resumed from checkpoint: settle from the persisted heist
                    # result without re-running the heist (the reflection
                    # commentary for this one round is skipped — cosmetic only).
                    ended = _settle_round_core(
                        camp,
                        final_take=int(ph.get("final_take", 0)),
                        heat=int(ph.get("heat", 0)),
                        caught_member_ids=list(ph.get("caught_member_ids", []) or []),
                        job_name=str(ph.get("job_name", "")),
                        aborted=bool(ph.get("aborted", False)),
                        escape_success=ph.get("escape_success"),
                    )
                # Consumed — clear so the next round's heist runs normally.
                pending_heist_per_ai[i] = None
                if ended:
                    any_ended = True
            snapshot_all()

            gamestate.broadcast({
                "type": "campaign_round_done",
                "campaign_id": campaign_id,
                "round_idx": round_idx,
            })

            if any_ended:
                break

        set_stage("done", last_round_idx)
        snapshot_all(finished=True)
        gamestate.broadcast({"type": "campaign_done", "campaign_id": campaign_id})

    except Exception as exc:
        log.error(
            "campaign_conductor_crashed",
            campaign_id=campaign_id,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        snapshot_all(finished=True)
        gamestate.broadcast({"type": "campaign_done", "campaign_id": campaign_id})
    finally:
        with gamestate.lock:
            gamestate.runtime.active_campaigns.discard(campaign_id)
