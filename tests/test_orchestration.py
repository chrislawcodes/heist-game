"""Tests for the campaign conductor's board stage.

Populated by feature 003 (scouting-depth-rotation) — specifically US1's parallel
scout fan-out and per-team error containment. Lives alongside test_campaign.py
which covers the higher-level multi-round behavior (US4 / US5).
"""

from __future__ import annotations

import time

from heist.orchestration import _run_parallel_scout_turns
from heist.state import ScoutState

# ── US1: parallel scout fan-out ────────────────────────────────────────────


def test_parallel_scout_runs_concurrently_not_serially():
    """3 teams each take ~0.3s to scout; total elapsed should be ~0.3s (parallel),
    not ~0.9s (serial). stagger=0 so the test doesn't pay the production 30s
    rate-limit-friendly stagger."""
    delay = 0.3

    def scout_one(_ai_idx: int) -> tuple[ScoutState, int]:
        time.sleep(delay)
        ss = ScoutState(free_probes=10, probes_spent_free=4)
        return ss, 4

    t0 = time.monotonic()
    scout_states, probes_spent = _run_parallel_scout_turns(
        [0, 1, 2], scout_one, stagger_seconds=0,
    )
    elapsed = time.monotonic() - t0

    # Parallel should be ~delay (with overhead), not 3 * delay. Cap at 1.5×.
    assert elapsed < delay * 1.5, f"board stage took {elapsed:.2f}s — appears serial"
    assert set(scout_states.keys()) == {0, 1, 2}
    assert probes_spent == {0: 4, 1: 4, 2: 4}


def test_parallel_scout_one_failure_does_not_block_others():
    """If one team's scout raises, the other teams still return; the failing team
    gets probes_spent=0 (sorts to the front of pick_order — they rush blind) and
    a default ScoutState."""
    def scout_one(ai_idx: int) -> tuple[ScoutState, int]:
        if ai_idx == 1:
            raise RuntimeError("boom: simulated scout failure")
        ss = ScoutState(free_probes=10, probes_spent_free=3)
        return ss, 3

    scout_states, probes_spent = _run_parallel_scout_turns(
        [0, 1, 2], scout_one, stagger_seconds=0,
    )

    assert probes_spent == {0: 3, 1: 0, 2: 3}
    assert scout_states[0].probes_spent_free == 3
    assert scout_states[2].probes_spent_free == 3
    # Failing team got a default (empty) ScoutState — no reveals, picks blind.
    assert scout_states[1].probes_spent_free == 0
    assert scout_states[1].reveals == {}


def test_parallel_scout_empty_active_list_returns_empty():
    """No active teams → no work, no errors."""
    scout_states, probes_spent = _run_parallel_scout_turns(
        [], lambda _i: (ScoutState(), 0), stagger_seconds=0,
    )
    assert scout_states == {}
    assert probes_spent == {}


def test_parallel_scout_staggers_submissions():
    """stagger_seconds delays each subsequent submission. With 3 teams + stagger
    0.1s, total elapsed should be ≥ 2 * 0.1 (= 0.2s) — the stagger between A/B
    and B/C — plus the longest single scout. Confirms the rate-limit guard fires."""
    delay = 0.05    # individual scout takes 50ms
    stagger = 0.15  # 150ms stagger between submissions

    def scout_one(_ai_idx: int) -> tuple[ScoutState, int]:
        time.sleep(delay)
        return ScoutState(free_probes=10, probes_spent_free=2), 2

    t0 = time.monotonic()
    _run_parallel_scout_turns([0, 1, 2], scout_one, stagger_seconds=stagger)
    elapsed = time.monotonic() - t0

    # We slept stagger × 2 between submissions (after A, after B) → at least 2 × stagger.
    assert elapsed >= 2 * stagger * 0.9, (
        f"elapsed {elapsed:.3f}s — appears not to have staggered (expected ≥ {2*stagger}s)"
    )
    # But not fully serialized: ≤ 2 × stagger + delay × 2 (with slack).
    assert elapsed < 2 * stagger + delay * 3, (
        f"elapsed {elapsed:.3f}s — appears serialized rather than staggered+parallel"
    )
