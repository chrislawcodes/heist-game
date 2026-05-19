"""Exhaustive tests for the Phase 2 auction module.

The module is a pure function so we can hit every interesting edge case
without AI scaffolding. These tests are the rule book — if any of them fails
after a future edit, the design changed."""

import random

from heist.auction import BidWin, PlayerBid, random_fill, resolve_round
from heist.content import ROSTER, ROSTER_BY_ID

# ────────── resolve_round ──────────


def test_single_bidder_wins_uncontested():
    bids = [PlayerBid(player_id="A", character_id=10, amount=700)]
    r = resolve_round(bids)
    assert r.wins == {"A": [BidWin("A", 10, 700)]}
    assert r.tied_characters == []
    assert r.uncontested_characters == [10]


def test_highest_unique_bid_wins():
    bids = [
        PlayerBid("A", 10, 700),
        PlayerBid("B", 10, 800),
        PlayerBid("C", 10, 750),
    ]
    r = resolve_round(bids)
    assert r.wins == {"B": [BidWin("B", 10, 800)]}
    assert r.tied_characters == []
    assert r.uncontested_characters == []  # 3 bidders, not uncontested


def test_tied_top_bids_produce_no_winner():
    bids = [
        PlayerBid("A", 10, 800),
        PlayerBid("B", 10, 800),
    ]
    r = resolve_round(bids)
    assert r.wins == {}
    assert r.tied_characters == [10]


def test_three_way_tie_no_winner():
    bids = [
        PlayerBid("A", 10, 700),
        PlayerBid("B", 10, 700),
        PlayerBid("C", 10, 700),
    ]
    r = resolve_round(bids)
    assert r.wins == {}
    assert r.tied_characters == [10]


def test_tie_below_a_unique_high_does_not_count():
    """Two players tie at $700, one player bids $900 alone. The $900 wins."""
    bids = [
        PlayerBid("A", 10, 700),
        PlayerBid("B", 10, 700),
        PlayerBid("C", 10, 900),
    ]
    r = resolve_round(bids)
    assert r.wins == {"C": [BidWin("C", 10, 900)]}
    assert r.tied_characters == []


def test_multiple_characters_resolved_independently():
    bids = [
        # char 10: A wins
        PlayerBid("A", 10, 800),
        PlayerBid("B", 10, 700),
        # char 4: tied → no winner
        PlayerBid("A", 4, 700),
        PlayerBid("B", 4, 700),
        # char 13: B wins uncontested
        PlayerBid("B", 13, 700),
    ]
    r = resolve_round(bids)
    assert r.wins["A"] == [BidWin("A", 10, 800)]
    assert r.wins["B"] == [BidWin("B", 13, 700)]
    assert r.tied_characters == [4]
    assert r.uncontested_characters == [13]


def test_one_player_can_win_multiple_characters_one_round():
    bids = [
        PlayerBid("A", 10, 700),
        PlayerBid("A", 4, 700),
        PlayerBid("A", 8, 200),
    ]
    r = resolve_round(bids)
    assert len(r.wins["A"]) == 3
    assert r.winnings_for("A") == 700 + 700 + 200
    assert set(c for c in r.characters_won()) == {10, 4, 8}


def test_empty_bid_list_returns_empty_result():
    r = resolve_round([])
    assert r.wins == {}
    assert r.tied_characters == []
    assert r.uncontested_characters == []


def test_only_winning_bids_count_toward_winnings():
    bids = [
        PlayerBid("A", 10, 800),  # A wins
        PlayerBid("B", 10, 700),  # B loses (refund implicit)
        PlayerBid("B", 4, 700),  # B wins this one
    ]
    r = resolve_round(bids)
    # A spent only what they won
    assert r.winnings_for("A") == 800
    # B's $700 loss to A is not counted; only their $700 win on char 4
    assert r.winnings_for("B") == 700


# ────────── random_fill ──────────


def _char_by_id(cid: int):
    return ROSTER_BY_ID[cid]


def test_random_fill_picks_only_affordable():
    rng = random.Random(0)
    # Tiny budget — only $200 chars are affordable
    pool = list(ROSTER)
    crew = random_fill(
        current_crew=[],
        remaining_budget=200,
        candidate_pool=pool,
        crew_size=4,
        rng=rng,
    )
    assert len(crew) == 1  # only one $200 character affordable after first pick
    assert crew[0].floor_cost == 200


def test_random_fill_skips_already_owned():
    rng = random.Random(0)
    already_own = [_char_by_id(10), _char_by_id(13)]  # Rook + Slim
    crew = random_fill(
        current_crew=already_own,
        remaining_budget=600,
        candidate_pool=list(ROSTER),
        crew_size=4,
        rng=rng,
    )
    crew_ids = [c.id for c in crew]
    # The starting crew is preserved; new picks don't duplicate them
    assert 10 in crew_ids and 13 in crew_ids
    assert crew_ids.count(10) == 1 and crew_ids.count(13) == 1


def test_random_fill_stops_at_crew_size_limit():
    """Hard upper bound: random_fill never returns more than crew_size.
    (We use a pool of all-$200 characters so the budget is never the binder —
    the crew_size cap is what we're isolating.)"""
    rng = random.Random(0)
    cheap_pool = [c for c in ROSTER if c.floor_cost <= 400]
    assert len(cheap_pool) >= 4  # sanity: roster has at least 4 affordable chars
    crew = random_fill(
        current_crew=[],
        remaining_budget=2000,
        candidate_pool=cheap_pool,
        crew_size=4,
        rng=rng,
    )
    assert len(crew) == 4


def test_random_fill_never_exceeds_crew_size_even_with_huge_pool():
    """Invariant: with any budget, any pool, crew length ≤ crew_size."""
    rng = random.Random(0)
    crew = random_fill(
        current_crew=[],
        remaining_budget=10_000,  # absurd budget
        candidate_pool=list(ROSTER),
        crew_size=4,
        rng=rng,
    )
    assert len(crew) <= 4


def test_random_fill_stops_when_pool_exhausted():
    rng = random.Random(0)
    tiny_pool = [_char_by_id(2)]  # one $200 character
    crew = random_fill(
        current_crew=[],
        remaining_budget=2000,
        candidate_pool=tiny_pool,
        crew_size=4,
        rng=rng,
    )
    assert len(crew) == 1
    assert crew[0].id == 2


def test_random_fill_deterministic_with_same_seed():
    pool = list(ROSTER)
    crew_a = random_fill([], 2000, pool, 4, random.Random(42))
    crew_b = random_fill([], 2000, pool, 4, random.Random(42))
    assert [c.id for c in crew_a] == [c.id for c in crew_b]


def test_random_fill_handles_budget_drained_mid_fill():
    """Player has $400. First pick is $400 → no budget left → stop."""
    rng = random.Random(0)
    only_400 = [c for c in ROSTER if c.floor_cost == 400]
    crew = random_fill([], 400, only_400, 4, rng)
    assert len(crew) == 1


def test_random_fill_returns_empty_list_when_no_pool():
    rng = random.Random(0)
    crew = random_fill([], 2000, [], 4, rng)
    assert crew == []


# ────────── multi-round scenario (round 1 + round 2 + fill) ──────────


def test_two_round_scenario_with_ties_and_fill():
    """Player A loses a tie in round 1, wins in round 2, gets random-filled
    the rest."""
    # Round 1: A and B both bid $700 on Rook (id 10). Tied → no winner.
    round_1 = [
        PlayerBid("A", 10, 700),
        PlayerBid("B", 10, 700),
        # A also bids on Slim alone
        PlayerBid("A", 13, 700),
        # B also bids on Vance alone
        PlayerBid("B", 4, 700),
    ]
    r1 = resolve_round(round_1)
    assert r1.tied_characters == [10]
    assert r1.winnings_for("A") == 700  # Slim
    assert r1.winnings_for("B") == 700  # Vance

    # A still has $1300, crew = [Slim]. Round 2: A bids $1100 on Rook (still
    # in pool since the tie), unopposed.
    round_2 = [PlayerBid("A", 10, 1100)]
    r2 = resolve_round(round_2)
    assert r2.wins == {"A": [BidWin("A", 10, 1100)]}

    # A crew so far = [Slim, Rook], spent = $1800, budget left = $200.
    # Random fill: only $200 chars affordable.
    rng = random.Random(7)
    a_crew = [_char_by_id(13), _char_by_id(10)]  # Slim + Rook
    a_pool = [c for c in ROSTER if c.id not in {13, 10, 4}]  # everyone but Slim/Rook/Vance
    filled = random_fill(a_crew, 200, a_pool, 4, rng)
    assert len(filled) == 3  # original 2 + one $200 random
    assert filled[-1].floor_cost == 200
