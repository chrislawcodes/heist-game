from heist.state import (
    CHALLENGE_TO_SKILL,
    ChallengeLevel,
    Character,
    Crew,
    SkillLevel,
)


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
    if challenge == ChallengeLevel.NONE:
        return True
    return int(skill_level) >= int(challenge)


def base_cost(total_points: int, num_high: int) -> int:
    base = {2: 200, 3: 400, 4: 800}[total_points]
    return base + 300 * num_high


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
