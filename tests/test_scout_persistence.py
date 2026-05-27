"""Persistent scouting (spec 002): locked campaign scores + carried-forward
per-team scout memory, serialize/resume-safe."""
import copy
import random

from heist.campaign import run_campaign
from heist.content import DEFAULT_PROMPT
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
