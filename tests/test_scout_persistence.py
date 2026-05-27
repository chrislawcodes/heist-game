"""Persistent scouting (spec 002): locked campaign scores + carried-forward
per-team scout memory, serialize/resume-safe."""
import copy
import random

from heist.campaign import run_campaign
from heist.content import DEFAULT_PROMPT
from heist.state import Campaign
from heist.stub_responses import build_stub_ai


def _run(rounds: int):
    """Run a stub campaign, capturing a per-round snapshot of the locked scores
    and the picked job's recorded challenge scores + scout reveals."""
    snaps: list[dict] = []
    picks: list[tuple[str, dict]] = []
    reveals: list[dict] = []

    def on_round(camp, state, extras):
        snaps.append(copy.deepcopy(camp.slate_scores))
        picks.append((state.job.name, dict(state.challenge_scores)))
        reveals.append(copy.deepcopy(state.scout_state.exact_scores))

    campaign, _ = run_campaign(
        DEFAULT_PROMPT, build_stub_ai(), rounds=rounds,
        rng=random.Random(7), on_round=on_round,
    )
    return campaign, snaps, picks, reveals


# ── US1: locked scores per campaign ──────────────────────────────────────────

def test_locked_scores_identical_across_rounds():
    """SC-001: a job's hidden scores are rolled once and never change round-to-round."""
    campaign, snaps, _picks, _reveals = _run(rounds=3)
    assert len(snaps) >= 2, "need at least two rounds to compare"
    assert snaps[0], "slate_scores must be populated after round 1"
    for later in snaps[1:]:
        assert later == snaps[0], "locked scores must not change between rounds"


def test_working_scores_are_a_copy_of_locked():
    """run_one_job hands the scene loop a COPY of the locked scores, so the in-run
    heat cascade (which raises difficulty) can't ratchet the campaign's locked slate
    upward every round."""
    shared: list[bool] = []

    def on_round(camp, state, extras):
        shared.append(state.challenge_scores is camp.slate_scores.get(state.job.name))

    run_campaign(
        DEFAULT_PROMPT, build_stub_ai(), rounds=2,
        rng=random.Random(7), on_round=on_round,
    )
    assert shared and not any(shared), "working scores must be a separate dict from the lock"


def test_scouted_value_equals_locked_value():
    """A scouted cell reveals the locked value (no divergence)."""
    campaign, _snaps, _picks, reveals = _run(rounds=2)
    saw_any = False
    for round_reveals in reveals:
        for job, cats in round_reveals.items():
            for cat, score in cats.items():
                saw_any = True
                assert score == campaign.slate_scores[job][cat]
    assert saw_any, "stub crew should have scouted at least one cell"


# ── US2: scouting stays scouted ──────────────────────────────────────────────

def _run_capturing(rounds: int):
    """Run a stub campaign, capturing emitted events segmented per round plus a
    per-round snapshot of the team's (accumulating) scout memory."""
    events: list[dict] = []
    bounds: list[int] = []
    snaps: list[dict] = []

    def before_round(_idx):
        bounds.append(len(events))

    def on_round(camp, state, extras):
        snaps.append(copy.deepcopy(camp.scout_state.exact_scores))

    campaign, _ = run_campaign(
        DEFAULT_PROMPT, build_stub_ai(), rounds=rounds,
        rng=random.Random(7), emit=events.append,
        before_round=before_round, on_round=on_round,
    )
    bounds.append(len(events))
    per_round = [events[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]
    return campaign, snaps, per_round


def _cells(exact_scores: dict) -> set:
    return {(j, c) for j, cats in exact_scores.items() for c in cats}


def test_reveals_carry_forward_across_rounds():
    """SC-002: cells known after round 0 are still known after round 1."""
    _campaign, snaps, _per_round = _run_capturing(rounds=2)
    assert len(snaps) >= 2
    assert _cells(snaps[0]), "stub should scout at least one cell in round 0"
    assert _cells(snaps[0]) <= _cells(snaps[1]), "round-0 reveals must persist into round 1"


def test_carried_scouted_events_reemitted_each_round():
    """FR-007: round 1's stream re-emits round-0's known cells (carried=True)."""
    _campaign, snaps, per_round = _run_capturing(rounds=2)
    carried = {
        (e["job"], e["category"])
        for e in per_round[1]
        if e.get("type") == "scouted" and e.get("carried")
    }
    assert _cells(snaps[0]) <= carried, "round 1 must re-emit round-0's known cells"


def test_reprobing_known_cells_spends_no_new_reveal():
    """SC-004 / FR-006: the stub re-probes the same cells each round; in round 1
    those are already known, so round 1 produces only carried (no new) reveals."""
    _campaign, _snaps, per_round = _run_capturing(rounds=2)
    fresh = [
        e for e in per_round[1]
        if e.get("type") == "scouted" and not e.get("carried")
    ]
    assert fresh == [], f"re-probing known cells should yield no new reveals, got {fresh}"


def test_per_team_scout_memory_is_independent():
    """SC-005: each team's Campaign carries its own scout memory (no cross-talk)."""
    a = Campaign(rounds_total=3, bankroll=0, banked_loot=0)
    b = Campaign(rounds_total=3, bankroll=0, banked_loot=0)
    assert a.scout_state is not b.scout_state
    a.scout_state.exact_scores.setdefault("Museum", {})["physical"] = 8
    assert b.scout_state.exact_scores == {}
