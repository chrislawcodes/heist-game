import random

from heist.board import (
    BOARD_SIZE,
    affordable,
    build_board,
    estimated_crew_cost,
    pick_order,
    tier_rank,
    unlocked_max_rank,
)
from heist.content import JOBS
from heist.state import ChallengeLevel


def _hard_count(job):
    return sum(1 for v in job.profile.values() if v == ChallengeLevel.HARD)


def test_tier_rank_tracks_hard_count():
    for j in JOBS:
        hc = _hard_count(j)
        r = tier_rank(j)
        if hc == 0:
            assert r == 0
        elif hc == 1:
            assert r == 1
        elif hc in (2, 3):
            assert r == 2
        else:
            assert r == 3


def test_affordable_monotonic_in_bankroll():
    j_easy = min(JOBS, key=tier_rank)
    assert affordable(j_easy, estimated_crew_cost(j_easy))
    assert not affordable(j_easy, estimated_crew_cost(j_easy) - 1)


def test_pick_order_ascending_probes_with_tiebreaks():
    """Feature 003 / US2: pick order = ascending probes_spent, then ascending
    banked_loot, then ascending ai_idx. Standings are (ai_idx, probes, bankroll)."""
    # Fewest probes wins outright.
    standings = [(0, 5, 1_000_000), (1, 1, 9_000_000), (2, 3, 500_000)]
    assert pick_order(standings) == [1, 2, 0]
    # Same probes → bankroll asc wins.
    same_probes = [(0, 4, 1_000_000), (1, 4, 500_000), (2, 4, 2_000_000)]
    assert pick_order(same_probes) == [1, 0, 2]
    # Same probes + same bankroll → ai_idx asc wins.
    same_all = [(2, 4, 500_000), (0, 4, 500_000), (1, 4, 500_000)]
    assert pick_order(same_all) == [0, 1, 2]


def test_pick_order_all_zero_probes_falls_through_to_bankroll():
    """When every team rushed (0 probes), order is bankroll-ascending then ai_idx —
    equivalent to the old trailing-team-first rule for that case."""
    standings = [(0, 0, 5_000_000), (1, 0, 1_000_000), (2, 0, 1_000_000), (3, 0, 9_000_000)]
    assert pick_order(standings) == [1, 2, 0, 3]


def test_pick_order_empty_input():
    assert pick_order([]) == []


def test_board_size_and_no_consumed():
    rng = random.Random(42)
    consumed = set()
    board = build_board(JOBS, consumed, 0, 10, 0, trailing_bankroll=2_000_000, rng=rng)
    assert len(board) == min(BOARD_SIZE, len(JOBS))
    assert len(set(board)) == len(board)  # no dupes
    # never offers a consumed job
    rng2 = random.Random(7)
    consumed2 = {JOBS[0].name, JOBS[1].name}
    board2 = build_board(JOBS, consumed2, 3, 10, 5_000_000, trailing_bankroll=3_000_000, rng=rng2)
    assert JOBS[0].name not in board2 and JOBS[1].name not in board2


def test_board_deterministic_for_seed():
    kw = dict(trailing_bankroll=3_000_000)
    a = build_board(JOBS, set(), 4, 10, 6_000_000, rng=random.Random(99), **kw)
    b = build_board(JOBS, set(), 4, 10, 6_000_000, rng=random.Random(99), **kw)
    assert a == b


def test_board_returns_all_when_pool_runs_low():
    # consume all but 3 jobs → board is exactly those 3
    keep = {JOBS[0].name, JOBS[1].name, JOBS[2].name}
    consumed = {j.name for j in JOBS if j.name not in keep}
    board = build_board(
        JOBS, consumed, 8, 10, 20_000_000,
        trailing_bankroll=5_000_000, rng=random.Random(1),
    )
    assert set(board) == keep


def test_early_round_gates_out_elite():
    # Round 0 with no banked loot: gated slots must not include rank-3 (4-Hard)
    # jobs; only the wild slots could. With wild_slots=0 the board excludes elite.
    rng = random.Random(3)
    board = build_board(
        JOBS, set(), 0, 10, 0,
        wild_slots=0, trailing_bankroll=2_000_000, rng=rng,
    )
    by_name = {j.name: j for j in JOBS}
    assert all(tier_rank(by_name[n]) <= unlocked_max_rank(0, 10, 0) for n in board)


def test_late_round_unlocks_elite():
    assert unlocked_max_rank(9, 10, 30_000_000) == 3
    assert unlocked_max_rank(0, 10, 0) == 1


def test_affordable_minimum_guaranteed():
    rng = random.Random(11)
    # trailing team is poor: only rank-0 jobs are affordable
    poor = 600_000
    board = build_board(
        JOBS, set(), 6, 10, 4_000_000,
        min_affordable=2, trailing_bankroll=poor, rng=rng,
    )
    by_name = {j.name: j for j in JOBS}
    aff = [n for n in board if affordable(by_name[n], poor)]
    assert len(aff) >= 2
