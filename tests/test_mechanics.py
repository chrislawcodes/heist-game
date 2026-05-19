from heist.content import ROSTER
from heist.mechanics import (
    base_cost,
    effective_skill,
    escape_resolves,
    expected_floor_cost,
    job_is_viable,
    resolves_challenge,
)
from heist.state import ChallengeLevel, Crew, SkillLevel


def _char(name, skills, cost=0):
    from heist.state import Character
    return Character(id=999, name=name, skills=skills, floor_cost=cost)


def test_effective_skill_solo():
    a = _char("a", {"hacker": SkillLevel.MEDIUM})
    assert effective_skill([a], "hacker") == SkillLevel.MEDIUM


def test_effective_skill_no_one_has_it():
    a = _char("a", {"hacker": SkillLevel.MEDIUM})
    assert effective_skill([a], "muscle") == SkillLevel.NONE


def test_collaboration_low_plus_low_is_medium():
    a = _char("a", {"hacker": SkillLevel.LOW})
    b = _char("b", {"hacker": SkillLevel.LOW})
    assert effective_skill([a, b], "hacker") == SkillLevel.MEDIUM


def test_collaboration_medium_plus_medium_is_high():
    a = _char("a", {"inside_man": SkillLevel.MEDIUM})
    b = _char("b", {"inside_man": SkillLevel.MEDIUM})
    assert effective_skill([a, b], "inside_man") == SkillLevel.HIGH


def test_collaboration_capped_at_high():
    a = _char("a", {"muscle": SkillLevel.HIGH})
    b = _char("b", {"muscle": SkillLevel.HIGH})
    assert effective_skill([a, b], "muscle") == SkillLevel.HIGH


def test_resolves_challenge_pass_and_fail():
    assert resolves_challenge(SkillLevel.HIGH, ChallengeLevel.HARD) is True
    assert resolves_challenge(SkillLevel.MEDIUM, ChallengeLevel.HARD) is False
    assert resolves_challenge(SkillLevel.NONE, ChallengeLevel.LOW) is False
    assert resolves_challenge(SkillLevel.NONE, ChallengeLevel.NONE) is True


def test_base_cost_table():
    assert base_cost(2, 0) == 200
    assert base_cost(3, 0) == 400
    assert base_cost(3, 1) == 700
    assert base_cost(4, 1) == 1100
    assert base_cost(4, 2) == 1400


def test_every_roster_member_has_correct_floor_cost():
    for c in ROSTER:
        assert c.floor_cost == expected_floor_cost(c), (
            f"{c.name}: floor {c.floor_cost} ≠ expected {expected_floor_cost(c)}"
        )


def test_escape_with_driver_high_clears_heat_three():
    crew = Crew(members=[_char("slim", {"driver": SkillLevel.HIGH})])
    success, diff = escape_resolves(crew, heat=3, escape_modifier=0)
    assert success is True
    assert diff == 3


def test_escape_with_no_driver_treated_as_low():
    crew = Crew(members=[_char("nobody", {"muscle": SkillLevel.MEDIUM})])
    ok_low_heat, _ = escape_resolves(crew, heat=1, escape_modifier=0)
    fail_high_heat, _ = escape_resolves(crew, heat=2, escape_modifier=0)
    assert ok_low_heat is True
    assert fail_high_heat is False


def test_escape_uses_collaboration_bonus():
    crew = Crew(members=[
        _char("a", {"driver": SkillLevel.MEDIUM}),
        _char("b", {"driver": SkillLevel.MEDIUM}),
    ])
    # Two Medium drivers = effective High. Should clear heat=3.
    ok, _ = escape_resolves(crew, heat=3, escape_modifier=0)
    assert ok is True


def test_job_viable_requires_hard_coverage():
    crew_no_high = Crew(members=[_char("a", {"safecracker": SkillLevel.MEDIUM})])
    crew_with_high = Crew(members=[_char("a", {"safecracker": SkillLevel.HIGH})])
    profile = {
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.NONE,
        "social": ChallengeLevel.NONE,
    }
    assert job_is_viable(crew_no_high, profile) is False
    assert job_is_viable(crew_with_high, profile) is True
