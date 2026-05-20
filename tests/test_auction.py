from __future__ import annotations

import json

import pytest

from heist.ai import AgentTurn
from heist.auction import (
    _resolve_round,
    _round_bid_prompt,
    _validate_round_bids,
    run_auction,
)
from heist.content import BANKROLL, ROSTER_BY_ID
from heist.state import Crew, TurnLog


def _char(cid: int):
    return ROSTER_BY_ID[cid]


@pytest.fixture(autouse=True)
def _no_turn_delay(monkeypatch):
    monkeypatch.setattr("heist.auction.TURN_DELAY_SECONDS", 0.0)


def test_resolve_round_uncontested_win():
    winners, ties = _resolve_round({0: [(_char(10), 700)]})
    assert winners == [(0, _char(10), 700)]
    assert ties == []


def test_resolve_round_clear_winner():
    winners, ties = _resolve_round({
        0: [(_char(10), 700)],
        1: [(_char(10), 800)],
    })
    assert winners == [(1, _char(10), 800)]
    assert ties == []


def test_resolve_round_tie_two_ais():
    winners, ties = _resolve_round({
        0: [(_char(10), 800)],
        1: [(_char(10), 800)],
    })
    assert winners == []
    assert ties == [([0, 1], _char(10), 800)]


def test_resolve_round_tie_three_ais():
    winners, ties = _resolve_round({
        0: [(_char(10), 700)],
        1: [(_char(10), 700)],
        2: [(_char(10), 700)],
    })
    assert winners == []
    assert ties == [([0, 1, 2], _char(10), 700)]


def test_resolve_round_mixed_chars():
    winners, ties = _resolve_round({
        0: [(_char(10), 800), (_char(8), 200), (_char(9), 500)],
        1: [(_char(10), 700), (_char(8), 200)],
        2: [(_char(9), 400)],
    })
    assert winners == [
        (0, _char(9), 500),
        (0, _char(10), 800),
    ]
    assert ties == [([0, 1], _char(8), 200)]


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
                    {"character_id": 10, "bid": 1100},
                    {"character_id": 13, "bid": 1100},
                ]
            },
            pool=[_char(10), _char(13)],
            crew_so_far=[],
            bankroll=2000,
        )


def test_validate_bid_on_owned_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {"bids": [{"character_id": 10, "bid": 700}]},
            pool=[_char(10), _char(13)],
            crew_so_far=[_char(10)],
            bankroll=BANKROLL,
        )


def test_validate_bid_on_not_in_pool_rejected():
    with pytest.raises(ValueError):
        _validate_round_bids(
            {"bids": [{"character_id": 10, "bid": 700}]},
            pool=[_char(13)],
            crew_so_far=[],
            bankroll=BANKROLL,
        )


def test_validate_pass_returns_empty_list_pass_true():
    bids, did_pass = _validate_round_bids(
        {"pass": True, "bids": [{"character_id": 10, "bid": 700}]},
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
    assert result.bankrolls_spent == {0: 1500, 1: 1600}
    assert result.rounds
    assert any(evt["type"] == "auction_round_resolved" for evt in broadcast_events)
    assert any(evt["type"] == "crew_known" for evt in turn_events)
    assert all(logs_per_ai[idx] for idx in logs_per_ai)
