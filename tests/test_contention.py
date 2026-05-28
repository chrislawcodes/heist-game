"""US3 — contested board resolution: teams pick trailing-first, a lower-banked
team wins a job a richer rival also wants, every team gets a distinct job, and
the board is consumed globally."""
from heist.board import pick_order, resolve_contention


def test_pick_order_trailing_first():
    # ai 0 leads ($5M), ai 1 trails ($1M), ai 2 mid ($3M). All-zero probes →
    # falls through to bankroll ascending. Feature 003 pick_order takes
    # (ai_idx, probes_spent, banked_loot) tuples.
    assert pick_order([(0, 0, 5_000_000), (1, 0, 1_000_000), (2, 0, 3_000_000)]) == [1, 2, 0]


def test_lower_banked_wins_a_contested_job():
    """All three teams want 'The Mint' first; the trailing (lowest-banked) team
    claims it, the richer teams fall back to the next available board job."""
    order = pick_order([(0, 0, 5_000_000), (1, 0, 1_000_000), (2, 0, 3_000_000)])
    board = ["The Mint", "B", "C", "D"]

    def everyone_wants_the_mint(ai_idx, remaining):
        return "The Mint"  # always the top prize

    assigned, contested = resolve_contention(order, board, everyone_wants_the_mint)
    # Trailing team (ai 1) gets the contested prize.
    assert assigned[1] == "The Mint"
    # Richer teams got distinct fallbacks (system picks first remaining).
    assert assigned[2] != "The Mint" and assigned[0] != "The Mint"
    assert len(set(assigned.values())) == 3  # all distinct
    # ai 1 picked first (no prior claims) → not contested; the rest are.
    assert contested[1] is False
    assert contested[2] is True and contested[0] is True


def test_each_team_gets_a_distinct_job():
    order = [2, 0, 1, 3]
    board = ["A", "B", "C", "D", "E"]
    # each team wants the first item it sees
    assigned, _ = resolve_contention(order, board, lambda ai, rem: rem[0])
    assert set(assigned.keys()) == {0, 1, 2, 3}
    assert len(set(assigned.values())) == 4  # distinct
    assert all(v in board for v in assigned.values())


def test_board_runs_dry_leaves_late_team_without_a_job():
    order = [0, 1, 2]  # 3 teams
    board = ["A", "B"]  # only 2 jobs
    assigned, _ = resolve_contention(order, board, lambda ai, rem: rem[0])
    assert len(assigned) == 2  # the last team (2) gets nothing — board ran dry
    assert 2 not in assigned


def test_invalid_pick_falls_back_to_first_remaining():
    order = [0, 1]
    board = ["A", "B"]
    # team 0 names an off-board job → system falls back to remaining[0].
    assigned, _ = resolve_contention(order, board, lambda ai, rem: "NOT_ON_BOARD")
    assert assigned[0] == "A"
    assert assigned[1] == "B"
