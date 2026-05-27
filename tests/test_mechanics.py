import random

from heist.content import ROSTER
from heist.mechanics import (
    Outcome,
    driver_scout_bonus,
    effective_skill_score,
    escape_resolves,
    free_probe_budget,
    job_is_viable,
    resolve_by_margin,
    roll_challenge_scores,
    score_floor_cost,
    score_to_bucket,
)
from heist.state import ChallengeLevel, Character, Crew, SkillLevel


def _char(name, scores):
    """Build a character from 1-10 scores; buckets derived to stay consistent."""
    skills = {k: score_to_bucket(v) for k, v in scores.items()}
    return Character(id=999, name=name, skills=skills, skill_scores=scores, floor_cost=0)


# ── effective skill score (+1 point collaboration) ──────────────────────────


def test_effective_score_solo():
    assert effective_skill_score([_char("a", {"hacker": 5})], "hacker") == 5


def test_effective_score_no_one_has_it():
    assert effective_skill_score([_char("a", {"hacker": 5})], "muscle") == 0


def test_collaboration_adds_one_point():
    a = _char("a", {"hacker": 6})
    b = _char("b", {"hacker": 5})
    assert effective_skill_score([a, b], "hacker") == 7  # best 6, +1


def test_collaboration_capped_at_ten():
    a = _char("a", {"muscle": 10})
    b = _char("b", {"muscle": 9})
    assert effective_skill_score([a, b], "muscle") == 10


def test_two_mediums_may_or_may_not_reach_high():
    # 7+1 = 8 (High); 5+1 = 6 (still Medium) — collaboration is +1 POINT now.
    hi = [_char("a", {"inside_man": 7}), _char("b", {"inside_man": 6})]
    lo = [_char("a", {"safecracker": 5}), _char("b", {"safecracker": 5})]
    assert score_to_bucket(effective_skill_score(hi, "inside_man")) == SkillLevel.HIGH
    assert score_to_bucket(effective_skill_score(lo, "safecracker")) == SkillLevel.MEDIUM


# ── buckets ─────────────────────────────────────────────────────────────────


def test_score_to_bucket_boundaries():
    assert score_to_bucket(0) == SkillLevel.NONE
    assert score_to_bucket(3) == SkillLevel.LOW
    assert score_to_bucket(4) == SkillLevel.MEDIUM
    assert score_to_bucket(7) == SkillLevel.MEDIUM
    assert score_to_bucket(8) == SkillLevel.HIGH
    assert score_to_bucket(10) == SkillLevel.HIGH


# ── graded outcomes by margin ───────────────────────────────────────────────


def test_resolve_by_margin_bands():
    assert resolve_by_margin(10, 8) is Outcome.CLEAN     # margin +2
    assert resolve_by_margin(9, 8) is Outcome.SQUEAK     # margin +1
    assert resolve_by_margin(8, 8) is Outcome.SQUEAK     # margin 0
    assert resolve_by_margin(7, 8) is Outcome.FAIL       # margin -1
    assert resolve_by_margin(5, 8) is Outcome.FAIL       # margin -3
    assert resolve_by_margin(4, 8) is Outcome.CAUGHT     # margin -4
    assert resolve_by_margin(3, 9) is Outcome.CAUGHT     # margin -6
    assert resolve_by_margin(2, 0) is Outcome.CLEAN      # no challenge


# ── pricing curve ───────────────────────────────────────────────────────────


def test_every_roster_member_matches_pricing_curve():
    for c in ROSTER:
        assert c.floor_cost == score_floor_cost(c), (
            f"{c.name}: floor {c.floor_cost} ≠ curve {score_floor_cost(c)}"
        )


def test_pricing_curve_examples():
    assert score_floor_cost(_char("rook", {"safecracker": 9})) == 700_000
    # Low skills now cost $10/$15/$20k for scores 1/2/3 (Marcus' driver-2 adds $15k).
    assert score_floor_cost(_char("marcus", {"hacker": 10, "driver": 2})) == 1_215_000
    assert score_floor_cost(_char("vance", {"muscle": 8})) == 425_000
    assert score_floor_cost(_char("eli", {"hacker": 2, "inside_man": 3})) == 135_000


def test_low_skill_premiums():
    # $100k seat + Low premiums (1->10k, 2->15k, 3->20k), kept under the Med-4 rung.
    assert score_floor_cost(_char("a", {"hacker": 1})) == 110_000
    assert score_floor_cost(_char("b", {"hacker": 2})) == 115_000
    assert score_floor_cost(_char("c", {"hacker": 3})) == 120_000
    assert score_floor_cost(_char("d", {"hacker": 4})) == 125_000  # Med-4 still > Low-3


# ── rolled challenge scores stay in tier band ───────────────────────────────


def test_roll_challenge_scores_respects_tier_bands():
    rng = random.Random(0)
    profile = {"physical": ChallengeLevel.HARD, "social": ChallengeLevel.MEDIUM}
    for _ in range(50):
        t1 = roll_challenge_scores(profile, "1", rng)
        t3 = roll_challenge_scores(profile, "3", rng)
        assert t1["physical"] == 8           # Tier-1 Hard is always an 8
        assert t3["physical"] in (9, 10)     # Tier-3 Hard rolls 9-10
        assert 4 <= t1["social"] <= 7


# ── escape (bucket-resolved; collaboration is +1 point) ─────────────────────


def test_escape_high_driver_clears_heat_three():
    crew = Crew(members=[_char("slim", {"driver": 9})])
    success, diff = escape_resolves(crew, heat=3, escape_modifier=0)
    assert success is True and diff == 3


def test_escape_no_driver_treated_as_low():
    crew = Crew(members=[_char("nobody", {"muscle": 5})])
    ok_low, _ = escape_resolves(crew, heat=1, escape_modifier=0)
    fail_hi, _ = escape_resolves(crew, heat=2, escape_modifier=0)
    assert ok_low is True and fail_hi is False


def test_escape_two_top_mediums_collaborate_to_high():
    crew = Crew(members=[_char("a", {"driver": 7}), _char("b", {"driver": 6})])
    # 7 + 1 = 8 → High bucket → clears heat 3.
    ok, _ = escape_resolves(crew, heat=3, escape_modifier=0)
    assert ok is True


# ── scouting capacity ───────────────────────────────────────────────────────


def test_driver_scout_bonus_by_bucket():
    assert driver_scout_bonus([_char("a", {"driver": 9})]) == 3
    assert driver_scout_bonus([_char("a", {"driver": 5})]) == 2
    assert driver_scout_bonus([_char("a", {"driver": 2})]) == 1
    assert driver_scout_bonus([_char("a", {"muscle": 9})]) == 0


def test_free_probe_budget_is_crew_plus_driver_bonus():
    crew = [_char("a", {"driver": 9}), _char("b", {"muscle": 6})]
    assert free_probe_budget(crew) == 2 + 3


# ── viability hint (bucket-based) ───────────────────────────────────────────


def test_job_viable_requires_hard_coverage():
    no_high = Crew(members=[_char("a", {"safecracker": 6})])
    with_high = Crew(members=[_char("a", {"safecracker": 9})])
    profile = {
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.NONE,
        "social": ChallengeLevel.NONE,
    }
    assert job_is_viable(no_high, profile) is False
    assert job_is_viable(with_high, profile) is True
