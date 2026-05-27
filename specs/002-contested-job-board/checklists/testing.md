# Testing Quality Checklist

**Feature:** [tasks.md](../tasks.md) — Contested Job Board

## Preflight (run before every push; `/ship` Step 3 reruns it)

- [ ] `python3 -m ruff check .` clean
- [ ] `mypy heist/ agents.py demo.py` clean
- [ ] `pytest -q` green

## Coverage by success criterion

- [ ] SC-001: 4-team 10-round stub campaign completes via the conductor harness — `tests/test_contention.py`.
- [ ] SC-002: no attempted job reappears across a full campaign — `test_contention.py` + `test_campaign_board.py`.
- [ ] SC-003: pool min take ≥ $1M; band-median take ascends {0,1,2,4 Hards}; 4-Hard jobs are the top two — `test_locations.py`.
- [ ] SC-004: every board ≤ 8 and ≥ affordable-minimum; trailing team picks first every round — `test_board.py` + `test_contention.py`.
- [ ] SC-005: killed-and-resumed campaign restores identical board/pick-order/consumed — `test_serialize_board.py`.
- [ ] SC-006: full preflight green.

## Determinism & edges

- [ ] Same seed → identical board (asserted).
- [ ] Board runs low (< 8, < team-count) handled without crash.
- [ ] All-tied banked (round 1) → deterministic ai_idx tiebreak.
- [ ] Single-AI campaign still works (contention no-op).

## Regression

- [ ] Existing campaign/runner/content/serialize tests updated and green (no silent deletions).
