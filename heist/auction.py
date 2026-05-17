"""Phase 2 bid resolution as a pure module.

Two functions: `resolve_round` runs one blind-bid round; `random_fill` does the
post-round-2 chaos fill. Neither knows anything about AIs, sessions, or the
runner — they just take data and return data. The Phase 2 runner (when it
lands) will orchestrate: collect AI bid submissions, call resolve_round,
update player state, repeat for round 2, call random_fill, hand crews to the
scene loop.

See the "Phase 2 bid resolution" section of heist_game_design.md for the rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from heist.state import Character


@dataclass(frozen=True)
class PlayerBid:
    """One bid: player P offers $A for character C."""
    player_id: str
    character_id: int
    amount: int


@dataclass(frozen=True)
class BidWin:
    """A character won by a player in one round, at the bid amount."""
    player_id: str
    character_id: int
    amount_paid: int


@dataclass
class RoundResult:
    """Outcome of one auction round.

    - `wins`: per-player list of BidWins (player → characters they took).
    - `tied_characters`: character ids that had ≥2 top-bidders → no winner.
    - `uncontested_characters`: ids with exactly one bidder (subset of wins'
      character ids, surfaced for casting-reveal narration).
    """
    wins: dict[str, list[BidWin]] = field(default_factory=dict)
    tied_characters: list[int] = field(default_factory=list)
    uncontested_characters: list[int] = field(default_factory=list)

    def winnings_for(self, player_id: str) -> int:
        return sum(w.amount_paid for w in self.wins.get(player_id, []))

    def characters_won(self) -> set[int]:
        return {w.character_id for wins in self.wins.values() for w in wins}


def resolve_round(bids: list[PlayerBid]) -> RoundResult:
    """One blind-bid round. Highest unique bid wins each character; ties at
    the top mean no one wins that character (it stays in the pool).

    The function does not validate per-player bankroll constraints — the caller
    must enforce `sum(bids per player) ≤ bankroll` before calling. Doing so
    here would couple the auction to game-wide state it doesn't need.
    """
    by_char: dict[int, list[PlayerBid]] = {}
    for b in bids:
        by_char.setdefault(b.character_id, []).append(b)

    wins: dict[str, list[BidWin]] = {}
    tied: list[int] = []
    uncontested: list[int] = []

    for char_id, char_bids in by_char.items():
        max_amount = max(b.amount for b in char_bids)
        top = [b for b in char_bids if b.amount == max_amount]
        if len(top) == 1:
            w = top[0]
            wins.setdefault(w.player_id, []).append(
                BidWin(
                    player_id=w.player_id,
                    character_id=char_id,
                    amount_paid=w.amount,
                )
            )
            if len(char_bids) == 1:
                uncontested.append(char_id)
        else:
            tied.append(char_id)

    return RoundResult(
        wins=wins,
        tied_characters=sorted(tied),
        uncontested_characters=sorted(uncontested),
    )


def random_fill(
    current_crew: list[Character],
    remaining_budget: int,
    candidate_pool: list[Character],
    crew_size: int,
    rng: random.Random,
) -> list[Character]:
    """Post-round-2 random fill. Draws uniformly from `candidate_pool`,
    skipping characters the player already owns and those they can't afford,
    until the crew hits `crew_size` or the affordable pool is exhausted.

    The Heist AI is intentionally NOT consulted here. The fill phase exists to
    inject randomness at the tail of a contested draft — it's a feature, not a
    fallback the AI should reason about.
    """
    crew = list(current_crew)
    budget = remaining_budget
    owned_ids = {c.id for c in crew}
    pool = [c for c in candidate_pool if c.id not in owned_ids]

    while len(crew) < crew_size:
        affordable = [c for c in pool if c.floor_cost <= budget]
        if not affordable:
            break
        pick = rng.choice(affordable)
        crew.append(pick)
        budget -= pick.floor_cost
        pool = [c for c in pool if c.id != pick.id]

    return crew
