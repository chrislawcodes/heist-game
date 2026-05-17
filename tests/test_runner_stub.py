import random

import pytest

from heist.content import DEFAULT_PROMPT
from heist.output import render_markdown
from heist.runner import run_heist
from heist.stub_responses import build_stub_ai


def test_end_to_end_with_stub_ai():
    state, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(42))
    assert len(state.crew.members) == 4
    assert state.crew.total_cost <= 2000
    assert state.job.name == "The Museum Gala"
    # Structural assertions instead of a magic count — number depends on which
    # hidden depth element rolled (some skip scenes, some add them, abort cuts
    # the body short).
    assert state.scene_results[0].scene.type == "setup"
    assert state.scene_results[-1].scene.type == "escape"
    assert any(r.scene.type == "challenge" for r in state.scene_results)
    assert state.escape_success is not None
    assert state.escape_difficulty is not None


def test_markdown_renders_without_error():
    state, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(7))
    md = render_markdown(state, extras)
    assert "# Heist Report:" in md
    assert "## Casting" in md
    assert "## Heist" in md
    assert "## Outcome" in md
    assert state.job.name in md


@pytest.mark.parametrize("job_name", [
    "The Museum Gala",
    "The Armored Car",
    "The Corporate Server Farm",
])
def test_every_job_runs_cleanly_with_stub(job_name):
    """All three jobs must execute end-to-end without runtime errors. The
    mechanical outcome (success/abort/fail) doesn't matter here — we only
    assert the structural invariants of a finished run."""
    state, _ = run_heist(
        DEFAULT_PROMPT, build_stub_ai(job_name=job_name), rng=random.Random(7)
    )
    assert state.job.name == job_name
    assert len(state.crew.members) == 4
    assert state.crew.total_cost <= 2000
    assert state.scene_results, "no scenes resolved"
    assert state.scene_results[0].scene.type == "setup"
    assert state.scene_results[-1].scene.type == "escape"
    assert state.escape_success is not None
    assert state.escape_difficulty is not None
    # final_take is either 0 (abort/failed escape) or hidden-depth reward + maybe bonus
    if state.aborted or state.escape_success is False:
        assert state.final_take == 0
    else:
        assert state.final_take >= state.hidden_depth.reward_amount


def test_zero_take_on_failed_escape(monkeypatch):
    """If the escape fails, final_take must be 0 even if scenes succeeded."""
    from heist.runner import _finalize_reward
    from heist.state import (
        ChallengeLevel,
        Character,
        Crew,
        HeistState,
        HiddenDepthElement,
        HiddenDepthRoll,
        Job,
        SkillLevel,
    )
    char = Character(1, "x", {"driver": SkillLevel.LOW}, 200, "")
    job = Job("J", "", (1, 2), {"physical": ChallengeLevel.LOW,
                                  "electronic": ChallengeLevel.NONE,
                                  "confrontation": ChallengeLevel.NONE,
                                  "social": ChallengeLevel.NONE},
              0,
              [HiddenDepthElement("x", "x", "complication", {})],
              [("std", 1_000_000)])
    el = job.hidden_depth[0]
    state = HeistState(
        crew=Crew([char]), job=job,
        hidden_depth=HiddenDepthRoll(el, "std", 1_000_000),
        escape_success=False,
    )
    _finalize_reward(state)
    assert state.final_take == 0


def test_zero_take_on_abort():
    from heist.runner import _finalize_reward
    from heist.state import (
        ChallengeLevel,
        Character,
        Crew,
        HeistState,
        HiddenDepthElement,
        HiddenDepthRoll,
        Job,
        SkillLevel,
    )
    char = Character(1, "x", {"driver": SkillLevel.LOW}, 200, "")
    job = Job("J", "", (1, 2), {"physical": ChallengeLevel.LOW,
                                  "electronic": ChallengeLevel.NONE,
                                  "confrontation": ChallengeLevel.NONE,
                                  "social": ChallengeLevel.NONE},
              0,
              [HiddenDepthElement("x", "x", "complication", {})],
              [("std", 1_000_000)])
    el = job.hidden_depth[0]
    state = HeistState(
        crew=Crew([char]), job=job,
        hidden_depth=HiddenDepthRoll(el, "std", 1_000_000),
        aborted=True,
    )
    _finalize_reward(state)
    assert state.final_take == 0
