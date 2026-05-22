from __future__ import annotations

import json

import pytest

from heist.ai import AgentTurn
from heist.auction import (
    _bid_correction_prompt,
    _resolve_round,
    _round_bid_prompt,
    _validate_round_bids,
    run_auction,
)
from heist.content import BANKROLL, ROSTER_BY_ID
from heist.state import Crew, TurnLog


def _char(cid: int):
    return ROSTER_BY_ID[cid]


def test_resolve_round_uncontested_win():
    winners, ties = _resolve_round({0: [(_char(10), 700_000)]})
    assert winners == [(0, _char(10), 700_000)]
    assert ties == []


def test_resolve_round_clear_winner():
    winners, ties = _resolve_round({
        0: [(_char(10), 700_000)],
        1: [(_char(10), 800_000)],
    })
    assert winners == [(1, _char(10), 800_000)]
    assert ties == []


def test_resolve_round_tie_two_ais():
    winners, ties = _resolve_round({
        0: [(_char(10), 800_000)],
        1: [(_char(10), 800_000)],
    })
    assert winners == []
    assert ties == [([0, 1], _char(10), 800_000)]


def test_resolve_round_tie_three_ais():
    winners, ties = _resolve_round({
        0: [(_char(10), 700_000)],
        1: [(_char(10), 700_000)],
        2: [(_char(10), 700_000)],
    })
    assert winners == []
    assert ties == [([0, 1, 2], _char(10), 700_000)]


def test_resolve_round_mixed_chars():
    winners, ties = _resolve_round({
        0: [(_char(10), 800_000), (_char(8), 200_000), (_char(9), 500_000)],
        1: [(_char(10), 700_000), (_char(8), 200_000)],
        2: [(_char(9), 400_000)],
    })
    assert winners == [
        (0, _char(9), 500_000),
        (0, _char(10), 800_000),
    ]
    assert ties == [([0, 1], _char(8), 200_000)]


def test_validate_under_floor_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {"bids": [{"character_id": 10, "bid": _char(10).floor_cost - 1}]},
            pool=[_char(10)],
            crew_so_far=[],
            bankroll=BANKROLL,
        )


def test_validate_total_over_bankroll_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {
                "bids": [
                    {"character_id": 10, "bid": 1_100_000},
                    {"character_id": 13, "bid": 1_100_000},
                ]
            },
            pool=[_char(10), _char(13)],
            crew_so_far=[],
            bankroll=2_000_000,
        )


def test_validate_bid_on_owned_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {"bids": [{"character_id": 10, "bid": 700_000}]},
            pool=[_char(10), _char(13)],
            crew_so_far=[_char(10)],
            bankroll=BANKROLL,
        )


def test_validate_bid_on_not_in_pool_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {"bids": [{"character_id": 10, "bid": 700_000}]},
            pool=[_char(13)],
            crew_so_far=[],
            bankroll=BANKROLL,
        )


def test_validate_pass_returns_empty_list_pass_true():
    bids, did_pass = _validate_round_bids(
        {"pass": True, "bids": [{"character_id": 10, "bid": 700_000}]},
        pool=[_char(10)],
        crew_so_far=[],
        bankroll=BANKROLL,
    )
    assert bids == []
    assert did_pass is True


def test_round_bid_prompt_mentions_available_pool():
    prompt = _round_bid_prompt(
        "smoke strategy",
        [_char(10), _char(13)],
        [_char(2)],
        1800,
        2,
        {"won": ["Rook"], "lost": ["Slim"], "tied": []},
    )
    assert "smoke strategy" in prompt
    assert "round 2" in prompt
    assert "Available characters" in prompt


class _AuctionStubAI:
    def __init__(self, target_ids: list[int]):
        self.target_ids = target_ids
        self.prompts_seen: list[str] = []

    def ask(self, prompt: str) -> AgentTurn:
        self.prompts_seen.append(prompt)
        available_ids = {
            int(part.split("=", 1)[1].split(",", 1)[0])
            for part in prompt.splitlines()
            if part.strip().startswith("- id=")
        }
        bids = []
        for cid in self.target_ids:
            if cid not in available_ids:
                continue
            char = _char(cid)
            bids.append({
                "character_id": cid,
                "bid": char.floor_cost,
                "rationale": f"Target {char.name}.",
            })
        return AgentTurn(
            text=json.dumps({
                "bids": bids,
                "pass": not bids,
                "reasoning": "Pre-planned target list.",
            }),
            session_id="stub-session",
        )


def test_bid_correction_prompt_contains_pool_and_error():
    from heist.content import ROSTER_BY_ID
    pool = [ROSTER_BY_ID[10], ROSTER_BY_ID[13]]
    prompt = _bid_correction_prompt("Bid 800 for Rook below floor 700000", pool, 1_500_000)
    assert "bid was rejected" in prompt
    assert "Bid 800 for Rook below floor 700000" in prompt
    assert "id=10" in prompt
    assert "id=13" in prompt
    assert "1500000" in prompt


class _FailFirstStubAI:
    """Returns below-floor bids on first call, valid bids on subsequent calls."""

    def __init__(self, target_id: int):
        self.target_id = target_id
        self.calls: list[str] = []

    def ask(self, prompt: str) -> AgentTurn:
        self.calls.append(prompt)
        char = _char(self.target_id)
        if len(self.calls) == 1:
            # First attempt: bid way below floor
            payload = {
                "bids": [{"character_id": self.target_id, "bid": 1, "rationale": "test"}],
                "pass": False,
                "reasoning": "First bad attempt.",
            }
        else:
            # Correction attempt: bid at floor
            payload = {
                "bids": [
                    {"character_id": self.target_id, "bid": char.floor_cost,
                     "rationale": "corrected"}
                ],
                "pass": False,
                "reasoning": "Corrected bid.",
            }
        return AgentTurn(text=json.dumps(payload), session_id="stub-session")


def test_run_auction_retries_on_invalid_bids():
    """AI that bids below floor on first attempt should get a correction prompt
    and succeed on the retry — not be permanently excluded."""
    failing_ai = _FailFirstStubAI(target_id=10)  # Rook, floor $700k
    other_ai = _AuctionStubAI([13])              # Slim, no overlap
    logs_per_ai: dict[int, list[TurnLog]] = {0: [], 1: []}
    turn_events: list[dict] = []
    broadcast_events: list[dict] = []

    result = run_auction(
        [failing_ai, other_ai],
        ["strategy A", "strategy B"],
        logs_per_ai,
        lambda ai_idx, evt: turn_events.append({**evt, "ai_idx": ai_idx}),
        broadcast_events.append,
        snapshot_fn=None,
        max_rounds=8,
    )

    # AI 0 should have won Rook despite the first bad attempt
    crew_0_ids = [c.id for c in result.crews[0].members]
    assert 10 in crew_0_ids, "Rook should be in AI 0's crew after correction"
    # The failing AI should have been sent a correction prompt
    assert len(failing_ai.calls) >= 2, "Should have at least 2 calls (original + correction)"
    assert "bid was rejected" in failing_ai.calls[1]


def test_run_auction_failed_bids_not_permanent_exclusion():
    """An AI that exhausts all retries on bad bids in round 1 should still
    be able to bid in round 2 and acquire crew."""

    class _AlwaysFailThenPassStubAI:
        """Fails validation on all attempts in round 1, submits valid bids in round 2+."""

        def __init__(self, target_id: int):
            self.target_id = target_id
            self.calls: list[str] = []

        def ask(self, prompt: str) -> AgentTurn:
            self.calls.append(prompt)
            char = _char(self.target_id)
            # Round 1 original + 2 retries all fail; round 2+ succeed
            round_1_calls = [c for c in self.calls if "round 1" in c or "bid was rejected" in c]
            in_round_1 = len(round_1_calls) <= 3 and "round 2" not in prompt
            if in_round_1:
                payload = {
                    "bids": [{"character_id": self.target_id, "bid": 1, "rationale": "bad"}],
                    "pass": False,
                    "reasoning": "Bad round 1 attempt.",
                }
            else:
                payload = {
                    "bids": [
                        {"character_id": self.target_id, "bid": char.floor_cost,
                         "rationale": "good"}
                    ],
                    "pass": False,
                    "reasoning": "Good round 2 bid.",
                }
            return AgentTurn(text=json.dumps(payload), session_id="stub-session")

    stubborn_ai = _AlwaysFailThenPassStubAI(target_id=10)
    other_ai = _AuctionStubAI([13])  # different character, no conflict
    logs_per_ai: dict[int, list[TurnLog]] = {0: [], 1: []}

    result = run_auction(
        [stubborn_ai, other_ai],
        ["strategy A", "strategy B"],
        logs_per_ai,
        lambda ai_idx, evt: None,
        lambda evt: None,
        snapshot_fn=None,
        max_rounds=8,
    )

    # AI 0 should eventually get crew (from round 2+)
    assert len(result.crews[0].members) > 0, \
        "AI that failed round 1 should still get crew in later rounds"


class _HangingStubAI:
    """Simulates a hung/timed-out backend call: every ask raises.

    Mirrors the real failure that froze a campaign — a codex-mini bid call that
    blocked past its timeout and raised. The auction must recover (skip the bid)
    rather than propagate the exception and freeze the synchronized conductor.
    """

    def __init__(self) -> None:
        self.calls = 0

    def ask(self, prompt: str) -> AgentTurn:
        self.calls += 1
        raise TimeoutError("simulated hung AI call")


def test_run_auction_recovers_from_raising_ai_call():
    """A raising/hung ai.ask must NOT abort the auction. The failing AI skips
    its bid (acquires nothing, stays eligible), the healthy AI still wins crew,
    and a turn_end is still emitted so the UI doesn't hang on turn_start."""
    hanging_ai = _HangingStubAI()
    healthy_ai = _AuctionStubAI([13])  # Slim — no conflict
    logs_per_ai: dict[int, list[TurnLog]] = {0: [], 1: []}
    turn_events: list[dict] = []

    # Should return normally despite AI 0 raising on every call.
    result = run_auction(
        [hanging_ai, healthy_ai],
        ["strategy A", "strategy B"],
        logs_per_ai,
        lambda ai_idx, evt: turn_events.append({**evt, "ai_idx": ai_idx}),
        lambda evt: None,
        snapshot_fn=None,
        max_rounds=8,
    )

    assert hanging_ai.calls >= 1, "hanging AI should have been called and recovered"
    assert result.crews[0].members == [], "hanging AI should acquire nothing"
    assert 13 in [c.id for c in result.crews[1].members], "healthy AI still wins crew"
    assert any(
        e["type"] == "turn_end" and e["ai_idx"] == 0 for e in turn_events
    ), "turn_end must still be emitted for the failed call (UI not stuck)"


def test_run_auction_end_to_end_with_stub_ais():
    ais = [
        _AuctionStubAI([2, 6, 8, 10]),
        _AuctionStubAI([9, 11, 12, 14]),
    ]
    logs_per_ai: dict[int, list[TurnLog]] = {0: [], 1: []}
    turn_events: list[dict] = []
    broadcast_events: list[dict] = []

    result = run_auction(
        ais,
        ["smoke A", "smoke B"],
        logs_per_ai,
        lambda ai_idx, evt: turn_events.append({**evt, "ai_idx": ai_idx}),
        broadcast_events.append,
        snapshot_fn=None,
        max_rounds=8,
    )

    assert isinstance(result.crews[0], Crew)
    assert isinstance(result.crews[1], Crew)
    assert [c.id for c in result.crews[0].members] == [2, 6, 8, 10]
    assert [c.id for c in result.crews[1].members] == [9, 11, 12, 14]
    assert result.bankrolls_spent == {0: 1_500_000, 1: 1_600_000}
    assert result.rounds
    assert any(evt["type"] == "auction_round_resolved" for evt in broadcast_events)
    assert any(evt["type"] == "crew_known" for evt in turn_events)
    assert all(logs_per_ai[idx] for idx in logs_per_ai)
