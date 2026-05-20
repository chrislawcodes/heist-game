import enum

from heist.state import (
    CHALLENGE_TO_SKILL,
    ChallengeLevel,
    Character,
    Crew,
    SkillLevel,
)


class Outcome(enum.Enum):
    CLEAN = enum.auto()
    SQUEAK = enum.auto()
    FAIL = enum.auto()
    CAUGHT = enum.auto()


def resolve_outcome(skill: SkillLevel, challenge: ChallengeLevel) -> Outcome:
    if challenge == ChallengeLevel.NONE:
        return Outcome.CLEAN
    gap = int(challenge) - int(skill)
    if gap < 0:
        return Outcome.CLEAN
    if gap == 0:
        return Outcome.SQUEAK
    if gap == 1:
        return Outcome.FAIL
    return Outcome.CAUGHT


def outcome_is_pass(outcome: Outcome) -> bool:
    return outcome in (Outcome.CLEAN, Outcome.SQUEAK)


def effective_skill(members: list[Character], skill: str) -> SkillLevel:
    """Crew's effective level in a skill. Two+ members with the skill collaborate
    (highest level + 1, capped at HIGH). Single member = their level."""
    levels = [m.skills.get(skill, SkillLevel.NONE) for m in members]
    levels = [lvl for lvl in levels if lvl != SkillLevel.NONE]
    if not levels:
        return SkillLevel.NONE
    if len(levels) == 1:
        return levels[0]
    highest = max(levels)
    return SkillLevel(min(int(SkillLevel.HIGH), int(highest) + 1))


def resolves_challenge(skill_level: SkillLevel, challenge: ChallengeLevel) -> bool:
    """Bucket-level resolution: crew skill >= challenge level → success.

    PHASE 4 NOTE: This function will be superseded when hidden scores ship.
    Phase 4 resolution is: Character.skill_scores[skill] >= Job.challenge_scores[category].
    Both fields are intentionally empty until then — do NOT implement score
    resolution here before Phase 4 (scouting must ship at the same time, or
    the hidden scores are just random noise the player can't do anything about).
    """
    if challenge == ChallengeLevel.NONE:
        return True
    return int(skill_level) >= int(challenge)


def base_cost(total_points: int, num_high: int) -> int:
    base = {2: 200_000, 3: 400_000, 4: 800_000}[total_points]
    return base + 300_000 * num_high


def expected_floor_cost(char: Character) -> int:
    total = sum(int(lvl) for lvl in char.skills.values())
    num_high = sum(1 for lvl in char.skills.values() if lvl == SkillLevel.HIGH)
    return base_cost(total, num_high)


def escape_resolves(crew: Crew, heat: int, escape_modifier: int) -> tuple[bool, int]:
    """Returns (success, difficulty). Difficulty = escape_modifier + heat.
    Best Driver skill (no Driver = treated as Low). success = driver >= difficulty."""
    difficulty = escape_modifier + heat
    driver = effective_skill(crew.members, "driver")
    if driver == SkillLevel.NONE:
        driver = SkillLevel.LOW
    return int(driver) >= difficulty, difficulty


def job_is_viable(crew: Crew, job_profile: dict[str, ChallengeLevel]) -> bool:
    """True iff the crew can credibly attempt the job (covers every Hard challenge)."""
    for challenge_category, level in job_profile.items():
        if level == ChallengeLevel.HARD:
            skill = CHALLENGE_TO_SKILL[challenge_category]
            if effective_skill(crew.members, skill) < ChallengeLevel.HARD:
                return False
    return True
