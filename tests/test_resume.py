"""Tests for ``run_heist``'s snapshot callback and ``resume_heist`` resuming
from each stage of a heist.

We use the existing stub AI (``build_stub_ai``) for deterministic responses
so the test pins behaviour without depending on a real model."""
from __future__ import annotations

import random

import pytest

from heist.content import DEFAULT_PROMPT
from heist.runner import resume_heist, run_heist
from heist.serialize import (
    crew_to_dict,
    state_from_dict,
    state_to_dict,
)
from heist.state import HeistState
from heist.stub_responses import build_stub_ai


@pytest.fixture(autouse=True)
def _no_turn_delay(monkeypatch):
    """Disable inter-turn pacing in resume tests — it's irrelevant here and
    would slow the suite down by orders of magnitude."""
    monkeypatch.setattr("heist.runner.TURN_DELAY_SECONDS", 0.0)


def test_state_roundtrip_is_structurally_equal():
    """state_to_dict → state_from_dict round-trip preserves the state."""
    state, _ = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(42))
    d = state_to_dict(state)
    restored = state_from_dict(d)
    assert isinstance(restored, HeistState)
    assert restored.heat == state.heat
    assert restored.aborted == state.aborted
    assert restored.escape_success == state.escape_success
    assert restored.final_take == state.final_take
    assert restored.job.name == state.job.name
    assert [m.id for m in restored.crew.members] == [m.id for m in state.crew.members]
    assert len(restored.scene_results) == len(state.scene_results)
    assert restored.hidden_depth.element.id == state.hidden_depth.element.id
    assert restored.hidden_depth.reward_amount == state.hidden_depth.reward_amount


def test_snapshots_dont_change_final_outcome():
    """A run with snapshotting ON should produce the same final state as OFF."""
    state_off, _ = run_heist(
        DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(123),
    )

    captured: list[dict] = []
    state_on, _ = run_heist(
        DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(123),
        snapshot_fn=captured.append,
    )

    assert state_off.final_take == state_on.final_take
    assert state_off.aborted == state_on.aborted
    assert state_off.escape_success == state_on.escape_success
    assert len(state_off.scene_results) == len(state_on.scene_results)
    # At minimum: crew_drafted, summary_done, job_picked, len(scenes) in-scene, done.
    assert len(captured) >= 5
    stages = [s["stage"] for s in captured]
    assert "crew_drafted" in stages
    assert "summary_done" in stages
    assert "job_picked" in stages
    assert "in_scene" in stages
    assert stages[-1] == "done"


def _capture_snapshots(seed: int) -> tuple[list[dict], HeistState]:
    captured: list[dict] = []
    state, _ = run_heist(
        DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(seed),
        snapshot_fn=captured.append,
    )
    return captured, state


def test_resume_from_job_picked_completes():
    snaps, baseline = _capture_snapshots(seed=7)
    job_picked = next(s for s in snaps if s["stage"] == "job_picked")

    state, extras = resume_heist(job_picked, build_stub_ai())
    assert state.escape_success is not None
    assert state.job.name == baseline.job.name
    # Final take might differ if RNG state diverges; resume preserves it, so
    # the values should match.
    assert state.final_take == baseline.final_take
    assert extras["epilogue"]  # epilogue was produced


def test_resume_from_summary_done_completes():
    """Resuming from `summary_done` (after casting summary, before job pick)
    runs the rest of the heist."""
    snaps, baseline = _capture_snapshots(seed=7)
    cs = next(s for s in snaps if s["stage"] == "summary_done")

    state, extras = resume_heist(cs, build_stub_ai())
    assert state.final_take == baseline.final_take
    assert state.escape_success == baseline.escape_success
    assert extras["epilogue"]


def test_resume_from_crew_drafted_completes():
    """Resuming from `crew_drafted` (after bid, before summary) runs
    casting_summary + job_pick + scenes + epilogue."""
    snaps, baseline = _capture_snapshots(seed=7)
    cd = next(s for s in snaps if s["stage"] == "crew_drafted")

    state, extras = resume_heist(cd, build_stub_ai())
    assert state.final_take == baseline.final_take
    assert state.escape_success == baseline.escape_success
    assert extras["casting_summary"]
    assert extras["epilogue"]


def test_resume_mid_scene_continues_from_scene_idx():
    snaps, baseline = _capture_snapshots(seed=7)
    # Pick an in_scene snapshot with scene_idx > 0 (the snapshot after scene 0
    # would otherwise read like a fresh casting_summary_done resume).
    in_scene = [s for s in snaps if s["stage"] == "in_scene" and s["scene_idx"] >= 1]
    assert in_scene, "expected at least one in-scene snapshot"
    target = in_scene[len(in_scene) // 2]  # middle one for variety
    expected_scenes_done_at_resume = target["scene_idx"]

    # Build a stub AI and assert it does NOT re-issue the early-stage prompts
    # (bid, job_pick, casting_summary, or earlier scene narrations). It should
    # only see prompts for scenes >= scene_idx, plus the epilogue.
    ai = build_stub_ai()
    state, extras = resume_heist(target, ai)

    seen = ai.prompts_seen
    assert not any("Draft your crew" in p for p in seen), \
        "resume re-issued the bid prompt"
    assert not any("Pick the job this crew" in p for p in seen), \
        "resume re-issued the job_pick prompt"
    assert not any("Now write the casting summary" in p for p in seen), \
        "resume re-issued the casting summary prompt"

    # The final state must reach escape.
    assert state.escape_success is not None
    # We picked up where we left off — scene_results length matches the full run.
    assert len(state.scene_results) == len(baseline.scene_results)
    # Resumed run produces an epilogue.
    assert extras["epilogue"]
    # Sanity: we skipped at least one scene worth of prompts.
    assert expected_scenes_done_at_resume > 0


def test_resume_from_done_does_not_redo_work():
    snaps, baseline = _capture_snapshots(seed=7)
    done = snaps[-1]
    assert done["stage"] == "done"

    ai = build_stub_ai()
    state, extras = resume_heist(done, ai)
    # No fresh AI prompts when resuming from "done" (epilogue was already
    # captured in extras).
    assert ai.prompts_seen == []
    assert state.final_take == baseline.final_take
    assert extras["epilogue"] == "_ no fresh epilogue _" or extras["epilogue"]
    # (We only assert there IS an epilogue — content depends on what was in
    # the snapshot extras, which was set by the original run.)


def test_session_id_carried_into_snapshot():
    """Snapshots pull ``session_id`` off the AI object via getattr. The stub
    doesn't expose it (returning Turn.session_id is enough for its purposes),
    so emulate the real backend's interface by setting it on the AI."""
    ai = build_stub_ai()
    ai.session_id = "test-session-xyz"  # type: ignore[attr-defined]
    captured: list[dict] = []
    run_heist(
        DEFAULT_PROMPT, ai, rng=random.Random(7), snapshot_fn=captured.append,
    )
    assert all(s["session_id"] == "test-session-xyz" for s in captured)


def test_resume_emits_crew_and_job_events():
    """Resuming mid-run should re-emit ``crew_known`` and ``job_known`` so a
    viewer that connects late can still draw the board."""
    snaps, _ = _capture_snapshots(seed=7)
    # Resume from job_picked: state is fully populated, so crew_known AND
    # job_known are both re-emitted.
    jp = next(s for s in snaps if s["stage"] == "job_picked")

    emitted: list[dict] = []
    resume_heist(jp, build_stub_ai(), emit=emitted.append)

    types = [e["type"] for e in emitted]
    assert "crew_known" in types
    assert "job_known" in types


def test_resume_drafting_falls_back_to_fresh_run():
    """A pseudo-snapshot at stage=drafting (or with no state) should restart."""
    snapshot = {
        "stage": "drafting",
        "scene_idx": 0,
        "strategy": DEFAULT_PROMPT,
        "session_id": None,
        "rng_state": None,
        "extras": {},
        "state": None,
    }
    state, extras = resume_heist(snapshot, build_stub_ai())
    assert state.escape_success is not None
    assert extras["casting_summary"]
    assert extras["epilogue"]


def test_rng_state_in_snapshot_is_restorable():
    captured: list[dict] = []
    run_heist(
        DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(99),
        snapshot_fn=captured.append,
    )
    from heist.persist import _deserialize_rng_into
    snap = captured[0]
    rng = random.Random()
    _deserialize_rng_into(rng, snap["rng_state"])
    # Should produce a value without error.
    assert isinstance(rng.random(), float)


def test_snapshot_crew_and_job_match_runner_state():
    """The snapshot's serialized state must round-trip back to the same crew
    and job the runner is actually using."""
    captured: list[dict] = []
    state, _ = run_heist(
        DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(11),
        snapshot_fn=captured.append,
    )
    last = captured[-1]
    snap_state = state_from_dict(last["state"])
    assert snap_state.job.name == state.job.name
    assert [m.id for m in snap_state.crew.members] == [m.id for m in state.crew.members]


def test_snapshot_payload_includes_required_keys():
    captured: list[dict] = []
    run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(3),
              snapshot_fn=captured.append)
    for s in captured:
        assert {"stage", "scene_idx", "session_id", "rng_state",
                "state", "extras"} <= s.keys()


def test_crew_to_dict_round_trip_preserves_ids():
    state, _ = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(1))
    from heist.serialize import crew_from_dict
    d = crew_to_dict(state.crew)
    restored = crew_from_dict(d)
    assert [m.id for m in restored.members] == [m.id for m in state.crew.members]
    assert [m.name for m in restored.members] == [m.name for m in state.crew.members]
