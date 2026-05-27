"""Contested job board — pure, deterministic board construction & pick order.

Shared by the single-AI campaign loop (`heist/campaign.py`) and the multi-AI
conductor (`heist/orchestration.py`). No threads, no AI, no I/O: every function
is a pure function of (pool, consumed, round_idx, standings, seeded rng), so a
board is reproducible for replay, resume, and tests (two-lane rule + "system
owns deterministic mechanics").

Model
-----
Each round shows up to ``BOARD_SIZE`` jobs drawn from ``pool − consumed``:
  * **gated slots** — drawn from jobs whose ``tier_rank`` is within the ceiling
    unlocked by campaign progression (round + total banked), so early boards
    skew cheap-to-mid and the elite jackpots unlock late;
  * **wild slots** — drawn from *all* unconsumed jobs, so surprises (a reach
    jackpot to bank toward, an off-tier edge) can appear;
  * an **affordable guarantee** — at least ``min_affordable`` board jobs are
    attemptable for the trailing team, so no team is starved.

Pick order is trailing-team-first (ascending banked loot) — anti-snowball.
"""
from __future__ import annotations

import random

from heist.state import ChallengeLevel, Job

BOARD_SIZE = 8
WILD_SLOTS = 2
MIN_AFFORDABLE = 2

# Coarse crew-cost proxy by difficulty rank (used only for the starvation guard;
# it is a heuristic, not an exact min-crew solve — see plan Decision 5).
_EST_CREW_COST = {0: 600_000, 1: 1_000_000, 2: 1_800_000, 3: 3_500_000}


def _hard_count(job: Job) -> int:
    return sum(1 for v in job.profile.values() if v == ChallengeLevel.HARD)


def tier_rank(job: Job) -> int:
    """0..3 difficulty rank. Hard-count is the primary driver (it forces an
    expensive specialist per Hard); used for gating and the affordability proxy."""
    hc = _hard_count(job)
    if hc >= 4:
        return 3
    if hc >= 2:
        return 2
    if hc == 1:
        return 1
    return 0


def estimated_crew_cost(job: Job) -> int:
    """Coarse estimate of the crew needed to attempt this job (proxy from rank)."""
    return _EST_CREW_COST[tier_rank(job)]


def affordable(job: Job, bankroll: int) -> bool:
    """Could a team with ``bankroll`` plausibly field a crew for this job?"""
    return estimated_crew_cost(job) <= bankroll


def pick_order(standings: list[tuple[int, int]]) -> list[int]:
    """Return ai_idx ordered trailing-team-first: ascending banked loot, with a
    deterministic ai_idx tiebreak. ``standings`` = [(ai_idx, banked_loot)]."""
    return [ai for ai, _ in sorted(standings, key=lambda t: (t[1], t[0]))]


def unlocked_max_rank(round_idx: int, rounds_total: int, total_banked: int) -> int:
    """Highest ``tier_rank`` allowed in the *gated* slots this round. Rises with
    campaign progress and with how much loot has been banked across all teams,
    so elite (rank 3) only unlocks in the late campaign or once teams are rich."""
    rounds_total = max(1, rounds_total)
    frac = round_idx / rounds_total
    if frac < 0.3:
        by_round = 1
    elif frac < 0.6:
        by_round = 2
    else:
        by_round = 3
    by_banked = 1
    if total_banked >= 16_000_000:
        by_banked = 3
    elif total_banked >= 8_000_000:
        by_banked = 2
    return min(3, max(by_round, by_banked))


def _sample(rng: random.Random, items: list[Job], k: int,
            exclude: set[str]) -> list[Job]:
    """Deterministically pick up to k jobs from items, skipping excluded names."""
    pool = [j for j in items if j.name not in exclude]
    k = min(k, len(pool))
    return rng.sample(pool, k) if k > 0 else []


def build_board(
    pool: list[Job],
    consumed: set[str],
    round_idx: int,
    rounds_total: int,
    total_banked: int,
    *,
    size: int = BOARD_SIZE,
    wild_slots: int = WILD_SLOTS,
    min_affordable: int = MIN_AFFORDABLE,
    trailing_bankroll: int = 0,
    rng: random.Random,
) -> list[str]:
    """Build one round's board (list of job names) from ``pool − consumed``.

    Deterministic given ``rng``. If fewer than ``size`` unconsumed jobs remain,
    returns all of them (in pool order). Otherwise fills gated slots within the
    progression ceiling, wild slots from anything unconsumed, then enforces the
    affordable-minimum guarantee.
    """
    available = [j for j in pool if j.name not in consumed]
    if len(available) <= size:
        return [j.name for j in available]

    ceiling = unlocked_max_rank(round_idx, rounds_total, total_banked)
    gated_pool = [j for j in available if tier_rank(j) <= ceiling]

    chosen: list[Job] = []
    chosen_names: set[str] = set()

    # Gated slots — within the unlocked ceiling (fall back to all if too few).
    n_gated = max(0, size - wild_slots)
    gated_source = gated_pool if len(gated_pool) >= n_gated else available
    for j in _sample(rng, gated_source, n_gated, chosen_names):
        chosen.append(j)
        chosen_names.add(j.name)

    # Wild slots — anything unconsumed not already chosen.
    for j in _sample(rng, available, size - len(chosen), chosen_names):
        chosen.append(j)
        chosen_names.add(j.name)

    # Affordable-minimum guarantee: ensure ≥ min_affordable attemptable jobs by
    # swapping out the priciest unaffordable picks for affordable ones.
    def _afford(j: Job) -> bool:
        return affordable(j, trailing_bankroll)

    aff_count = sum(1 for j in chosen if _afford(j))
    if aff_count < min_affordable:
        need = min_affordable - aff_count
        candidates = [
            j for j in available
            if j.name not in chosen_names and _afford(j)
        ]
        swap_out = sorted(
            (j for j in chosen if not _afford(j)),
            key=tier_rank, reverse=True,
        )
        for repl in _sample(rng, candidates, need, chosen_names):
            if not swap_out:
                break
            drop = swap_out.pop(0)
            chosen.remove(drop)
            chosen_names.discard(drop.name)
            chosen.append(repl)
            chosen_names.add(repl.name)

    return [j.name for j in chosen]
