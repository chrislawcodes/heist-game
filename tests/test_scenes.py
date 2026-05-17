from heist.content import ARMORED_CAR, MUSEUM, SERVER_FARM
from heist.scenes import generate_scenes
from heist.state import ChallengeLevel, HiddenDepthRoll


def _roll(job, element_id, reward_idx=0):
    el = next(e for e in job.hidden_depth if e.id == element_id)
    label, amount = job.reward_amounts[reward_idx]
    return HiddenDepthRoll(element=el, reward_label=label, reward_amount=amount)


def test_setup_first_escape_last_transition_penultimate():
    scenes = generate_scenes(MUSEUM, _roll(MUSEUM, "museum_prince_security"))
    assert scenes[0].type == "setup"
    assert scenes[-1].type == "escape"
    assert scenes[-2].type == "transition"


def test_modifies_does_not_add_scene_but_attaches_context():
    # museum_biometric: electronic Medium → Hard (in-place)
    scenes = generate_scenes(MUSEUM, _roll(MUSEUM, "museum_biometric"))
    # The Museum profile has electronic Medium; after the bump, electronic Hard.
    electronic_scene = next(
        s for s in scenes if s.challenge_skill == "hacker"
    )
    assert electronic_scene.challenge_level == ChallengeLevel.HARD
    assert electronic_scene.is_core is True
    assert "Hidden depth" in electronic_scene.context


def test_adds_creates_new_scene():
    # museum_off_duty_detective: adds Social Medium
    scenes = generate_scenes(MUSEUM, _roll(MUSEUM, "museum_off_duty_detective"))
    hidden_scenes = [s for s in scenes if s.type == "hidden_depth"]
    assert len(hidden_scenes) == 1
    assert hidden_scenes[0].challenge_skill == "inside_man"


def test_bonus_with_cost_creates_decision_scene():
    # museum_emerald_necklace: bonus_with_cost
    scenes = generate_scenes(MUSEUM, _roll(MUSEUM, "museum_emerald_necklace"))
    decisions = [s for s in scenes if s.type == "decision"]
    assert len(decisions) == 1
    assert decisions[0].is_core is False
    assert "Bonus opportunity" in decisions[0].context


def test_hard_challenges_marked_core():
    scenes = generate_scenes(MUSEUM, _roll(MUSEUM, "museum_prince_security"))
    core_scenes = [s for s in scenes if s.is_core]
    # Museum has Physical Hard + Social Hard
    skills = sorted(s.challenge_skill for s in core_scenes)
    assert "inside_man" in skills
    assert "safecracker" in skills


def test_armored_car_canonical_order():
    scenes = generate_scenes(ARMORED_CAR, _roll(ARMORED_CAR, "armored_rookie_guard"))
    # Profile: electronic LOW (folded), physical MEDIUM, confrontation HARD (rookie → MEDIUM)
    challenge_skills = [s.challenge_skill for s in scenes if s.type == "challenge"]
    # canonical: social → electronic → physical → confrontation;
    # social NONE, electronic LOW (skipped), so just physical then confrontation
    assert challenge_skills == ["safecracker", "muscle"]


def test_server_farm_default():
    scenes = generate_scenes(SERVER_FARM, _roll(SERVER_FARM, "server_shift_change"))
    challenge_skills = [s.challenge_skill for s in scenes if s.type == "challenge"]
    # server farm: social MED, electronic HARD, physical MED, confrontation LOW (folded);
    # shift_change modifies confrontation to MEDIUM (so it shows up now too)
    assert "hacker" in challenge_skills
    assert "safecracker" in challenge_skills
    assert "inside_man" in challenge_skills
    assert "muscle" in challenge_skills  # bumped to medium by hidden depth
