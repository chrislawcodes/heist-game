"""Pin the in-fiction tradecraft text inside the prompts. If a future edit
strips the collaboration rule or the 'Hard needs High' teaching out, CI
catches it before the next run regresses to the pre-Option-B behavior."""

from heist.content import MUSEUM
from heist.prompts import (
    _TRADECRAFT,
    _bid_prompt,
    _job_prompt,
    _scene_assign_prompt,
)
from heist.scenes import generate_scenes
from heist.state import (
    Character,
    Crew,
    HeistState,
    HiddenDepthRoll,
    SkillLevel,
)


def test_tradecraft_block_teaches_collaboration():
    text = _TRADECRAFT
    assert "pair" in text.lower()
    assert "two mediums" in text.lower()
    assert "one level higher" in text.lower()


def test_tradecraft_block_teaches_hard_needs_high():
    text = _TRADECRAFT
    # The rule: Hard challenges need High coverage (or two Mediums paired).
    assert "Hard" in text and "High" in text
    assert "walk into a wall" in text.lower() or "no exceptions" in text.lower()


def test_tradecraft_block_teaches_driver_rule():
    text = _TRADECRAFT.lower()
    assert "driver" in text
    assert "running on foot" in text


def test_bid_prompt_contains_tradecraft():
    prompt = _bid_prompt("test strategy")
    assert _TRADECRAFT in prompt
    assert "test strategy" in prompt
    assert "Bankroll: $2000000" in prompt


def test_job_prompt_warns_about_traps():
    crew = Crew(members=[
        Character(10, "Rook", {"safecracker": SkillLevel.HIGH}, 700_000, "")
    ])
    prompt = _job_prompt(crew)
    assert "trap" in prompt.lower()
    assert "Hard" in prompt
    assert "two Mediums" in prompt or "Mediums who can pair" in prompt


def test_scene_assign_prompt_mentions_collaboration_for_challenges():
    char = Character(10, "Rook", {"safecracker": SkillLevel.HIGH}, 700, "")
    crew = Crew(members=[char])
    el = MUSEUM.hidden_depth[0]
    state = HeistState(
        crew=crew, job=MUSEUM,
        hidden_depth=HiddenDepthRoll(el, "Standard valuation", 2_500_000),
    )
    scenes = generate_scenes(MUSEUM, state.hidden_depth)
    challenge_scene = next(s for s in scenes if s.type == "challenge")
    prompt = _scene_assign_prompt(challenge_scene, state)
    assert "support" in prompt.lower()
    assert "one level higher" in prompt.lower() or "pair" in prompt.lower()
    # And the challenge skill is still surfaced so the AI knows what to target.
    assert challenge_scene.challenge_skill is not None
    assert challenge_scene.challenge_skill in prompt
