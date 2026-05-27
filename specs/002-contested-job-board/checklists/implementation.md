# Implementation Quality Checklist

**Feature:** [tasks.md](../tasks.md) — Contested Job Board

## Two-lane rule (CLAUDE.md § "The two lanes")

- [ ] Board, pick order, claims, contested losses, and the consumed set are **emitted as events** from the engine — not computed in the browser.
- [ ] The viewer (`shell.js`, `job.html`) renders board state only from events; it never reconstructs which jobs are on the board or who won a contested job.
- [ ] Round snapshot + campaign record persist board/claims/consumed so replay & resume need no recomputation.

## Determinism (CLAUDE.md § "System owns deterministic mechanics")

- [ ] `build_board` and contention are pure functions of (seed, round_idx, standings); same inputs → identical board.
- [ ] Per-round rng is seeded from campaign seed + round_idx (no global `random` calls in board logic).

## Concurrency

- [ ] The shared consumed set is conductor-owned; per-AI `Campaign.consumed_jobs` mirrors it under `gamestate.lock`.
- [ ] The board stage runs **before** the parallel heist stage; no team starts a heist before its job is claimed.

## Code quality (project conventions)

- [ ] `mypy heist/ agents.py demo.py` clean — no `Any`-leak, no `# type: ignore`.
- [ ] `ruff` clean.
- [ ] `run_one_job(assigned_job=None)` preserves the existing single-heist path (back-compat).
- [ ] No hard-coded job lists in prompts — they take the round's board.

## Content

- [ ] Every job (old + new) floor take ≥ $1M; reward climbs with difficulty; 4-Hard jobs are the top takes.
- [ ] Each new job has a `locations_art.csv` row and complete fields.
