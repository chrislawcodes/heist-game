"""Campaign resume: round-trip serialization + conductor stage-skip idempotency.

These exercise the resume engine in heist/orchestration.py
(``run_campaign_conductor(..., resume=True)``) directly — no HTTP layer — by
seeding ``gamestate.games`` with a persisted mid-campaign record and confirming
the conductor settles each round exactly once and never re-runs a completed
stage (no double-banked loot, no duplicate round results / sub-game ids).
"""
from __future__ import annotations

import threading
import time

import pytest

from heist import gamestate, orchestration
from heist.content import BANKROLL, JOBS, ROSTER
from heist.serialize import (
    campaign_from_dict,
    campaign_to_dict,
)
from heist.state import Campaign, RoundResult

# ── T003: campaign_from_dict round-trips a snapshot, ignoring extra keys ───────

def test_campaign_from_dict_round_trips_ignoring_extra_keys():
    """A snapshot built the way ``snapshot_all`` builds it (campaign_to_dict +
    conductor extras) must reconstruct standing_crew / banked_loot /
    round_results, ignoring the extra keys."""
    crew = list(ROSTER[:3])
    camp = Campaign(
        rounds_total=5,
        bankroll=BANKROLL - 100_000,
        banked_loot=750_000,
        standing_crew=list(crew),
        round_results=[
            RoundResult(
                round_idx=0,
                job_name="Museum Gala",
                take=750_000,
                aborted=False,
                escape_success=True,
                heat=2,
                banked_after=750_000,
                caught_member_ids=[],
                crew_ids=[c.id for c in crew],
            ),
        ],
    )

    # Mirror snapshot_all: campaign_to_dict + conductor-only extras.
    snapshot = {
        **campaign_to_dict(camp),
        "ai_idx": 0,
        "ai_name": "Aegis",
        "round_game_ids": [11, 12],
        "hiring_game_ids": [10],
        "ai_game_id": 12,
        "pending_heist": None,
        "status": "running",
    }

    restored = campaign_from_dict(snapshot)

    assert restored.banked_loot == 750_000
    assert restored.bankroll == BANKROLL - 100_000
    assert restored.rounds_total == 5
    assert [c.id for c in restored.standing_crew] == [c.id for c in crew]
    assert len(restored.round_results) == 1
    assert restored.round_results[0].take == 750_000
    assert restored.round_results[0].caught_member_ids == []
    # round_idx is derived from len(round_results) — one round already settled.
    assert restored.round_idx == 1


# ── Conductor resume harness ───────────────────────────────────────────────────

@pytest.fixture()
def clean_state(monkeypatch, tmp_path):
    monkeypatch.setenv("HEIST_STATE_DIR", str(tmp_path / "state"))
    with gamestate.lock:
        gamestate.games.clear()
        gamestate.event_history.clear()
        gamestate.subscribers.clear()
        gamestate.runtime.game_running = False
        gamestate.runtime.next_id = 1
        gamestate.runtime.active_campaigns.clear()
    yield
    with gamestate.lock:
        gamestate.games.clear()
        gamestate.runtime.active_campaigns.clear()


def _team_state(idx, name, crew_members, *, banked_loot, round_results,
                round_game_ids, hiring_game_ids, pending_heist):
    """A persisted per-team checkpoint (post-hiring / post-heist)."""
    camp = Campaign(
        rounds_total=1,
        bankroll=BANKROLL,
        banked_loot=banked_loot,
        standing_crew=list(crew_members),
        round_results=list(round_results),
    )
    # Mirror snapshot_all exactly: campaign_to_dict (standing_crew = character
    # dicts) plus the conductor-only extras. No separate id list / crew key —
    # snapshot_all overwrites the whole entry, so those don't survive on disk.
    return {
        **campaign_to_dict(camp),
        "ai_idx": idx,
        "ai_name": name,
        "round_game_ids": list(round_game_ids),
        "hiring_game_ids": list(hiring_game_ids),
        "ai_game_id": round_game_ids[-1] if round_game_ids else None,
        "pending_heist": pending_heist,
        "status": "running",
    }


def _crew_ids(team_state):
    """Extract standing-crew character ids from a persisted game_state entry."""
    out = []
    for m in team_state.get("standing_crew", []):
        if isinstance(m, dict):
            out.append(m.get("char_id", m.get("id")))
        else:
            out.append(m)
    return out


def _seed_campaign(gid, *, num_rounds, current_round_idx, current_stage, game_states):
    record = {
        "id": gid,
        "created_at": time.time(),
        "status": "running",
        "is_campaign": True,
        "checkpoint_version": 1,
        "num_rounds": num_rounds,
        "current_round_idx": current_round_idx,
        "current_stage": current_stage,
        "ais_cfg": [
            {"name": gs["ai_name"], "agent": "stub", "prompt": "Win."}
            for gs in game_states
        ],
        "game_states": game_states,
        "events": [],
    }
    with gamestate.lock:
        gamestate.games[gid] = record
        gamestate.runtime.next_id = max(gamestate.runtime.next_id, gid + 1)
    return record


def _spy(monkeypatch):
    calls = {"auction": 0, "job": 0}

    def fake_run_auction(*args, **kwargs):  # pragma: no cover - asserted not called
        calls["auction"] += 1
        raise AssertionError("run_auction must not run for a skipped hiring stage")

    def fake_run_one_job(*args, **kwargs):  # pragma: no cover - asserted not called
        calls["job"] += 1
        raise AssertionError("run_one_job must not run when the heist is checkpointed")

    monkeypatch.setattr("heist.auction.run_auction", fake_run_auction)
    monkeypatch.setattr("heist.runner.run_one_job", fake_run_one_job)
    monkeypatch.setattr("heist.campaign._opening_wire_call", lambda *a, **k: None)
    monkeypatch.setattr("heist.campaign._reflection_call", lambda *a, **k: None)
    return calls


# ── T008(a): resume at "heist" with a checkpointed take settles once ───────────

def test_resume_at_heist_skips_hiring_and_settles_once(clean_state, monkeypatch):
    """Reconstructed at start_stage="heist" with a persisted pending_heist:
    hiring is NOT re-run (banked_loot only changes by the checkpointed take) and
    exactly one RoundResult is appended (no duplicate)."""
    calls = _spy(monkeypatch)
    crew = list(ROSTER[:4])
    pending = {
        "final_take": 500_000,
        "heat": 1,
        "caught_member_ids": [],
        "job_name": JOBS[0].name,
        "aborted": False,
        "escape_success": True,
    }
    gs = _team_state(
        0, "Aegis", crew,
        banked_loot=0,                 # post-hiring, pre-settle
        round_results=[],
        round_game_ids=[101],          # heist sub-game already closed
        hiring_game_ids=[100],
        pending_heist=pending,
    )
    _seed_campaign(1, num_rounds=1, current_round_idx=0, current_stage="heist",
                   game_states=[gs])

    orchestration.run_campaign_conductor(1, 1, resume=True)

    assert calls["auction"] == 0, "hiring stage must be skipped on heist resume"
    assert calls["job"] == 0, "heist must not re-run when pending_heist is present"

    with gamestate.lock:
        rec = gamestate.games[1]
        team = rec["game_states"][0]
    assert rec["status"] == "done"
    assert len(team["round_results"]) == 1
    assert team["banked_loot"] == 500_000           # banked exactly the checkpoint take
    assert team["round_game_ids"] == [101]          # no duplicate heist sub-game
    assert team["pending_heist"] is None            # checkpoint consumed
    assert len(_crew_ids(team)) == 4                # nobody caught -> crew intact
    assert 1 not in gamestate.runtime.active_campaigns  # guard released in finally


# ── T008(b): crash between settle and round-advance does not re-settle ─────────

def test_resume_after_settle_does_not_double_settle(clean_state, monkeypatch):
    """Crash landed after settle_round persisted round 0 but before the loop
    advanced. Resume must NOT append a second RoundResult or re-bank loot."""
    calls = _spy(monkeypatch)
    crew = list(ROSTER[:4])
    settled_round = RoundResult(
        round_idx=0,
        job_name=JOBS[0].name,
        take=500_000,
        aborted=False,
        escape_success=True,
        heat=1,
        banked_after=500_000,
        caught_member_ids=[],
        crew_ids=[c.id for c in crew],
    )
    gs = _team_state(
        0, "Aegis", crew,
        banked_loot=500_000,           # already banked
        round_results=[settled_round],
        round_game_ids=[101],
        hiring_game_ids=[100],
        pending_heist=None,            # cleared by the settle that already ran
    )
    _seed_campaign(1, num_rounds=1, current_round_idx=0, current_stage="reflection",
                   game_states=[gs])

    orchestration.run_campaign_conductor(1, 1, resume=True)

    assert calls["auction"] == 0
    assert calls["job"] == 0
    with gamestate.lock:
        rec = gamestate.games[1]
        team = rec["game_states"][0]
    assert rec["status"] == "done"
    assert len(team["round_results"]) == 1          # not double-appended
    assert team["banked_loot"] == 500_000           # not re-banked
    assert 1 not in gamestate.runtime.active_campaigns


# ── Resume at "reflection" with a live checkpoint settles from pending_heist ───

def test_resume_at_reflection_settles_from_pending_heist(clean_state, monkeypatch):
    """Heist finished and pending_heist persisted, crash before settle. Resume at
    reflection banks the checkpointed take without re-running the heist."""
    calls = _spy(monkeypatch)
    crew = list(ROSTER[:4])
    pending = {
        "final_take": 320_000,
        "heat": 0,
        "caught_member_ids": [crew[0].id],   # one member caught -> removed on settle
        "job_name": JOBS[0].name,
        "aborted": False,
        "escape_success": False,
    }
    gs = _team_state(
        0, "Aegis", crew,
        banked_loot=0,
        round_results=[],
        round_game_ids=[101],
        hiring_game_ids=[100],
        pending_heist=pending,
    )
    _seed_campaign(1, num_rounds=1, current_round_idx=0, current_stage="reflection",
                   game_states=[gs])

    orchestration.run_campaign_conductor(1, 1, resume=True)

    assert calls["job"] == 0, "reflection resume must not re-run the heist"
    with gamestate.lock:
        rec = gamestate.games[1]
        team = rec["game_states"][0]
    assert rec["status"] == "done"
    assert len(team["round_results"]) == 1
    assert team["banked_loot"] == 320_000
    # The caught member is removed from standing crew by settle.
    assert crew[0].id not in _crew_ids(team)
    assert len(_crew_ids(team)) == 3


# ── T010 (US1): recover_games campaign branch ──────────────────────────────────

def _campaign_record(gid, *, status, num_rounds=5, checkpoint_version=None):
    rec = {
        "id": gid,
        "created_at": time.time(),
        "is_campaign": True,
        "status": status,
        "num_rounds": num_rounds,
        "game_states": [],
        "ais_cfg": [],
    }
    if checkpoint_version is not None:
        rec["checkpoint_version"] = checkpoint_version
    return rec


def test_recover_games_resumes_checkpointed_campaign(clean_state, monkeypatch):
    """A running campaign WITH checkpoint_version is scheduled for resume via the
    conductor (resume=True), and its status stays running."""
    resumed: list[tuple] = []
    spawned = threading.Event()

    def spy_conductor(cid, num_rounds, resume=False):
        resumed.append((cid, num_rounds, resume))
        spawned.set()

    monkeypatch.setattr(orchestration, "run_campaign_conductor", spy_conductor)
    monkeypatch.setattr(
        orchestration, "load_game_records",
        lambda: {7: _campaign_record(7, status="running", num_rounds=5,
                                      checkpoint_version=1)},
    )

    orchestration.recover_games()

    assert spawned.wait(timeout=2.0), "expected a resume conductor to be spawned"
    assert resumed == [(7, 5, True)]
    with gamestate.lock:
        assert gamestate.games[7]["status"] == "running"


def test_recover_games_marks_uncheckpointed_campaign_interrupted(clean_state, monkeypatch):
    """A running campaign WITHOUT checkpoint_version predates checkpointing →
    flipped to interrupted, never resumed."""
    resumed: list[tuple] = []
    monkeypatch.setattr(
        orchestration, "run_campaign_conductor",
        lambda *a, **k: resumed.append(a),
    )
    monkeypatch.setattr(
        orchestration, "load_game_records",
        lambda: {8: _campaign_record(8, status="running")},  # no checkpoint_version
    )

    orchestration.recover_games()

    with gamestate.lock:
        assert gamestate.games[8]["status"] == "interrupted"
    assert resumed == []


def test_recover_games_leaves_done_campaign_untouched(clean_state, monkeypatch):
    """A finished campaign is neither resumed nor flipped to interrupted."""
    resumed: list[tuple] = []
    monkeypatch.setattr(
        orchestration, "run_campaign_conductor",
        lambda *a, **k: resumed.append(a),
    )
    monkeypatch.setattr(
        orchestration, "load_game_records",
        lambda: {9: _campaign_record(9, status="done", checkpoint_version=1)},
    )

    orchestration.recover_games()

    with gamestate.lock:
        assert gamestate.games[9]["status"] == "done"
    assert resumed == []
