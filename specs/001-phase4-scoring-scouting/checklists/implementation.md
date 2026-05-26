# Implementation Quality Checklist

**Purpose:** Validate code quality during implementation
**Feature:** [tasks.md](../tasks.md)

(No constitution in repo — best-practices + `CLAUDE.md` project conventions.)

## Architecture (two-lane — CLAUDE.md)

- [ ] The engine emits every state change as an event; the UI only renders — no game state computed in `web/`
- [ ] Missing UI data is fixed by **emitting it from the engine**, never reconstructed in the browser
- [ ] `ScoutState` is the single source of truth for fog — both `prompts.py` and `serialize.py` gate on it (no second source)
- [ ] `Job` stays a frozen constant; rolled challenge scores live on `HeistState`, never mutated onto the Job

## Correctness

- [ ] Resolution is deterministic given (effective_score, challenge_score) — no randomness in the contest
- [ ] Collaboration is +1 **point** (best+1, cap 10), not +1 bucket, everywhere
- [ ] `score_floor_cost` matches the spec table to the dollar; no `base_cost`/`expected_floor_cost` callers remain
- [ ] Escape uses `effective_skill_bucket(driver)`; `escape_resolves` body unchanged (cascade not softened — project memory)
- [ ] Margin/heat bands match research.md Q1; heat rises on every non-clean outcome
- [ ] No prompt or serialize path exposes an **unscouted** exact challenge score; character scores are public

## Code style

- [ ] Consistent with existing module style (frozen dataclasses, pure functions in `mechanics.py`)
- [ ] No new dependencies (stdlib only)
- [ ] `mypy heist/ agents.py demo.py` clean; `ruff` clean
- [ ] No `@ts-ignore`-equivalent suppressions; no dead/commented-out code left behind

## Safety / scope

- [ ] `run_heist` and `run_campaign` still run end-to-end (FR-007) — verified with stub
- [ ] Legacy game records load without crashing (tolerant load); pre-Phase-4 in-flight games error rather than mis-resume
- [ ] Conflict-prone files (runner.py, server.py, shell.js, prompts.py, serialize.py, persist.py, locations, characters) edited by one task at a time
