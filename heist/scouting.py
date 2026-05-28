"""Scouting — pure logic for the per-round intel phase (Phase 4 P2).

Before committing to a job, the crew can scout the slate. Each free probe
(budget = crew size + best-driver bonus) reveals the EXACT 1-10 challenge score
of one (job, challenge-category). Published buckets stay visible as the free
estimate; scouting buys down the within-bucket uncertainty so the crew can
right-size and spot underdefended "edge" jobs.

Paid over-budget probes are deferred to a later slice; for now probes beyond the
free budget are dropped.
"""
from __future__ import annotations

import random

from heist.mechanics import roll_challenge_scores, score_to_bucket
from heist.state import Job, RevealLevel, ScoutState


def roll_slate_scores(
    jobs: list[Job], rng: random.Random
) -> dict[str, dict[str, int]]:
    """Roll hidden 1-10 challenge scores for every job on the slate, so the AI
    can scout any of them before picking. The picked job reuses its entry."""
    return {job.name: roll_challenge_scores(job.profile, job.tier, rng) for job in jobs}


def apply_probes(
    scout_state: ScoutState,
    slate_scores: dict[str, dict[str, int]],
    probes: list[dict],
) -> list[dict]:
    """Apply the AI's probe list to `scout_state`, revealing exact scores within
    the free budget. Returns the `scouted` event payloads to emit (in order)."""
    events: list[dict] = []
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        job = probe.get("job")
        category = probe.get("category")
        if not isinstance(job, str) or not isinstance(category, str):
            continue
        scores = slate_scores.get(job)
        if scores is None or category not in scores:
            continue  # unknown job/category — drop
        if scout_state.level(job, category) >= RevealLevel.EXACT:
            continue  # fully known — no-op, no budget spent
        if scout_state.budget_remaining() <= 0:
            continue  # out of free probes (paid overflow deferred)
        scout_state.probes_spent_free += 1
        # Two-step ladder: one probe advances one level (HIDDEN→BUCKET→EXACT).
        # First probe on a (job, category) reveals the bucket (Low/Med/Hard);
        # a second reveals the exact 1-10 score.
        new_level = scout_state.reveal(job, category)
        score = scores[category]
        ev: dict = {
            "type": "scouted",
            "job": job,
            "category": category,
            "reveal_level": new_level.name,
            "bucket": score_to_bucket(score).name,
            "probes_remaining_free": scout_state.budget_remaining(),
        }
        if new_level >= RevealLevel.EXACT:
            ev["score"] = score
            scout_state.exact_scores.setdefault(job, {})[category] = score
        events.append(ev)
    return events
