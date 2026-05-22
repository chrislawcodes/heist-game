"""Campaign loop: multi-round heist saga."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from heist.ai import HeistAI
from heist.content import BANKROLL
from heist.logs import log
from heist.prompts import _summary_prompt
from heist.runner import (
    EmitFn,
    TurnLog,
    _call,
    _draft_crew,
    run_one_job,
)
from heist.state import Campaign, HeistState, RoundResult

NOTORIETY_MEDIUM = 3    # Phase 3b: high-value jobs gated (not yet active)
NOTORIETY_HIGH = 6      # Phase 3b: between-round capture (not yet active)
NOTORIETY_CRITICAL = 9  # Raid - campaign ends early


def settle_round(
    campaign: Campaign,
    state: HeistState,
    notoriety_decay: int = 1,
) -> bool:
    """Update campaign in-place after one round. Returns True = end campaign."""
    campaign.banked_loot += state.final_take
    campaign.notoriety = max(0, campaign.notoriety + state.heat - notoriety_decay)

    if state.escape_success is False:
        job_crew_ids = {m.id for m in state.crew.members}
        campaign.standing_crew = [
            c for c in campaign.standing_crew if c.id not in job_crew_ids
        ]
        log.info(
            "crew_captured",
            captured_ids=list(job_crew_ids),
            remaining=len(campaign.standing_crew),
        )

    campaign.round_results.append(RoundResult(
        round_idx=campaign.round_idx,
        job_name=state.job.name,
        take=state.final_take,
        aborted=state.aborted,
        escape_success=state.escape_success,
        heat=state.heat,
    ))
    campaign.attempted_job_names.add(state.job.name)

    crew_wiped = len(campaign.standing_crew) == 0
    raid = campaign.notoriety >= NOTORIETY_CRITICAL
    if crew_wiped:
        log.info("campaign_end_crew_wiped")
    if raid:
        log.info("campaign_end_notoriety_raid", notoriety=campaign.notoriety)
    return crew_wiped or raid


OnRoundFn = Callable[[Campaign, HeistState, dict[str, Any]], None] | None


def run_campaign(
    strategy: str,
    ai: HeistAI,
    *,
    rounds: int = 10,
    rng: random.Random | None = None,
    on_round: OnRoundFn = None,
    emit: EmitFn = None,
) -> tuple[Campaign, list[dict[str, Any]]]:
    """Draft once, then loop run_one_job up to `rounds` times."""
    rng = rng or random.Random()
    logs: list[TurnLog] = []

    draft_extras: dict[str, Any] = {}
    crew = _draft_crew(strategy, ai, logs, extras=draft_extras, emit=emit)
    summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
    casting_summary = summary_turn.text

    campaign = Campaign(
        rounds_total=rounds,
        bankroll=BANKROLL - crew.total_cost,
        banked_loot=0,
        standing_crew=list(crew.members),
        notoriety=0,
        attempted_job_names=set(),
        round_results=[],
    )
    round_extras_list: list[dict[str, Any]] = []

    for _n in range(rounds):
        if not campaign.standing_crew:
            log.info("campaign_loop_no_crew", round=_n)
            break
        result = run_one_job(strategy, ai, campaign, rng=rng, emit=emit)
        if result is None:
            log.info("campaign_loop_jobs_exhausted", round=_n)
            break
        state, extras = result
        extras["casting_summary"] = casting_summary
        round_extras_list.append(extras)
        ended = settle_round(campaign, state)
        if on_round:
            on_round(campaign, state, extras)
        if ended:
            break

    return campaign, round_extras_list
