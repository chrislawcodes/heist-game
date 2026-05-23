from __future__ import annotations

import random

from heist.slate import build_slate
from heist.state import Job


def _job(name: str, tier: str) -> Job:
    return Job(
        name=name,
        flavor="",
        reward_range=(100_000, 200_000),
        profile={},
        escape_modifier=0,
        hidden_depth=[],
        reward_amounts=[],
        tier=tier,
    )


def _slate_state() -> dict:
    return {
        "current_slate": [],
        "rounds_on_slate": {},
    }


def _names(jobs: list[Job]) -> list[str]:
    return [job.name for job in jobs]


def test_easy_only_round_1() -> None:
    rng = random.Random(42)
    jobs = [
        _job("easy-1", "easy"),
        _job("easy-2", "easy"),
        _job("medium-1", "medium"),
        _job("hard-1", "hard"),
        _job("elite-1", "elite"),
    ]

    slate = build_slate(jobs, round_idx=0, num_ais=1, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert len(slate) == 2
    assert {job.tier for job in slate} == {"easy"}


def test_medium_unlocks_round_3() -> None:
    rng = random.Random(42)
    jobs = [
        _job("medium-1", "medium"),
        _job("easy-1", "easy"),
        _job("hard-1", "hard"),
        _job("elite-1", "elite"),
    ]

    slate = build_slate(jobs, round_idx=2, num_ais=1, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert any(job.tier == "medium" for job in slate)


def test_hard_unlocks_round_6() -> None:
    rng = random.Random(42)
    jobs = [
        _job("hard-1", "hard"),
        _job("medium-1", "medium"),
        _job("easy-1", "easy"),
        _job("elite-1", "elite"),
    ]

    slate = build_slate(jobs, round_idx=5, num_ais=1, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert any(job.tier == "hard" for job in slate)


def test_elite_unlocks_round_8() -> None:
    rng = random.Random(42)
    jobs = [
        _job("elite-1", "elite"),
        _job("hard-1", "hard"),
        _job("medium-1", "medium"),
        _job("easy-1", "easy"),
    ]

    slate = build_slate(jobs, round_idx=7, num_ais=1, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert any(job.tier == "elite" for job in slate)


def test_slate_size_matches_num_ais() -> None:
    rng = random.Random(42)
    jobs = [_job(f"easy-{idx}", "easy") for idx in range(1, 7)]

    slate = build_slate(jobs, round_idx=0, num_ais=3, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert len(slate) == 6


def test_unchosen_jobs_carry_over() -> None:
    rng = random.Random(42)
    jobs = [_job(f"easy-{idx}", "easy") for idx in range(1, 5)]
    state = _slate_state()

    first = build_slate(jobs, round_idx=0, num_ais=1, attempted_job_names=set(),
                        slate_state=state, rng=rng)
    second = build_slate(jobs, round_idx=1, num_ais=1, attempted_job_names=set(),
                         slate_state=state, rng=rng)

    assert _names(second) == _names(first)


def test_stale_job_removed_after_3_rounds() -> None:
    rng = random.Random(42)
    jobs = [_job("easy-1", "easy"), _job("easy-2", "easy")]
    state = _slate_state()

    build_slate(jobs, round_idx=0, num_ais=1, attempted_job_names=set(),
                slate_state=state, rng=rng)
    build_slate(jobs, round_idx=1, num_ais=1, attempted_job_names=set(),
                slate_state=state, rng=rng)
    build_slate(jobs, round_idx=2, num_ais=1, attempted_job_names=set(),
                slate_state=state, rng=rng)
    fourth = build_slate(jobs, round_idx=3, num_ais=1, attempted_job_names=set(),
                         slate_state=state, rng=rng)

    assert "easy-1" not in _names(fourth)
    assert "easy-2" not in _names(fourth)


def test_attempted_job_never_readded() -> None:
    rng = random.Random(42)
    jobs = [_job("easy-1", "easy"), _job("easy-2", "easy"), _job("easy-3", "easy")]
    state = _slate_state()
    attempted = {"easy-2"}

    first = build_slate(jobs, round_idx=0, num_ais=1, attempted_job_names=attempted,
                        slate_state=state, rng=rng)
    second = build_slate(jobs, round_idx=1, num_ais=1, attempted_job_names=attempted,
                         slate_state=state, rng=rng)

    assert "easy-2" not in _names(first)
    assert "easy-2" not in _names(second)


def test_slate_refills_after_removal() -> None:
    rng = random.Random(42)
    jobs = [_job(f"easy-{idx}", "easy") for idx in range(1, 6)]
    state = _slate_state()

    first = build_slate(jobs, round_idx=0, num_ais=2, attempted_job_names=set(),
                        slate_state=state, rng=rng)
    removed = first[0].name
    state["current_slate"] = [name for name in state["current_slate"] if name != removed]
    state["rounds_on_slate"].pop(removed, None)

    second = build_slate(jobs, round_idx=1, num_ais=2, attempted_job_names=set(),
                         slate_state=state, rng=rng)

    assert len(second) == 4


def test_small_pool_no_error() -> None:
    rng = random.Random(42)
    jobs = [_job("easy-1", "easy")]

    slate = build_slate(jobs, round_idx=0, num_ais=3, attempted_job_names=set(),
                        slate_state=_slate_state(), rng=rng)

    assert len(slate) == 1
