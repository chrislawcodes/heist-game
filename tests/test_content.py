from heist.content import JOBS, ROSTER, ROSTER_BY_ID
from heist.state import SkillLevel


def test_roster_size_and_uniqueness():
    assert len(ROSTER) == 16
    ids = [c.id for c in ROSTER]
    assert len(set(ids)) == 16
    names = [c.name for c in ROSTER]
    assert len(set(names)) == 16


def test_roster_by_id_matches():
    for c in ROSTER:
        assert ROSTER_BY_ID[c.id] is c


def test_no_character_is_single_low_skill():
    """Pure single-Low (1pt) characters are explicitly disallowed by design."""
    for c in ROSTER:
        total = sum(int(lvl) for lvl in c.skills.values())
        if len(c.skills) == 1 and total == 1:
            raise AssertionError(f"{c.name} is a forbidden 1-point single-Low character")


def test_total_skill_points_in_range():
    for c in ROSTER:
        total = sum(int(lvl) for lvl in c.skills.values())
        assert 2 <= total <= 4, f"{c.name} has {total} skill points"


def test_each_primary_skill_has_at_least_three_specialists():
    """Each skill needs at least 3 primaries for 2-player collaboration math to work.
    Roster is 16 chars; muscle has 4 primaries (Vance H, Carla M, Val Cruz M, Big Mike L)."""
    primaries: dict[str, int] = {}
    for c in ROSTER:
        if not c.skills:
            continue
        # The character's "primary" is the skill with the highest level (ties → first listed).
        top_skill = max(c.skills.items(), key=lambda kv: int(kv[1]))[0]
        primaries[top_skill] = primaries.get(top_skill, 0) + 1
    for skill in ("hacker", "muscle", "inside_man", "safecracker", "driver"):
        assert primaries.get(skill, 0) >= 3, f"{skill}: {primaries.get(skill, 0)} primaries"


def test_seven_jobs_present():
    assert len(JOBS) == 7
    names = {j.name for j in JOBS}
    assert names == {
        "The Museum Gala",
        "The Armored Car",
        "The Corporate Server Farm",
        "The Penthouse Caper",
        "The Cargo Yard",
        "The Diplomatic Reception",
        "The Casino Vault",
    }


def test_each_job_has_hidden_depth_and_rewards():
    for j in JOBS:
        assert 4 <= len(j.hidden_depth) <= 6
        assert 2 <= len(j.reward_amounts) <= 3
        for label, amount in j.reward_amounts:
            assert j.reward_range[0] <= amount <= j.reward_range[1], (
                f"{j.name}: reward {amount} ({label}) outside range {j.reward_range}"
            )


def test_job_slate_has_difficulty_spread():
    """The slate must include at least one job with no Hards (easy entry),
    and at least one with two or more Hards (premium). This is what makes
    'pick the job whose profile fits the crew' a real strategic question."""
    from heist.state import ChallengeLevel

    def hard_count(j):
        return sum(1 for v in j.profile.values() if v == ChallengeLevel.HARD)

    counts = [hard_count(j) for j in JOBS]
    assert 0 in counts, "no easy (zero-Hard) job in slate"
    assert any(c >= 2 for c in counts), "no premium (≥2 Hards) job in slate"


# Note: the design doc's "Inside Man has no Low option — premium skill" comment
# contradicts the roster table itself, which lists Low Inside Man on several characters
# as a secondary skill. We preserve the table as authoritative; this test pins the
# current set so it surfaces if membership changes unexpectedly.
# Current LOW inside_man holders: Eli (3), Big Mike (6), Margot (14), Val Cruz (16).
def test_low_inside_man_holders():
    low_inside_ids = sorted(
        c.id for c in ROSTER
        if c.skills.get("inside_man", SkillLevel.NONE) == SkillLevel.LOW
    )
    assert low_inside_ids == [3, 6, 14, 16]
