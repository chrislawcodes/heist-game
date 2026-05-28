from __future__ import annotations

import random

import pytest

from heist.ai import StubHeistAI
from heist.content import ROSTER_BY_ID
from heist.mechanics import Outcome, outcome_is_pass, resolve_by_margin
from heist.resolution import (
    _catch_member_from_assigned,
    _finalize_reward,
)
from heist.runner import (
    _emit_heist_complete,
    _execute_escape,
    _execute_scene,
    _run_scene_loop,
)
from heist.state import (
    ChallengeLevel,
    Character,
    Crew,
    HeistState,
    HiddenDepthElement,
    HiddenDepthRoll,
    Job,
    Scene,
    SkillLevel,
)


def _char(cid: int, name: str, skills: dict[str, SkillLevel], floor_cost: int) -> Character:
    return Character(cid, name, skills, floor_cost)


def _job(scene_loot: dict[str, int] | None = None) -> Job:
    return Job(
        name="Test Job",
        flavor="",
        reward_range=(1, 2),
        profile={
            "electronic": ChallengeLevel.NONE,
            "physical": ChallengeLevel.NONE,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.NONE,
        },
        hidden_depth=[HiddenDepthElement("hd", "hd", "complication", {})],
        reward_amounts=[("std", 1)],
        scene_loot=scene_loot or {},
    )


def _state(
    *,
    crew: Crew,
    caught: list[int] | None = None,
    secured_take: int = 0,
    heat: int = 0,
    escape_success: bool | None = None,
    job: Job | None = None,
) -> HeistState:
    job = job or _job()
    return HeistState(
        crew=crew,
        job=job,
        hidden_depth=HiddenDepthRoll(job.hidden_depth[0], "std", 1),
        caught_member_ids=list(caught or []),
        secured_take=secured_take,
        heat=heat,
        escape_success=escape_success,
    )


@pytest.mark.parametrize(
    "eff_score,challenge_score,outcome",
    [
        (5, 0, Outcome.CLEAN),    # no challenge
        (10, 8, Outcome.CLEAN),   # margin +2
        (8, 8, Outcome.SQUEAK),   # margin 0
        (9, 8, Outcome.SQUEAK),   # margin +1
        (7, 8, Outcome.FAIL),     # margin -1
        (5, 8, Outcome.FAIL),     # margin -3
        (4, 8, Outcome.CAUGHT),   # margin -4
    ],
)
def test_resolve_by_margin_table(eff_score, challenge_score, outcome):
    assert resolve_by_margin(eff_score, challenge_score) is outcome
    assert outcome_is_pass(outcome) is (outcome in (Outcome.CLEAN, Outcome.SQUEAK))


@pytest.mark.parametrize(
    "member_id,challenge_level,expected_heat,expected_success,expected_take,expected_caught",
    [
        (1, ChallengeLevel.LOW, 0, True, 123_000, []),
        (2, ChallengeLevel.MEDIUM, 1, True, 123_000, []),
    ],
)
def test_scene_resolution_passing(
    member_id, challenge_level, expected_heat, expected_success, expected_take, expected_caught
):
    """Passing scenes (CLEAN / SQUEAK): no abort prompt fired."""
    crew = Crew([ROSTER_BY_ID[member_id]])
    job = _job({"electronic": 123_000})
    state = _state(crew=crew, job=job)
    scene = Scene(
        number=1, type="challenge", title="Test",
        challenge_skill="hacker", challenge_level=challenge_level,
        is_core=False, context="", category="electronic",
    )
    ai = StubHeistAI([
        f'{{"assigned_member_ids": [{member_id}], "reasoning": "assign"}}',
        "stub narration",
    ])
    result = _execute_scene(scene, state, ai, [], None, random.Random(1))
    assert result.success is expected_success
    assert state.heat == expected_heat
    assert state.secured_take == expected_take
    assert state.caught_member_ids == expected_caught


@pytest.mark.parametrize(
    "member_id,challenge_level,expected_heat,expected_success,expected_take,expected_caught",
    [
        (3, ChallengeLevel.MEDIUM, 1, False, 0, []),
        (3, ChallengeLevel.HARD, 1, False, 0, [3]),
    ],
)
def test_scene_resolution_failing(
    member_id, challenge_level, expected_heat, expected_success, expected_take, expected_caught
):
    """Failing scenes (FAIL / CAUGHT): abort prompt fires; stub pushes on."""
    crew = Crew([ROSTER_BY_ID[member_id]])
    job = _job({"electronic": 123_000})
    state = _state(crew=crew, job=job)
    scene = Scene(
        number=1, type="challenge", title="Test",
        challenge_skill="hacker", challenge_level=challenge_level,
        is_core=False, context="", category="electronic",
    )
    ai = StubHeistAI([
        f'{{"assigned_member_ids": [{member_id}], "reasoning": "assign"}}',
        '{"abort": false, "reasoning": "push on"}',
        "stub narration",
    ])
    result = _execute_scene(scene, state, ai, [], None, random.Random(1))
    assert result.success is expected_success
    assert state.heat == expected_heat
    assert state.secured_take == expected_take
    assert state.caught_member_ids == expected_caught


@pytest.mark.parametrize(
    "member,challenge_level,expected_caught",
    [
        (ROSTER_BY_ID[3], ChallengeLevel.MEDIUM, []),
        (ROSTER_BY_ID[11], ChallengeLevel.HARD, [11]),
    ],
)
def test_bonus_resolution_failing_adds_only_one_heat(
    member, challenge_level, expected_caught
):
    """Bonus FAIL / CAUGHT scenes should add exactly one heat, same as core scenes."""
    crew = Crew([member])
    job = _job({"electronic": 123_000})
    state = _state(crew=crew, job=job)
    scene = Scene(
        number=1, type="decision", title="Bonus",
        challenge_skill="hacker", challenge_level=challenge_level,
        is_core=False, context="", category="electronic",
    )
    ai = StubHeistAI([
        f'{{"assigned_member_ids": [{member.id}], "reasoning": "assign"}}',
        '{"pursue": true, "reasoning": "go for it"}',
        '{"abort": false, "reasoning": "push on"}',
        "stub narration",
    ])
    result = _execute_scene(scene, state, ai, [], None, random.Random(1))
    assert result.success is False
    assert state.heat == 1
    assert state.secured_take == 0
    assert state.caught_member_ids == expected_caught


def test_caught_member_prefers_skill_holder_then_lowest_floor_cost():
    lead = _char(1, "Lead", {"hacker": SkillLevel.LOW}, 900_000)
    cheap = _char(2, "Cheap", {"safecracker": SkillLevel.LOW}, 100_000)
    scene = Scene(
        number=1,
        type="challenge",
        title="Test",
        challenge_skill="hacker",
        challenge_level=ChallengeLevel.HARD,
        is_core=True,
        context="",
        category="electronic",
    )
    chosen = _catch_member_from_assigned(scene, [lead, cheap])
    assert chosen is lead

    fallback = _catch_member_from_assigned(
        scene,
        [
            _char(3, "A", {"safecracker": SkillLevel.LOW}, 500_000),
            _char(4, "B", {"safecracker": SkillLevel.LOW}, 200_000),
        ],
    )
    assert fallback is not None
    assert fallback.id == 4


def test_escape_failure_catches_one_free_member():
    crew = Crew([
        _char(1, "A", {"muscle": SkillLevel.LOW}, 100_000),
        _char(2, "B", {"safecracker": SkillLevel.MEDIUM}, 200_000),
        _char(3, "C", {"inside_man": SkillLevel.MEDIUM}, 300_000),
    ])
    state = _state(crew=crew, heat=2)
    scene = Scene(1, "escape", "Escape", "driver", None, False, "", None)
    ai = StubHeistAI([
        '{"assigned_member_ids": [1], "abort": false, "reasoning": "go"}',
        '{"narration": "escape"}',
    ])
    result = _execute_escape(scene, state, ai, [], None, random.Random(7))
    assert result.success is False
    assert len(state.caught_member_ids) == 1
    assert state.caught_member_ids[0] in {1, 2, 3}


def test_finalize_reward_uses_secured_take_when_anyone_free():
    crew = Crew([
        _char(1, "A", {"muscle": SkillLevel.LOW}, 100_000),
        _char(2, "B", {"safecracker": SkillLevel.MEDIUM}, 200_000),
    ])
    state = _state(crew=crew, caught=[1], secured_take=1_250_000)
    _finalize_reward(state)
    assert state.final_take == 1_250_000


def test_finalize_reward_zero_when_everyone_caught():
    crew = Crew([
        _char(1, "A", {"muscle": SkillLevel.LOW}, 100_000),
        _char(2, "B", {"safecracker": SkillLevel.MEDIUM}, 200_000),
    ])
    state = _state(crew=crew, caught=[1, 2], secured_take=1_250_000)
    _finalize_reward(state)
    assert state.final_take == 0


def test_abort_sets_aborted_and_routes_to_escape():
    crew = Crew([
        _char(1, "Driver", {"driver": SkillLevel.HIGH}, 700_000),
        _char(2, "Hacker", {"hacker": SkillLevel.HIGH}, 700_000),
    ])
    job = _job()
    state = HeistState(
        crew=crew,
        job=job,
        hidden_depth=HiddenDepthRoll(job.hidden_depth[0], "std", 1),
    )
    challenge = Scene(
        number=1,
        type="challenge",
        title="Test Challenge",
        challenge_skill="hacker",
        challenge_level=ChallengeLevel.HARD,
        is_core=True,
        context="",
        category="electronic",
    )
    escape = Scene(
        number=2,
        type="escape",
        title="Escape",
        challenge_skill="driver",
        challenge_level=None,
        is_core=False,
        context="",
    )
    ai = StubHeistAI([
        '{"assigned_member_ids": [1, 2], "abort": true, "reasoning": "bail"}',
        '{"assigned_member_ids": [1], "abort": false, "reasoning": "driver"}',
        '{"narration": "escape"}',
    ])
    extras = {"scene_narrations": []}
    _run_scene_loop(
        [challenge, escape],
        state,
        ai,
        [],
        extras,
        emit=None,
        on_scene=None,
        snapshot_fn=None,
        strategy="",
        rng=random.Random(5),
    )
    assert state.aborted is True
    assert state.escape_success is True
    assert [r.scene.type for r in state.scene_results] == ["challenge", "escape"]
    assert not any("scene_1_narrate" in prompt for prompt in ai.prompts_seen)


# ── new event-field tests ────────────────────────────────────────────────────


def test_scene_done_event_carries_outcome_and_deltas():
    """scene_done event must include outcome, heat_delta, caught_member_id,
    loot_secured, and secured_take."""
    crew = Crew([ROSTER_BY_ID[1]])  # member 1 has hacker LOW
    job = _job({"electronic": 50_000})
    state = _state(crew=crew, job=job)
    scene = Scene(
        number=1, type="challenge", title="Test",
        challenge_skill="hacker", challenge_level=ChallengeLevel.LOW,
        is_core=True, context="", category="electronic",
    )
    ai = StubHeistAI([
        '{"assigned_member_ids": [1], "reasoning": "assign"}',
        "stub narration",
    ])
    emitted: list[dict] = []
    _run_scene_loop(
        [scene], state, ai, [], {"scene_narrations": []},
        emit=emitted.append, on_scene=None, snapshot_fn=None,
        strategy="", rng=random.Random(1),
    )
    scene_done_events = [e for e in emitted if e["type"] == "scene_done"]
    assert len(scene_done_events) == 1
    ev = scene_done_events[0]
    # CLEAN outcome: hacker LOW vs LOW challenge → CLEAN
    assert ev["outcome"] == "CLEAN"
    assert ev["heat_delta"] == 0
    assert ev["caught_member_id"] is None
    assert ev["loot_secured"] == 50_000
    assert ev["secured_take"] == 50_000


def test_scene_done_event_caught_and_heat_delta_on_caught_outcome():
    """CAUGHT outcome increments heat and records caught_member_id."""
    # member 3 has hacker NONE — will get CAUGHT vs HARD challenge
    crew = Crew([ROSTER_BY_ID[3]])
    job = _job({"electronic": 100_000})
    state = _state(crew=crew, job=job)
    scene = Scene(
        number=1, type="challenge", title="Test",
        challenge_skill="hacker", challenge_level=ChallengeLevel.HARD,
        is_core=True, context="", category="electronic",
    )
    ai = StubHeistAI([
        '{"assigned_member_ids": [3], "reasoning": "assign"}',
        '{"abort": false, "reasoning": "push on"}',
        "stub narration",
    ])
    emitted: list[dict] = []
    _run_scene_loop(
        [scene], state, ai, [], {"scene_narrations": []},
        emit=emitted.append, on_scene=None, snapshot_fn=None,
        strategy="", rng=random.Random(1),
    )
    ev = next(e for e in emitted if e["type"] == "scene_done")
    assert ev["outcome"] == "CAUGHT"
    assert ev["heat_delta"] == 1
    assert ev["caught_member_id"] == 3
    assert ev["loot_secured"] == 0


def test_heist_complete_event_fires_with_final_take():
    """_emit_heist_complete emits a heist_complete event with final_take."""
    crew = Crew([
        _char(1, "A", {"driver": SkillLevel.HIGH}, 700_000),
    ])
    state = _state(crew=crew, secured_take=500_000)
    _finalize_reward(state)
    emitted: list[dict] = []
    _emit_heist_complete(emitted.append, state)
    assert len(emitted) == 1
    ev = emitted[0]
    assert ev["type"] == "heist_complete"
    assert ev["final_take"] == 500_000
    assert ev["secured_take"] == 500_000
    assert ev["caught_member_ids"] == []
    assert 1 in ev["free_member_ids"]


def test_heist_complete_final_take_zero_when_all_caught():
    """final_take is 0 when all crew members are caught."""
    crew = Crew([_char(1, "A", {"muscle": SkillLevel.LOW}, 100_000)])
    state = _state(crew=crew, caught=[1], secured_take=999_000)
    _finalize_reward(state)
    emitted: list[dict] = []
    _emit_heist_complete(emitted.append, state)
    ev = emitted[0]
    assert ev["final_take"] == 0
    assert ev["free_member_ids"] == []
    assert ev["caught_member_ids"] == [1]
