"""Round-based cross-AI hiring auction."""

from __future__ import annotations

import contextlib
import sys
import time
import traceback
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from heist.ai import AgentTurn, HeistAI, parse_json_block
from heist.content import BANKROLL, ROSTER, ROSTER_BY_ID
from heist.logs import log
from heist.serialize import crew_to_dict
from heist.state import Character, Crew, TurnLog

EmitPerAIFn = Callable[[int, dict], None]
EmitBroadcastFn = Callable[[dict], None]
SnapshotFn = Callable[[dict], None] | None

_BID_MAX_RETRIES = 2

_TRADECRAFT = """\
What you know about this work:

  • Every job is a profile of four challenge types — Electronic (cameras,
    networks, electronic locks), Physical (vaults, safes, structural),
    Confrontation (guards, armed response), and Social (blending in, talking
    your way through). Each one rates None, Low, Medium, or Hard.

  • Crew members have skill ratings in those areas — Low, Medium, or High.
    A specialist hits their level. A Hard challenge needs a High to clear
    alone, no exceptions.

  • Two crew members with skill in the same area work above the sum of their
    parts: pair them and you act at one level higher than the higher one,
    capped at High. Two Mediums together hit High. Two Lows together hit
    Medium. This is the move that makes a tight budget work — and it's how
    you cover a Hard area without paying for a $1,100 High specialist.

  • The exit always matters. A High Driver covers any escape; no driver
    means running on foot, and that limits which jobs you'll survive.

  • A Hard challenge with no High coverage and no two Mediums to pair on it
    is a walk into a wall. Plan around them or don't take the job."""


def _format_char_for_bid(c: Character) -> str:
    skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
    return f"  - id={c.id}, name={c.name!r}, skills=({skills}), floor=${c.floor_cost}"


def _round_bid_prompt(
    strategy: str,
    pool: list[Character],
    crew_so_far: list[Character],
    bankroll: int,
    round_num: int,
    last_result: dict[str, list[str]] | None,
) -> str:
    have = [f"{c.name} (cost ${c.floor_cost})" for c in crew_so_far]
    pool_lines = [_format_char_for_bid(c) for c in pool]
    last_section = ""
    if last_result is not None:
        last_section = (
            "\nLast round results (yours):\n"
            f"  Won:  {last_result.get('won', [])}\n"
            f"  Lost: {last_result.get('lost', [])}\n"
            f"  Tied: {last_result.get('tied', [])}\n"
        )
    return (
        f"You are the Heist AI, round {round_num} of crew bidding.\n\n"
        f"{_TRADECRAFT}\n\n"
        f"Player's strategy:\n---\n{strategy}\n---\n\n"
        f"Your crew so far ({len(crew_so_far)}/4):\n  {have or '(none yet)'}\n"
        f"Your bankroll: ${bankroll}\n"
        f"{last_section}\n"
        f"Available characters (these are the ones still in the pool):\n"
        + "\n".join(pool_lines)
        + "\n\nBid on any subset of available characters, or pass. "
        "Highest unique bid wins; ties refund all bidders and the character "
        "returns next round. You can save money for later rounds. "
        "Reply with ONLY JSON:\n"
        "{\n"
        '  "bids": [{"character_id": <int>, "bid": <int>>=floor, '
        '"rationale": "<why>"}],\n'
        '  "pass": <bool>,\n'
        '  "reasoning": "<short summary of your round-level strategy>"\n'
        "}"
    )


def _bid_correction_prompt(
    error: str, pool: list[Character], bankroll: int
) -> str:
    pool_lines = "\n".join(_format_char_for_bid(c) for c in pool)
    return (
        f"Your bid was rejected: {error}\n\n"
        "Reminder: bid amounts are full dollar values matching or exceeding "
        "each character's floor (e.g., floor=$700000 means bid at least "
        "700000, not 700 or 7000).\n\n"
        f"Your remaining bankroll: ${bankroll}\n\n"
        f"Still available:\n{pool_lines}\n\n"
        "Please correct your bids and reply with ONLY JSON:\n"
        "{\n"
        '  "bids": [{"character_id": <int>, "bid": <int>>=floor, '
        '"rationale": "<why>"}],\n'
        '  "pass": <bool>,\n'
        '  "reasoning": "<short summary>"\n'
        "}"
    )


def _call(
    ai: HeistAI,
    prompt: str,
    label: str,
    logs: list[TurnLog],
    ai_idx: int,
    emit_per_ai: EmitPerAIFn | None = None,
) -> AgentTurn:
    if emit_per_ai:
        emit_per_ai(ai_idx, {
            "type": "turn_start",
            "label": label,
            "prompt": prompt,
            "ai_idx": ai_idx,
        })
    t0 = time.monotonic()
    try:
        turn = ai.ask(prompt)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        log.error(
            "ai_call_error",
            label=label,
            elapsed_ms=int(elapsed * 1000),
            prompt_len=len(prompt),
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        # Recovery: the backend already retried this call AI_MAX_ATTEMPTS times
        # (see heist/backends.py); reaching here means every attempt failed. A
        # dead/hung call must NOT freeze the synchronized campaign conductor, so
        # instead of propagating (which aborts the whole auction) we record the
        # elapsed time and return a no-bid fallback. The caller then emits
        # turn_end normally and this AI simply skips this bid round — it stays
        # eligible next round (same as exhausting the bid-correction retries).
        elapsed = time.monotonic() - t0
        logs.append(TurnLog(label=label, seconds=elapsed))
        return AgentTurn(
            text='{"pass": false, "bids": []}',
            session_id=getattr(ai, "session_id", None),
        )
    elapsed = time.monotonic() - t0
    logs.append(TurnLog(label=label, seconds=elapsed))
    print(f"  [round {label}: {elapsed:.1f}s]", file=sys.stderr)
    parsed_ok = False
    with contextlib.suppress(Exception):
        parse_json_block(turn.text)
        parsed_ok = True
    log.info(
        "ai_call",
        label=label,
        # elapsed_ms wraps the whole ai.ask (incl. any retries + pauses);
        # attempt_ms is the clean latency of the single attempt that succeeded.
        elapsed_ms=int(elapsed * 1000),
        attempts=getattr(ai, "last_attempts", 1),
        attempt_ms=getattr(ai, "last_attempt_ms", int(elapsed * 1000)),
        prompt_len=len(prompt),
        response_len=len(turn.text),
        parsed_ok=parsed_ok,
    )
    return turn


def _validate_round_bids(
    parsed: dict,
    pool: list[Character],
    crew_so_far: list[Character],
    bankroll: int,
) -> tuple[list[tuple[Character, int]], bool]:
    if parsed.get("pass") is True:
        return ([], True)

    pool_ids = {c.id for c in pool}
    owned_ids = {c.id for c in crew_so_far}
    bids: list[tuple[Character, int]] = []
    seen: set[int] = set()
    total = 0

    try:
        raw_bids = parsed.get("bids", [])
        if not isinstance(raw_bids, list):
            raise ValueError("bids must be a list")
        for raw in raw_bids:
            cid = int(raw["character_id"])
            if cid in seen:
                raise ValueError(f"Duplicate character id in bid list: {cid}")
            if cid not in pool_ids:
                raise ValueError(f"Bid on character not in pool: {cid}")
            if cid in owned_ids:
                raise ValueError(f"Bid on already-owned character: {cid}")
            char = ROSTER_BY_ID[cid]
            bid = int(raw["bid"])
            if bid < char.floor_cost:
                raise ValueError(
                    f"Bid {bid} for {char.name} below floor {char.floor_cost}"
                )
            bids.append((char, bid))
            seen.add(cid)
            total += bid
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    if total > bankroll:
        raise ValueError(f"Total bids ${total} exceed bankroll ${bankroll}")
    return (bids, False)


def _resolve_round(
    bids_by_ai: dict[int, list[tuple[Character, int]]],
) -> tuple[list[tuple[int, Character, int]], list[tuple[list[int], Character, int]]]:
    bids_per_char: dict[int, list[tuple[int, int]]] = defaultdict(list)
    chars_by_id: dict[int, Character] = {}
    for ai_idx, bids in bids_by_ai.items():
        for char, bid in bids:
            bids_per_char[char.id].append((ai_idx, bid))
            chars_by_id[char.id] = char

    winners: list[tuple[int, Character, int]] = []
    ties: list[tuple[list[int], Character, int]] = []
    for char_id in sorted(chars_by_id):
        char = chars_by_id[char_id]
        entries = sorted(
            bids_per_char[char_id],
            key=lambda item: (-item[1], item[0]),
        )
        top_bid = entries[0][1]
        top_bidders = [ai_idx for ai_idx, bid in entries if bid == top_bid]
        if len(top_bidders) == 1:
            winners.append((top_bidders[0], char, top_bid))
        else:
            ties.append((top_bidders, char, top_bid))
    return winners, ties


def _extract_round_result_for(
    ai_idx: int,
    winners: list[tuple[int, Character, int]],
    ties: list[tuple[list[int], Character, int]],
    bids_for_ai: list[tuple[Character, int]],
) -> dict[str, list[str]]:
    won_ids = {char.id for winner_ai, char, _ in winners if winner_ai == ai_idx}
    tied_ids = {char.id for tied_ai_idxs, char, _ in ties if ai_idx in tied_ai_idxs}
    won = [f"{char.name} (${bid})" for winner_ai, char, bid in winners if winner_ai == ai_idx]
    tied = [f"{char.name} (${bid})" for tied_ai_idxs, char, bid in ties if ai_idx in tied_ai_idxs]
    lost = [
        f"{char.name} (${bid})"
        for char, bid in bids_for_ai
        if char.id not in won_ids and char.id not in tied_ids
    ]
    return {"won": won, "lost": lost, "tied": tied}


@dataclass
class AuctionRoundRecord:
    round_num: int
    bids_by_ai: dict[int, list[tuple[int, int]]]
    winners: list[tuple[int, int, int]]
    ties: list[tuple[list[int], int, int]]
    bankrolls_after: dict[int, int]
    crews_after: dict[int, list[int]]
    done_ais: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_num": self.round_num,
            "bids_by_ai": self.bids_by_ai,
            "winners": self.winners,
            "ties": self.ties,
            "bankrolls_after": self.bankrolls_after,
            "crews_after": self.crews_after,
            "done_ais": self.done_ais,
        }


@dataclass
class AuctionResult:
    crews: dict[int, Crew]
    bankrolls_spent: dict[int, int]
    rounds: list[AuctionRoundRecord]
    logs_per_ai: dict[int, list[TurnLog]]


def _snapshot_auction(
    snapshot_fn: SnapshotFn,
    *,
    stage: str,
    round_num: int,
    pool: list[Character],
    crews: dict[int, list[Character]],
    bankrolls: dict[int, int],
    passed: set[int],
    rounds_log: list[AuctionRoundRecord],
) -> None:
    if snapshot_fn is None:
        return
    payload: dict[str, Any] = {
        "stage": stage,
        "round": round_num,
        "scene_idx": 0,
        "strategy": "",
        "session_id": None,
        "rng_state": None,
        "extras": {
            "auction_state": {
                "pool": [c.id for c in pool],
                "crews_by_ai": {i: [c.id for c in crew] for i, crew in crews.items()},
                "bankrolls": dict(bankrolls),
                "passed": sorted(passed),
                "rounds_log": [r.to_dict() for r in rounds_log],
            }
        },
    }
    try:
        snapshot_fn(payload)
    except Exception as exc:
        log.warn("auction_snapshot_failed", stage=stage, error=str(exc))


def run_auction(
    ais: list[HeistAI],
    strategies: list[str],
    logs_per_ai: dict[int, list[TurnLog]],
    emit_per_ai: EmitPerAIFn,
    emit_broadcast: EmitBroadcastFn,
    snapshot_fn: SnapshotFn = None,
    max_rounds: int = 8,
    *,
    initial_crews: dict[int, list[Character]] | None = None,
    initial_bankrolls: dict[int, int] | None = None,
    pool_override: list[Character] | None = None,
) -> AuctionResult:
    pool: list[Character] = list(pool_override) if pool_override is not None else list(ROSTER)
    crews: dict[int, list[Character]] = (
        {i: list(initial_crews[i]) for i in range(len(ais))}
        if initial_crews is not None
        else {i: [] for i in range(len(ais))}
    )
    effective_initial_bankrolls: dict[int, int] = (
        {i: initial_bankrolls[i] for i in range(len(ais))}
        if initial_bankrolls is not None
        else {i: BANKROLL for i in range(len(ais))}
    )
    bankrolls: dict[int, int] = dict(effective_initial_bankrolls)
    passed: set[int] = set()
    rounds_log: list[AuctionRoundRecord] = []
    last_result_per_ai: dict[int, dict[str, list[str]]] = {}
    min_floor = min((c.floor_cost for c in pool), default=0) if pool else 0

    for ai_idx in range(len(ais)):
        logs_per_ai.setdefault(ai_idx, [])

    for round_num in range(1, max_rounds + 1):
        # AIs are active this round if they still need crew, haven't chosen to
        # stop bidding (passed), can afford at least the cheapest character,
        # and there are still characters to bid on.
        active = [
            i for i in range(len(ais))
            if len(crews[i]) < 4
            and i not in passed
            and bankrolls[i] >= min_floor
            and pool
        ]
        if not active:
            break

        bids_by_ai: dict[int, list[tuple[Character, int]]] = {}
        for ai_idx in active:
            prompt = _round_bid_prompt(
                strategies[ai_idx],
                pool,
                crews[ai_idx],
                bankrolls[ai_idx],
                round_num,
                last_result_per_ai.get(ai_idx),
            )
            turn = _call(
                ais[ai_idx],
                prompt,
                f"bid_round_{round_num}",
                logs_per_ai[ai_idx],
                ai_idx,
                emit_per_ai,
            )
            valid_bids: list[tuple[Character, int]] = []
            did_pass: bool = False
            parsed: dict[str, object] = {}

            # Bid validation with correction loop.
            #
            # On any parse or business-rule failure (e.g. bids below floor,
            # over bankroll, unknown character id) we send the exact error back
            # to the AI as a correction prompt and retry up to _BID_MAX_RETRIES
            # times. This recovers the common hallucination where the AI writes
            # bid amounts in the wrong unit (e.g. $800 instead of $800,000).
            #
            # Failure modes and how each is handled:
            #
            #   • Malformed JSON: parse_json_block raises → send correction,
            #     retry. If all retries exhausted, parsed stays {} and
            #     valid_bids stays [] — the AI skips this round.
            #
            #   • Business rule violation (below floor, over bankroll, etc.):
            #     _validate_round_bids raises ValueError with a human-readable
            #     message → same correction-and-retry flow.
            #
            #   • Explicit pass ("pass": true): _validate_round_bids returns
            #     ([], True) — did_pass becomes True and the AI is added to
            #     `passed`, removing it from all future rounds. This is the
            #     ONLY path that permanently ends an AI's bidding.
            #
            # Exhausting retries skips the round but does NOT add to `passed`.
            # The AI will appear in `active` again next round and bid fresh.
            for attempt in range(_BID_MAX_RETRIES + 1):
                try:
                    parsed = parse_json_block(turn.text)
                except Exception as exc:
                    error_msg = f"Response was not valid JSON: {exc}"
                    log.warn(
                        "invalid_round_json",
                        ai_idx=ai_idx,
                        round_num=round_num,
                        attempt=attempt,
                        error=error_msg,
                    )
                    parsed = {}
                    if attempt < _BID_MAX_RETRIES:
                        turn = _call(
                            ais[ai_idx],
                            _bid_correction_prompt(
                                error_msg, pool, bankrolls[ai_idx]
                            ),
                            f"bid_round_{round_num}_retry_{attempt + 1}",
                            logs_per_ai[ai_idx],
                            ai_idx,
                            emit_per_ai,
                        )
                        continue
                    break  # all retries exhausted — skip this round
                try:
                    valid_bids, did_pass = _validate_round_bids(
                        parsed, pool, crews[ai_idx], bankrolls[ai_idx]
                    )
                    break  # valid response — exit retry loop
                except ValueError as exc:
                    error_msg = str(exc)
                    log.warn(
                        "invalid_round_bids",
                        ai_idx=ai_idx,
                        round_num=round_num,
                        attempt=attempt,
                        error=error_msg,
                    )
                    if attempt < _BID_MAX_RETRIES:
                        turn = _call(
                            ais[ai_idx],
                            _bid_correction_prompt(
                                error_msg, pool, bankrolls[ai_idx]
                            ),
                            f"bid_round_{round_num}_retry_{attempt + 1}",
                            logs_per_ai[ai_idx],
                            ai_idx,
                            emit_per_ai,
                        )
                        continue
                    # All retries exhausted. Skip this round — do NOT add to
                    # `passed`. The AI gets another chance next round.
                    break

            parsed_bids = parsed.get("bids", [])
            if not isinstance(parsed_bids, list):
                parsed_bids = []
            # Only an explicit "pass": true adds the AI to `passed` (permanent).
            # Invalid bids / exhausted retries leave the AI eligible next round.
            if did_pass:
                passed.add(ai_idx)
            elif valid_bids:
                bids_by_ai[ai_idx] = valid_bids
            emit_per_ai(ai_idx, {
                "type": "turn_end",
                "label": f"bid_round_{round_num}",
                "seconds": logs_per_ai[ai_idx][-1].seconds,
                "parsed": {
                    "round": round_num,
                    "bids": [
                        {
                            "character_id": char.id,
                            "bid": bid,
                            "rationale": (
                                parsed_bids[idx].get("rationale", "")
                                if idx < len(parsed_bids) else ""
                            ),
                        }
                        for idx, (char, bid) in enumerate(valid_bids)
                    ],
                    "pass": did_pass,
                    "reasoning": parsed.get("reasoning", ""),
                    "remaining_roster": [c.id for c in pool],
                    "your_crew_so_far": [c.id for c in crews[ai_idx]],
                    "your_bankroll": bankrolls[ai_idx],
                },
                "response": turn.text,
                "ai_idx": ai_idx,
            })

        winners, ties = _resolve_round(bids_by_ai)
        for ai_idx, char, bid in winners:
            crews[ai_idx].append(char)
            bankrolls[ai_idx] -= bid
            pool.remove(char)

        for ai_idx in range(len(ais)):
            if len(crews[ai_idx]) >= 4:
                passed.add(ai_idx)

        done_ais = sorted({
            i for i in range(len(ais))
            if len(crews[i]) >= 4 or i in passed or bankrolls[i] < min_floor or not pool
        })
        record = AuctionRoundRecord(
            round_num=round_num,
            bids_by_ai={
                ai_idx: [(char.id, bid) for char, bid in bids]
                for ai_idx, bids in bids_by_ai.items()
            },
            winners=[(ai_idx, char.id, bid) for ai_idx, char, bid in winners],
            ties=[([*ai_idxs], char.id, bid) for ai_idxs, char, bid in ties],
            bankrolls_after=dict(bankrolls),
            crews_after={i: [c.id for c in crew] for i, crew in crews.items()},
            done_ais=done_ais,
        )
        rounds_log.append(record)
        emit_broadcast({
            "type": "auction_round_resolved",
            "round": round_num,
            "winners": [
                {"char_id": char.id, "ai_idx": ai_idx, "bid": bid}
                for ai_idx, char, bid in winners
            ],
            "ties": [
                {"char_id": char.id, "ai_idxs": ai_idxs, "bid": bid}
                for ai_idxs, char, bid in ties
            ],
            "bankrolls_after": dict(bankrolls),
            "crews_after": {i: [c.id for c in crew] for i, crew in crews.items()},
            "done_ais": done_ais,
        })

        for ai_idx in active:
            last_result_per_ai[ai_idx] = _extract_round_result_for(
                ai_idx,
                winners,
                ties,
                bids_by_ai.get(ai_idx, []),
            )

        _snapshot_auction(
            snapshot_fn,
            stage=f"auction_round_{round_num}",
            round_num=round_num,
            pool=pool,
            crews=crews,
            bankrolls=bankrolls,
            passed=passed,
            rounds_log=rounds_log,
        )

    final_crews: dict[int, Crew] = {}
    for ai_idx in range(len(ais)):
        crew = Crew(members=crews[ai_idx])
        final_crews[ai_idx] = crew
        emit_per_ai(ai_idx, {"type": "crew_known", "crew": crew_to_dict(crew)})

    _snapshot_auction(
        snapshot_fn,
        stage="auction_complete",
        round_num=len(rounds_log),
        pool=pool,
        crews=crews,
        bankrolls=bankrolls,
        passed=passed,
        rounds_log=rounds_log,
    )

    return AuctionResult(
        crews=final_crews,
        bankrolls_spent={i: effective_initial_bankrolls[i] - bankrolls[i] for i in range(len(ais))},
        rounds=rounds_log,
        logs_per_ai=logs_per_ai,
    )
