"""US1 — the single-AI campaign shows a rotating board (subset of the pool) each
round, attempted jobs are consumed globally, and no attempted job ever repeats."""
import random

from heist.board import BOARD_SIZE, build_board
from heist.campaign import run_campaign
from heist.content import DEFAULT_PROMPT, JOBS
from heist.stub_responses import build_stub_ai


def test_board_rotation_and_consumption_no_repeats():
    campaign, extras = run_campaign(DEFAULT_PROMPT, build_stub_ai(), rounds=10)
    results = campaign.round_results
    assert results, "campaign produced no rounds"

    attempted = [r.job_name for r in results]
    # SC-002: no attempted job repeats across the campaign.
    assert len(attempted) == len(set(attempted)), f"repeat job attempted: {attempted}"

    attempted_so_far: set[str] = set()
    for r in results:
        assert 1 <= len(r.board) <= BOARD_SIZE, f"board size {len(r.board)} out of range"
        # The attempted job was on that round's board.
        assert r.job_name in r.board, f"{r.job_name!r} not on its board {r.board}"
        # No already-attempted (consumed) job reappears on a later board.
        assert attempted_so_far.isdisjoint(r.board), (
            f"consumed job re-offered: {attempted_so_far & set(r.board)}"
        )
        attempted_so_far.add(r.job_name)

    # Every attempted job is in the campaign's global consumed set.
    assert set(attempted) <= campaign.consumed_jobs


def test_build_board_full_drain_never_repeats_an_attempt():
    """Drive build_board across many rounds, consuming the picked job each time:
    no job is ever offered after it's been attempted, and the pool drains cleanly."""
    consumed: set[str] = set()
    attempted: list[str] = []
    banked = 0
    for rnd in range(len(JOBS) + 2):
        board = build_board(
            JOBS, consumed, rnd, len(JOBS), banked,
            trailing_bankroll=5_000_000, rng=random.Random(rnd),
        )
        if not board:
            break
        assert len(board) <= BOARD_SIZE
        for name in board:
            assert name not in consumed, f"{name} re-offered after being attempted"
        pick = board[0]
        attempted.append(pick)
        consumed.add(pick)
        banked += 2_000_000
    assert len(attempted) == len(set(attempted))
    # Pool fully drains (every job eventually consumed) within pool-size rounds.
    assert len(consumed) == len(JOBS)
