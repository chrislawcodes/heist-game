"""Pure game mechanics — Phase 4 score-based engine.

Skills and challenges carry a true 1-10 score; only the Low/Med/High bucket is
public. Resolution compares true scores. Character scores are public; location
challenge scores are fogged (rolled per round, revealed by scouting).
"""
import enum
import random

from heist.state import (
    CHALLENGE_TO_SKILL,
    ChallengeLevel,
    Character,
    Crew,
    SkillLevel,
)

# ── Buckets ───────────────────────────────────────────────────────────────────
# Score → bucket boundaries (Phase 4): 0 None, 1-3 Low, 4-7 Medium, 8-10 High.


def score_to_bucket(score: int) -> SkillLevel:
    if score <= 0:
        return SkillLevel.NONE
    if score <= 3:
        return SkillLevel.LOW
    if score <= 7:
        return SkillLevel.MEDIUM
    return SkillLevel.HIGH


# A bucket-only character (legacy/test fixtures with no skill_scores) gets a
# canonical mid-bucket score. Real roster characters carry explicit scores.
_BUCKET_SCORE = {SkillLevel.LOW: 2, SkillLevel.MEDIUM: 5, SkillLevel.HIGH: 9}


def _member_score(member: Character, skill: str) -> int:
    score = member.skill_scores.get(skill, 0)
    if score:
        return score
    return _BUCKET_SCORE.get(member.skills.get(skill, SkillLevel.NONE), 0)


# ── Outcomes ────────────────────────────────────────────────────────────────


class Outcome(enum.Enum):
    CLEAN = enum.auto()
    SQUEAK = enum.auto()
    FAIL = enum.auto()
    CAUGHT = enum.auto()


def resolve_by_margin(eff_score: int, challenge_score: int) -> Outcome:
    """Graded outcome from the score margin (Phase 4, supersedes the bucket gap).

    margin = eff_score - challenge_score
      >= 2  CLEAN              (comfortable)
      0..1  SQUEAK  (+1 heat)  (barely made it)
      -1..-3 FAIL    (+1 heat)
      <= -4 CAUGHT   (+1 heat, lose the lead member)
    Bands are wider than the 3-bucket model because the scale is finer; the heat
    cascade stays steep (any non-clean costs +1 heat).
    """
    if challenge_score <= 0:
        return Outcome.CLEAN
    margin = eff_score - challenge_score
    if margin >= 2:
        return Outcome.CLEAN
    if margin >= 0:
        return Outcome.SQUEAK
    if margin >= -3:
        return Outcome.FAIL
    return Outcome.CAUGHT


def outcome_is_pass(outcome: Outcome) -> bool:
    return outcome in (Outcome.CLEAN, Outcome.SQUEAK)


# ── Effective skill ─────────────────────────────────────────────────────────


def effective_skill_score(members: list[Character], skill: str) -> int:
    """Crew's effective 1-10 score in a skill. Two+ members with the skill
    collaborate at best + 1 (capped 10). No member with the skill → 0."""
    scores = [s for s in (_member_score(m, skill) for m in members) if s > 0]
    if not scores:
        return 0
    best = max(scores)
    if len(scores) >= 2:
        best = min(10, best + 1)
    return best


def effective_skill_bucket(members: list[Character], skill: str) -> SkillLevel:
    return score_to_bucket(effective_skill_score(members, skill))


# Back-compat name: callers that want the public bucket (escape, viability).
def effective_skill(members: list[Character], skill: str) -> SkillLevel:
    return effective_skill_bucket(members, skill)


# ── Pricing (score-based convex curve) ──────────────────────────────────────

SEAT_COST = 100_000
SKILL_PREMIUM = {
    # Low skills cost a little now (kept under the Med-4 rung to stay monotonic).
    1: 10_000, 2: 15_000, 3: 20_000,
    4: 25_000, 5: 50_000, 6: 100_000, 7: 175_000,
    8: 325_000, 9: 600_000, 10: 1_100_000,
}


def skill_premium(score: int) -> int:
    return SKILL_PREMIUM.get(score, 0)


def score_floor_cost(char: Character) -> int:
    """$100k seat + Σ premium(score). Premium accelerates at the top so an
    8→9→10 step costs far more than 6→7."""
    return SEAT_COST + sum(skill_premium(s) for s in char.skill_scores.values())


# ── Hidden challenge scores (rolled per round) ──────────────────────────────
# Tier shifts where in the bucket the true score lands: higher tier = harder.

_TIER_BANDS: dict[tuple[ChallengeLevel, str], list[int]] = {
    (ChallengeLevel.LOW, "1"): [1, 2],
    (ChallengeLevel.LOW, "2"): [2, 3],
    (ChallengeLevel.LOW, "3"): [3],
    (ChallengeLevel.MEDIUM, "1"): [4, 5],
    (ChallengeLevel.MEDIUM, "2"): [5, 6],
    (ChallengeLevel.MEDIUM, "3"): [6, 7],
    (ChallengeLevel.HARD, "1"): [8],
    (ChallengeLevel.HARD, "2"): [8, 9],
    (ChallengeLevel.HARD, "3"): [9, 10],
}
_FULL_BAND = {
    ChallengeLevel.LOW: [1, 2, 3],
    ChallengeLevel.MEDIUM: [4, 5, 6, 7],
    ChallengeLevel.HARD: [8, 9, 10],
}


# Map the authored tier names to fog-band tiers (1 = easiest end of each bucket,
# 3 = hardest). A Tier-1 "Hard" reliably rolls an 8; a Tier-3 "Hard" rolls 9-10.
_TIER_ALIASES = {
    "easy": "1", "medium": "2", "hard": "3", "elite": "3",
    "1": "1", "2": "2", "3": "3",
}


def _norm_tier(tier: str) -> str:
    return _TIER_ALIASES.get(tier, "2")


def roll_one_score(level: ChallengeLevel, tier: str, rng: random.Random) -> int:
    """Roll a single hidden 1-10 score from a bucket × tier band."""
    if level == ChallengeLevel.NONE:
        return 0
    band = _TIER_BANDS.get((level, _norm_tier(tier))) or _FULL_BAND[level]
    return rng.choice(band)


def roll_challenge_scores(
    profile: dict[str, ChallengeLevel],
    tier: str,
    rng: random.Random,
) -> dict[str, int]:
    """Roll a hidden 1-10 score for each active challenge from its bucket × tier band."""
    return {cat: roll_one_score(level, tier, rng) for cat, level in profile.items()}


# ── Scouting capacity ───────────────────────────────────────────────────────


def driver_scout_bonus(members: list[Character]) -> int:
    """+1/+2/+3 free probes for a Low/Med/High best driver (single best, not
    collaboration-boosted); +0 with no driver."""
    best = max((_member_score(m, "driver") for m in members), default=0)
    return {
        SkillLevel.NONE: 0,
        SkillLevel.LOW: 1,
        SkillLevel.MEDIUM: 2,
        SkillLevel.HIGH: 3,
    }[score_to_bucket(best)]


def free_probe_budget(members: list[Character]) -> int:
    """Free scouting probes per team per round.

    Feature 003: ``len(crew) + best driver's 1–10 skill score`` (0 if no driver).

    Varies per team and rewards investment in both crew size and driver skill:
      • 4-crew with a High driver (score ~9) → 4 + 9 = 13 probes.
      • 4-crew with no driver               → 4 + 0 = 4 probes.
      • 6-crew with a Medium driver (~6)    → 6 + 6 = 12 probes.

    Pairs with the new fewest-probes-first pick order (US2): teams that field a
    big crew with a strong driver get more scouting capacity AND pay for it in
    later pick order if they actually use it.
    """
    best_driver = max((_member_score(m, "driver") for m in members), default=0)
    return len(members) + best_driver


# ── Escape (derived difficulty; driver score contest) ───────────────────────


def escape_base(profile: dict) -> int:
    """Escape difficulty (0–6) derived from how defended the job is.
    Sum the four challenge levels (NONE=0, LOW=1, MEDIUM=2, HARD=3 → 0–12),
    halve (round up), cap at 6. Harder jobs trend toward 6."""
    total = sum(int(lvl) for lvl in profile.values())
    return min(6, (total + 1) // 2)


def escape_resolves(crew: Crew, heat: int, escape_base: int) -> tuple[bool, int]:
    """Returns (success, difficulty). difficulty = escape_base + heat.
    Best Driver's effective 1–10 score (0 if no driver) must be ≥ difficulty."""
    difficulty = escape_base + heat
    driver_score = effective_skill_score(crew.members, "driver")
    return driver_score >= difficulty, difficulty


def job_is_viable(crew: Crew, job_profile: dict[str, ChallengeLevel]) -> bool:
    """Bucket-level 'looks attemptable' hint for the AI's job pick (true
    resolution uses scores): crew covers every Hard challenge at High bucket."""
    for challenge_category, level in job_profile.items():
        if level == ChallengeLevel.HARD:
            skill = CHALLENGE_TO_SKILL[challenge_category]
            if effective_skill_bucket(crew.members, skill) < ChallengeLevel.HARD:
                return False
    return True
