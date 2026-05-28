# Implementation Quality Checklist

**Purpose**: Validate code quality during implementation.
**Feature**: [tasks.md](../tasks.md)

No constitution file in this repo — best-practices items are derived from the project's CLAUDE.md "Locked Design Decisions," the "Two Lanes" rule, and standard Python hygiene.

## Locked Design (do not touch)

- [ ] Phase 4's hidden 1–10 challenge scores, score-margin resolution, +1-point collaboration rule, and convex per-score pricing are **untouched**.
- [ ] The 21-character roster is unchanged.
- [ ] `BOARD_SIZE = 8` is unchanged.
- [ ] The escape mechanic from #85 (derived 0–6 difficulty vs the Driver's 1–10 score) is unchanged — no `escape_modifier` reintroduced.

## Two Lanes Rule

- [ ] Every new state change is **emitted as an event** by the engine (orchestration / runner). The UI never reconstructs.
- [ ] Persisted reveals reach the Job tab via the new `scout_state_loaded` event (per research.md § Question 3), not by the UI reading prior sub-games.
- [ ] No new logic in `heist/web/` reads game state outside of registered event handlers.

## Code Quality

- [ ] No `# type: ignore`, no `# noqa`, no broad `except Exception: pass` (the per-team scout exception handler logs via `log.warn(...)` and continues with `probes_spent=0` — that's intentional and bounded).
- [ ] Function names match existing style (snake_case; helpers prefixed with `_`).
- [ ] Logging via the existing `log` helper from `heist/logs.py`, not `print`.
- [ ] New helpers in `heist/board.py` and `heist/orchestration.py` keep small, named-purpose functions (`_scout_one`, `_pick_one`, `replenish_mix_aware`) — no giant nested closures.

## Concurrency

- [ ] `concurrent.futures.ThreadPoolExecutor` is the only added concurrency primitive. No `asyncio`, no `multiprocessing`.
- [ ] Each parallel scout future writes only to its own per-team state (`ScoutState`, per-team logs, per-team emit channel). No cross-team mutation in flight.
- [ ] Per-future exceptions are caught + logged; one team's failure does not abort the round.
- [ ] The picks phase remains **serial** — contention resolution requires it.

## Serialization / Backward Compat

- [ ] `campaign_from_dict` defaults the three new fields (`carryover_board`, `persistent_slate_scores`, `per_ai_scout_state`) to empty when keys are absent — pre-feature saved campaigns load and play resumes.
- [ ] `scout_state_loaded` event is additive — old UI (without the handler) ignores it; old replays (without the event) render exactly as before.
- [ ] `job_board` event payload extensions (if any) are additive and optional fields.

## Test Hygiene

- [ ] No test calls a live LLM. All US tests use stub agents or direct function calls.
- [ ] `tests/test_orchestration.py` (new) imports cleanly with `pytest` and tests the conductor logic via narrow harness, not a full server.
- [ ] Existing 243-test green baseline is preserved (no test removed unless it was specifically obsolete to the redesign — call those out in the commit).

## Files-In-Scope Discipline

- [ ] Only the files listed in plan-summary.md "Files In Scope" are modified. If another file truly needs a change, note it in the implementation report rather than touching it silently.
- [ ] No edits to `CLAUDE.md`, `AGENTS.md`, `MEMORY.md`, `README.md`, `heist_game_design.md`, `ARCHITECTURE.md` unless explicitly tasked.

## Performance

- [ ] Board-stage wall-clock with 3 active teams is ≤ 1.2 × the slowest single scout (SC-001).
- [ ] `replenish_mix_aware` runs in O(pool_size) per round — no nested loops over jobs × jobs.
