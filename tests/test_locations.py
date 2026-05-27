"""Reward-shape invariants for the contested job board (US2 / Decision 6):
take climbs with difficulty, every job is worth contesting (floor >= $1M),
the elite 4-Hard jobs are the jackpots, and published ranges are honest."""
import statistics

from heist.content import JOBS
from heist.state import ChallengeLevel


def _hard_count(job):
    return sum(1 for v in job.profile.values() if v == ChallengeLevel.HARD)


def _take(job):
    return sum(job.scene_loot.values())


def test_reward_floor_at_least_one_million():
    for j in JOBS:
        assert _take(j) >= 1_000_000, f"{j.name} take {_take(j)} below $1M floor"


def test_band_median_take_ascends_with_difficulty():
    bands = {}
    for j in JOBS:
        bands.setdefault(_hard_count(j), []).append(_take(j))
    medians = {hc: statistics.median(v) for hc, v in bands.items()}
    present = sorted(medians)
    for a, b in zip(present, present[1:], strict=False):
        assert medians[a] < medians[b], (
            f"band-median take not ascending: {a}-Hard {medians[a]} >= {b}-Hard {medians[b]}"
        )


def test_four_hard_jobs_are_the_top_two_takes():
    ranked = sorted(JOBS, key=_take, reverse=True)
    top_two = ranked[:2]
    assert all(_hard_count(j) == 4 for j in top_two), (
        f"top-two takes are not the 4-Hard jobs: {[(j.name, _hard_count(j)) for j in top_two]}"
    )
    for j in top_two:
        assert _take(j) >= 15_000_000, f"{j.name} jackpot {_take(j)} below $15M"


def test_reward_range_is_honest_and_reachable():
    for j in JOBS:
        lo, hi = j.reward_range
        take = _take(j)
        best_bonus = max((amt for _, amt in j.reward_amounts), default=0)
        assert lo < hi, f"{j.name} range not ascending: {j.reward_range}"
        assert hi <= take + best_bonus, (
            f"{j.name} range top {hi} unreachable (clean {take} + best bonus {best_bonus})"
        )
        assert lo <= take, f"{j.name} range bottom {lo} exceeds clean take {take}"


def test_scene_loot_pays_into_active_challenges():
    for j in JOBS:
        for cat in j.scene_loot:
            assert j.profile.get(cat, ChallengeLevel.NONE) != ChallengeLevel.NONE, (
                f"{j.name}: scene_loot pays into inactive challenge {cat!r}"
            )


def test_pool_depth_and_category_coverage():
    """US5: ~50-job pool, and every active challenge category gates (appears at
    HARD on) at least one job, so scouting matters across all skills."""
    assert len(JOBS) >= 45
    gated = {
        cat
        for j in JOBS
        for cat, lvl in j.profile.items()
        if lvl == ChallengeLevel.HARD
    }
    for cat in ("electronic", "physical", "confrontation", "social"):
        assert cat in gated, f"no job gates on a Hard {cat} challenge"


def test_edges_exist():
    """The difficulty→reward bands overlap (the scoutable mispriced jobs): at
    least one 1-Hard job out-earns the weakest 2-Hard (a bargain), and at least
    one 2-Hard job pays below the 2-Hard median (a trap)."""
    twos = [_take(j) for j in JOBS if _hard_count(j) == 2]
    ones = [_take(j) for j in JOBS if _hard_count(j) == 1]
    bargain = max(ones) >= min(twos)
    trap = any(t < statistics.median(twos) for t in twos)
    assert bargain, "no bargain edge: no 1-Hard job out-earns the weakest 2-Hard"
    assert trap, "no trap edge: no 2-Hard job pays below the 2-Hard median"
