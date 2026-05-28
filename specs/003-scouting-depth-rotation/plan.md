# Implementation Plan: Scouting Depth + Board Rotation

**Branch**: `feat/scouting-depth-rotation` | **Date**: 2026-05-27 | **Spec**: [spec.md](./spec.md)

## Summary

Restructure the campaign conductor so all teams' scout turns fire in parallel; re-order the per-round pick order by "fewest probes used first" (bankroll tiebreak); raise the free probe budget; carry over unpicked jobs each round with a mix-aware replenish; and persist each team's scouting intel across rounds. Implemented in three MVP-first phases with staging review between phases.

---

## Technical Context

**Language/Version**: Python 3.14 (framework Python; `python3 -m heist serve`)
**Primary Dependencies**: Standard library only. New use of `concurrent.futures.ThreadPoolExecutor` (stdlib) for parallel scout turns.
**Storage**: JSON files under `state/games/` (no DB). Campaign records serialized via `heist/serialize.py`.
**Testing**: `pytest` (currently 243 passing). Use existing fixtures + add tests for the new pick-order, board-carryover, and persistence behavior.
**Target Platform**: Local long-running Python HTTP server (`heist serve`). UI is vanilla HTML/JS in `heist/web/`.
**Performance Goals** (from spec):
- Board stage wall-clock ≤ 1.2× a single team's scout-turn time (SC-001).
- Probe budget ≥ 10 per team (SC-003).
- ≥ 62% of round N+1's board is carryover (SC-004).
- Mix-aware: stddev of category-count across 8 jobs ≤ 1.5 (SC-006).

**Constraints** (from spec + project CLAUDE.md):
- Locked Phase 4: hidden 1–10 scores, score-margin resolution, +1-point collaboration, convex pricing.
- 21-character roster, `BOARD_SIZE = 8`, escape model from #85.
- "Two lanes" rule: every state change must be emitted as a discrete event from the AI lane; UI never reconstructs.
- Files conflict-prone: `runner.py`, `server.py`, `shell.js` — touch carefully; we touch `orchestration.py` (effectively conflict-prone too).

**Scale/Scope**: Typical campaign = 3 teams, 3–7 rounds. The conductor manages per-team threads for scouting and per-team sub-games for hiring/heist.

---

## Constitution Check

**Status**: SKIPPED — no constitution / governance file found at `CONSTITUTION.md`, `docs/constitution.md`, or `.specify/memory/constitution.md`. The repo's CLAUDE.md "Locked Design Decisions" act as the operative constraints (carried into FR-010 and Technical Context above).

---

## Architecture Decisions

### Decision 1: Parallel scouts via `concurrent.futures.ThreadPoolExecutor`

**Chosen**: Threads (stdlib `concurrent.futures.ThreadPoolExecutor`), one worker per active team, fan-out/fan-in pattern. Each future runs `_run_scout_turn` for its team and returns the resulting `ScoutState` plus a probes-spent count.

**Rationale**:
- Scout turns are LLM I/O (subprocess `codex exec` or HTTP). I/O-bound concurrency is exactly what the GIL handles well; no need for processes.
- Stdlib only — no new dependency, fits the project's "minimal deps" character.
- The existing `_run_scout_turn(crew, available_jobs, slate_scores, ai, logs, emit)` is naturally thread-safe per team (each team has its own `logs_per_ai[i]` and `make_emit_fn(i)`), and writes to its own `scout_state` object.

**Alternatives Considered**:
- **asyncio**: would require re-coloring the entire conductor + LLM backends as async; too invasive for the value.
- **multiprocessing**: heavy (process startup, pickling state), no concurrency win over threads for I/O.

**Tradeoffs**:
- Pros: minimal blast radius — only the board stage flips from sequential to fan-out/fan-in; existing scout function unchanged.
- Cons: must explicitly handle per-future exceptions so one team's scout failure doesn't kill the round; tests for "thread-safety per team" need to be deliberate.

---

### Decision 2: `pick_order` signature extension

**Chosen**: Extend `board.pick_order(standings)` to accept tuples of `(ai_idx, probes_spent, banked_loot)` and sort by `(probes_spent, banked_loot, ai_idx)` ascending. Update its single call site in `orchestration.py`.

**Rationale**:
- Keeps pick order a **pure function** of public per-team facts.
- Adds the new ranking dimension without breaking the existing tiebreak (banked-loot ascending preserves the soft anti-snowball).

**Alternatives Considered**:
- Wrap pick_order with a higher-level selector elsewhere: more indirection, no benefit.
- Sort by `(probes_spent, ai_idx)` only (drop bankroll tiebreak): the spec explicitly keeps anti-snowball as a tiebreak (FR-002).

**Tradeoffs**:
- Pros: tiny diff, easy to unit-test against synthetic standings.
- Cons: every caller and test that built the old tuple shape must update; a tiny ripple but real.

---

### Decision 3: Probe budget = `len(crew) + best driver's 1–10 score`

**Chosen**: `free_probe_budget(members)` returns `len(members) + max(_member_score(m, "driver") for m in members)` (0 driver if no driver). Replaces the old `len(members) + driver_scout_bonus(members)` formula (which only added +1/+2/+3 for the bucket).

**Rationale**:
- Varies per team — investment in crew size AND driver skill both translate directly into scouting capacity. A typical 4-crew with a High driver (~9 score) gets 13 probes; a 4-crew with no driver gets 4.
- Pairs with the new fewest-probes-first pick order (US2): high-driver teams have *more probes available*, but spending them costs them in pick order. The strategic axis becomes "how many of my budget do I spend?" — and a deep-driver crew genuinely has more to work with.
- Replaces the bucket-based bonus with the actual 1–10 score, on theme with Phase 4's score-based mechanics.

**Alternatives Considered**:
- Flat 10 (originally implemented): uniform across teams. Rejected — flattens the crew-composition signal; doesn't reward investment in drivers.
- `len(crew) + driver_scout_bonus` (old formula, +1/+2/+3 bucket): too narrow a band; a top driver feels barely better than a mid one.
- Collaboration-aware effective score (`effective_skill_score`): two-driver crews would get +1. Considered but adds complexity; single best driver is the cleaner read.

**Tradeoffs**:
- Pros: directly couples scouting capacity to crew investment; reads as fair (more crew + better driver = more probes); the budget number visible in the scout prompt becomes a meaningful per-team data point.
- Cons: total round time scales with biggest team's budget × scout time; with the 30s rate-limit stagger between calls, a wide budget difference isn't a wall-clock issue per round (each team scouts in parallel) but matters for the AI's *spend* choices.

---

### Decision 4: Board carryover with persisted rolled scores

**Chosen**: Extend `Campaign` with two new fields:
- `carryover_board: list[str]` — job names from the prior round's board that were not consumed (= unpicked).
- `persistent_slate_scores: dict[str, dict[str, int]]` — per-job rolled hidden challenge scores (`job_name → category → 1–10`). Rolled once when a job first enters the board; **carried** until that job is consumed.

Each round's board = `carryover + N new draws (mix-aware)`; the conductor merges `persistent_slate_scores` for carryover with a fresh roll for new draws, and the union is used as `slate_scores` for the round.

**Rationale**:
- Two-lanes-aligned: the carryover state lives on the Campaign (single source of truth); the UI sees it via the `job_board` event.
- Decouples the carryover question (which jobs) from the roll question (what hidden numbers). Persisting rolled scores is the **necessary** correlate for persisted reveals to stay truthful (US5 / FR-006).

**Alternatives Considered**:
- Attach rolled scores to a Job snapshot copy on the Campaign: more nesting, harder to serialize.
- Re-roll scores each round even for carried jobs: kills persistent reveals — a team's "scouted Hard" reveal would be revealing the *old* number, not the current one.

**Tradeoffs**:
- Pros: persistent intel becomes mathematically correct; the data model is flat and serializable.
- Cons: another field to round-trip; serialization additions in `serialize.py`.

---

### Decision 5: Mix-aware replenish heuristic

**Chosen**: When drawing the N new jobs, build a weighted random selection over `build_board`'s already-gated pool. Weights = inverse-frequency along two axes computed from the carryover:
- **Category emphasis**: for each job in the carryover, determine its "dominant" challenge category (the one whose `ChallengeLevel` is highest, ties broken by a fixed order). Tally the distribution. Bias new draws toward under-represented dominants.
- **Reward tier**: bin reward by 3 tiers (low/mid/elite) from `reward_range[1]`. Bias new draws toward under-represented tiers.

Weight per candidate = `1 + (1 / (1 + count_of_its_category_in_carryover)) + (1 / (1 + count_of_its_tier_in_carryover))`. Normalize, then weighted-sample without replacement for `N` draws.

**Rationale**:
- Cheap, deterministic given the seeded RNG (preserves replay/resume).
- Layers on top of `build_board`'s existing gating (campaign progress + wilds) — does not replace it.

**Alternatives Considered**:
- Hand-curated category caps ("at most 4 confrontation-heavy jobs"): brittle, more knobs.
- ML-style scoring on a richer feature vector: way overkill.

**Tradeoffs**:
- Pros: simple, tunable single formula; doesn't fight existing gating.
- Cons: heuristic may over-correct on tiny boards; reviewable in playtest.

---

### Decision 6: Persistent scouting on `Campaign.per_ai_scout_state`

**Chosen**: Add `Campaign.per_ai_scout_state: dict[int, ScoutState]` (ai_idx → ScoutState). `ScoutState` already carries the right fields (`reveals`, `exact_scores`, `rationale`, `free_probes`, `probes_spent_free`). Lift its lifecycle from per-round to per-campaign:
- Persist `reveals`, `exact_scores` (and the rolled-scores live on the Campaign).
- Reset `probes_spent_free` to 0 at the start of each round; set `free_probes` from the flat-10 budget.
- When the conductor enters the board stage, the per-team `ScoutState` it uses for `_run_scout_turn` is the team's persisted instance — fresh probes spent this round accumulate on top of prior reveals.

**Rationale**:
- One-line lifecycle lift; no new entity needed.
- `serialize.py`'s `scout_state_to_dict` / `scout_state_from_dict` already round-trip the fields; campaign serialization adds the per-team map.

**Alternatives Considered**:
- New `CampaignScoutHistory` entity: redundant given `ScoutState` already carries everything.
- Per-round scout state with a separate "history" snapshot: harder to merge new reveals into prior reveals.

**Tradeoffs**:
- Pros: minimal type churn; `ScoutState`'s methods (`level`, `scouted_score`, `reveal`) work unchanged.
- Cons: backward-compat — old saved campaigns lack the map; serializer defaults to empty.

---

### Decision 7: Conductor flow restructure (orchestration.py)

**Chosen**: Replace today's nested `_pick_for(ai_idx, ...)` that scouts-then-picks per team with a three-step board stage:
1. **Build round board**: take prior `carryover_board`; drop any consumed; draw `N` new via the mix-aware replenisher; compose final 8-job board; merge `persistent_slate_scores` (carryover) with a fresh roll for new draws.
2. **Emit + Parallel scout**: open each team's round sub-game, emit `job_board` (each team), then `ThreadPoolExecutor`-fan-out `_run_scout_turn(...)` per team (using their persisted `ScoutState`). Wait for all futures; collect `probes_spent` per team.
3. **Pick (sequential)**: compute pick order via `pick_order([(ai_idx, probes_spent[i], banked_loot[i]) ...])`. Walk in order; each team runs `pick_job_from_board(...)` against the remaining slate; existing contention resolution.

**Rationale**:
- Each step is a clear seam — easier to test and to checkpoint for resume.
- Parallel scouts only need to read shared inputs (the board) and write per-team state — no cross-team mutation in flight.

**Alternatives Considered**:
- Async coroutines with `await asyncio.gather(...)`: see Decision 1.

**Tradeoffs**:
- Pros: cleaner separation; the (now-removed) closure `_pick_for` is replaced by two named helpers (`_scout_one(ai_idx)`, `_pick_one(ai_idx)` — illustrative).
- Cons: real diff in `orchestration.py` (the conflict-prone file); must be careful with the resume path.

---

### Decision 8: Phase rollout (MVP-first)

**Chosen** — three sequential commits/PRs, each shippable end-to-end, with a staging review between:

| Phase | Stories | Touches | Shippable behavior |
|------|--------|---------|---------------------|
| **A — MVP** | US1, US2, US3 | mechanics.py, board.py, orchestration.py, prompts.py, tests | Parallel scouts + pick-order-by-probes (bankroll tiebreak) + flat 10-probe budget |
| **B — Carryover** | US4 | board.py, state.py, serialize.py, orchestration.py, prompts.py, tests | `(8 − N)` carryover with mix-aware replenish; rolled scores persist per carried job |
| **C — Persistence** | US5 | state.py, serialize.py, orchestration.py, scouting.py, web/tabs/job.html, prompts.py, tests | `Campaign.per_ai_scout_state` carries reveals across rounds; UI shows persisted reveals |

Each phase passes preflight + smoke + (B and C) a campaign run validating the persistence/carryover behavior.

---

## Project Structure

### Monolithic Python package + vanilla web frontend

```
heist/
├── orchestration.py         ← MAJOR: conductor board stage restructure (parallel scout, pick reorder, carryover wiring)
├── board.py                 ← pick_order signature; build_board carryover hooks; mix-aware replenish helper
├── state.py                 ← Campaign new fields (carryover_board, persistent_slate_scores, per_ai_scout_state); ScoutState lifecycle note
├── mechanics.py             ← free_probe_budget → flat 10 (replaces crew-size formula)
├── scouting.py              ← uses persisted ScoutState; minor adjustments if any
├── serialize.py             ← campaign_to_dict / campaign_from_dict additions for new Campaign fields
├── persist.py               ← (no change expected; round-trips via serialize.py)
├── prompts.py               ← _TRADECRAFT updates: 10-probe budget, least-probes-first pick order, carryover, persistent reveals
└── web/tabs/
    └── job.html             ← visual marker for "scouted last round" cells (Phase C)

tests/
├── test_board.py            ← pick_order with probes triples; carryover + mix-aware replenish (Phase B)
├── test_scouting.py         ← flat probe budget; persisted ScoutState across rounds (Phase C)
├── test_campaign.py         ← carryover + persistence end-to-end (stub campaign, 2 rounds)
└── test_orchestration.py    ← parallel scout (assert wall-clock ≤ 1.2× single-scout time with mocked delays) [new file]
```

**Structure Decision**: Pure heist/ package changes. No new files in `heist/`, one new test file (`test_orchestration.py`). UI touches limited to `web/tabs/job.html` in Phase C. No new dependencies.

---

## Notes on the "Two Lanes" rule

Every new state change is emitted from the engine as an event the UI can consume:
- `job_board` already covers the round board (extended in Phase B to include carryover markers as needed).
- `scouted` events fire as today; the UI's `boardByAI` (per #84) accumulates them. For persisted reveals (Phase C), the conductor emits the team's prior `reveals` either via an enriched `job_board` event (preferred — keeps the UI from reconstructing) or a new `scout_state` event at round start. **Decision finalized in research.md.**

---

## Risks & Open Items (resolved before tasks)

1. **Driver scout bonus**: drop or keep on top of 10? Resolved → drop for MVP, can re-add as +1 perk later if playtest shows drivers need a scouting differentiator.
2. **Mix heuristic weighting**: the proposed formula is the starting point; tunable post-playtest.
3. **Persisted-reveals UI**: do we need a visual marker that distinguishes "scouted this round" vs "scouted last round"? Recommendation: subtle dim/tint on prior-round reveals; finalize in Phase C tasks.
