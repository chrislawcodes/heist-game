"""Rolling job slate for campaign mode.

Each round, a filtered subset of jobs is offered to the AIs. Jobs carry over
if unchosen (up to STALENESS_LIMIT rounds), then fall off. New jobs fill slots
from the eligible pool based on round number and tier unlock rules.
"""
from __future__ import annotations

import random

from heist.content import JOB_TIER_UNLOCK_ROUND
from heist.state import Job

STALENESS_LIMIT = 3  # rounds a job can sit on the slate before it falls off


def build_slate(
    all_jobs: list[Job],
    round_idx: int,
    num_ais: int,
    attempted_job_names: set[str],
    slate_state: dict,
    rng: random.Random | None = None,
) -> list[Job]:
    """Build the job slate for this round. Mutates slate_state in place.

    Args:
        all_jobs: Full job pool (e.g. JOBS from heist/content.py).
        round_idx: 0-based current round index.
        num_ais: Number of AI players. Slate size = 2 * num_ais.
        attempted_job_names: Jobs already completed - never re-added.
        slate_state: Dict with keys "current_slate" (list[str]) and
            "rounds_on_slate" (dict[str, int]). Mutated in place.
        rng: Optional seeded Random for reproducible tests.

    Returns:
        List of Job objects on the slate for this round.
    """
    rng = rng or random.Random()
    jobs_by_name = {job.name: job for job in all_jobs}
    target_size = max(0, 2 * num_ais)
    current = slate_state.setdefault("current_slate", [])
    ages = slate_state.setdefault("rounds_on_slate", {})

    expired_this_round = {
        name for name in current if ages.get(name, 0) >= STALENESS_LIMIT
    }

    # 1. Expire stale jobs (on slate >= STALENESS_LIMIT rounds).
    current[:] = [j for j in current if j not in expired_this_round]
    for name in list(ages):
        if name not in current:
            del ages[name]

    # 2. Remove attempted jobs (safety check).
    current[:] = [j for j in current if j not in attempted_job_names]
    for name in list(ages):
        if name not in current:
            del ages[name]

    # 3. Build eligible pool.
    on_slate = set(current)
    eligible = [
        job for job in all_jobs
        if job.name not in attempted_job_names
        and job.name not in on_slate
        and job.name not in expired_this_round
        and (not job.tier or JOB_TIER_UNLOCK_ROUND.get(job.tier, 1) <= round_idx + 1)
    ]

    # 4. Fill slate up to target size.
    slots_needed = max(0, target_size - len(current))
    if slots_needed > 0 and eligible:
        picks: list[Job] = []
        if not current:
            picks.append(eligible[0])
            eligible = eligible[1:]
            slots_needed -= 1
        if slots_needed > 0 and eligible:
            picks.extend(rng.sample(eligible, min(slots_needed, len(eligible))))
        current.extend(job.name for job in picks)

    # 5. Increment age for all jobs on slate (including newly added).
    for name in current:
        ages[name] = ages.get(name, 0) + 1

    # 6. Return Job objects in slate order.
    return [jobs_by_name[name] for name in current if name in jobs_by_name]
