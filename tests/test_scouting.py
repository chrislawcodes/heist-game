import random

from heist.content import JOBS, ROSTER_BY_ID
from heist.mechanics import free_probe_budget, score_to_bucket
from heist.runner import _run_scout_turn
from heist.scouting import apply_probes, roll_slate_scores
from heist.serialize import scout_state_from_dict, scout_state_to_dict
from heist.state import ChallengeLevel, Crew, RevealLevel, ScoutState
from heist.stub_responses import build_stub_ai


def _slate_scores():
    return roll_slate_scores(list(JOBS), random.Random(0))


def test_roll_slate_scores_covers_every_job_and_active_category():
    scores = _slate_scores()
    assert set(scores) == {j.name for j in JOBS}
    for job in JOBS:
        for cat, level in job.profile.items():
            sc = scores[job.name][cat]
            if level == ChallengeLevel.NONE:
                assert sc == 0
            else:
                # rolled score's bucket matches the published bucket
                assert score_to_bucket(sc) == level


def test_tier_alias_ladder_shifts_fog_band():
    from heist.content import JOBS_BY_NAME
    rng = random.Random(0)
    museum = JOBS_BY_NAME["The Museum Gala"]   # 'easy' -> tier-1 fog
    mint = JOBS_BY_NAME["The Mint"]            # 'elite' -> tier-3 fog
    easy_hard = {roll_slate_scores([museum], rng)[museum.name]["physical"] for _ in range(30)}
    elite_cat = next(k for k, v in mint.profile.items() if v == ChallengeLevel.HARD)
    elite_hard = {roll_slate_scores([mint], rng)[mint.name][elite_cat] for _ in range(30)}
    assert easy_hard == {8}                     # easy: a Hard is reliably an 8
    assert elite_hard <= {9, 10}                # elite: Hards run 9-10


def test_probe_reveals_bucket_then_exact():
    """Two-stage: first probe on a cell reveals its bucket (no exact); a second probe
    reveals the 1-10."""
    scores = {"J": {"physical": 9, "social": 5}}
    ss = ScoutState(free_probes=4)
    # First probe → BUCKET (bucket known, exact not yet).
    e1 = apply_probes(ss, scores, [{"job": "J", "category": "physical"}])
    assert ss.level("J", "physical") == RevealLevel.BUCKET
    assert ss.scouted_score("J", "physical") is None
    assert e1[0]["reveal_level"] == "BUCKET" and e1[0]["bucket"] == "HIGH"
    assert "score" not in e1[0]
    # Second probe on the same cell → EXACT.
    e2 = apply_probes(ss, scores, [{"job": "J", "category": "physical"}])
    assert ss.level("J", "physical") == RevealLevel.EXACT
    assert ss.scouted_score("J", "physical") == 9
    assert e2[0]["reveal_level"] == "EXACT" and e2[0]["score"] == 9
    assert ss.probes_spent_free == 2


def test_probe_budget_caps_and_exact_repeat_is_free_noop():
    scores = {"J": {"physical": 9, "social": 5, "electronic": 8}}
    ss = ScoutState(free_probes=1)
    # 1 free probe: first applies, the rest are dropped (paid overflow deferred).
    events = apply_probes(ss, scores, [
        {"job": "J", "category": "physical"},
        {"job": "J", "category": "social"},
    ])
    assert len(events) == 1
    assert ss.budget_remaining() == 0
    # Take a cell to EXACT (two probes), then a third probe is a free no-op.
    ss2 = ScoutState(free_probes=5)
    apply_probes(ss2, scores, [{"job": "J", "category": "physical"}])  # → BUCKET
    apply_probes(ss2, scores, [{"job": "J", "category": "physical"}])  # → EXACT
    again = apply_probes(ss2, scores, [{"job": "J", "category": "physical"}])  # no-op
    assert again == []
    assert ss2.probes_spent_free == 2
    assert ss2.level("J", "physical") == RevealLevel.EXACT


def test_unknown_job_or_category_is_dropped():
    scores = {"J": {"physical": 9}}
    ss = ScoutState(free_probes=3)
    events = apply_probes(ss, scores, [
        {"job": "Nope", "category": "physical"},
        {"job": "J", "category": "muscle"},   # not a challenge category
        {"job": "J"},                          # malformed
    ])
    assert events == []
    assert ss.probes_spent_free == 0


def test_free_probe_budget_includes_driver_bonus():
    # 4-person crew incl. Slim (High driver) → 4 + 3 = 7.
    crew = [ROSTER_BY_ID[i] for i in (13, 10, 2, 8)]
    assert free_probe_budget(crew) == 7


def test_run_scout_turn_with_stub_emits_events_and_records_intel():
    crew = Crew([ROSTER_BY_ID[i] for i in (13, 10, 2, 8)])
    slate = roll_slate_scores(list(JOBS), random.Random(1))
    ai = build_stub_ai()
    emitted: list[dict] = []
    ss = _run_scout_turn(crew, list(JOBS), slate, ai, [], emitted.append)
    scouted = [e for e in emitted if e.get("type") == "scouted"]
    assert scouted, "stub should have scouted at least one cell"
    # The stub probes each cell once → BUCKET level (bucket known, exact not yet).
    for e in scouted:
        assert e["reveal_level"] == "BUCKET"
        assert "score" not in e
        assert ss.level(e["job"], e["category"]) == RevealLevel.BUCKET
        assert e["bucket"] == score_to_bucket(slate[e["job"]][e["category"]]).name
    assert ss.probes_spent_free == len(scouted)


def test_scout_state_round_trips_through_serialize():
    ss = ScoutState(free_probes=5, probes_spent_free=2)
    ss.reveals.setdefault("J", {})["physical"] = RevealLevel.EXACT
    ss.exact_scores.setdefault("J", {})["physical"] = 9
    back = scout_state_from_dict(scout_state_to_dict(ss))
    assert back.free_probes == 5
    assert back.probes_spent_free == 2
    assert back.scouted_score("J", "physical") == 9
    assert back.level("J", "physical") == RevealLevel.EXACT
