# Research: Scouting Depth + Board Rotation

Three decisions warranted investigation before coding. Each section captures the question, the options weighed, and the chosen path.

---

## Question 1: Parallelism mechanism for scout turns

**Context**: Today `_pick_for` runs `_run_scout_turn` + `pick_job_from_board` sequentially per team inside `resolve_contention`. With N=3 teams and each scout averaging ~5–15s (LLM call), the board stage takes 15–45s. The new pick-order rule (least probes first) requires every team to scout before any team picks, so sequential scouting would compound the wait. We need concurrency.

**Options investigated**:

1. **`concurrent.futures.ThreadPoolExecutor`** (stdlib threads)
   - Pros: stdlib only; scout work is I/O-bound (LLM calls via `codex exec` subprocess or HTTP) — GIL is irrelevant for I/O; per-team `ScoutState` / `logs` / emit channel are independent → no shared mutation; trivial to layer onto the existing `_run_scout_turn` signature; failures isolated via `Future.exception()`.
   - Cons: must explicitly catch + log per-team exceptions; tests need a small "deliberately slow" stub to confirm wall-clock overlap.

2. **`asyncio` + `await asyncio.gather(...)`**
   - Pros: native concurrency story.
   - Cons: requires recoloring the entire conductor + LLM backends as async. The `codex exec` subprocess wrapper, `make_emit_fn`, `gamestate.broadcast`, the logs pipeline — all currently sync. Touching all of that for one stage is wildly out of scope.

3. **`multiprocessing`**
   - Pros: parallel CPU.
   - Cons: scout work is I/O (no CPU benefit); pickling per-team state to subprocesses adds complexity; subprocess startup ~hundreds of ms; emit/log channels would need IPC. Strictly worse here.

**Decision**: ThreadPoolExecutor.

**Rationale**: I/O-bound, per-team state is independent, stdlib, smallest possible blast radius. The conductor's other stages (hiring, heist) stay sequential where they need to be.

**Notes on failure handling**: if one team's scout future raises, the conductor logs the exception, treats that team's `probes_spent = 0`, leaves their `ScoutState` unchanged (whatever they already had persists), and continues. The team is then sorted to the *front* of the pick order (rushers go first); they pick blind.

---

## Question 2: Mix-aware replenish heuristic

**Context**: When carrying over `(8 − N)` jobs and drawing `N` new, we want to bias the new draws to diversify the board, not just re-roll randomly. Without bias, a streak of e.g. confrontation-heavy carryovers + a random draw could yield a 7-confrontation board, which is boring and unbalanced.

**Options investigated**:

1. **Inverse-frequency weighting on dominant category + reward tier** (chosen)
   - Compute the carryover's distribution along two axes: (a) dominant challenge category (per job: the category whose `ChallengeLevel` is highest; ties broken by fixed order `electronic → physical → confrontation → social`), and (b) reward tier (3 bins from `reward_range[1]`: low/mid/elite).
   - For each candidate `j` in `build_board`'s gated pool: `weight(j) = 1 + 1/(1 + count_of_j_dominant_in_carryover) + 1/(1 + count_of_j_tier_in_carryover)`.
   - Weighted-sample without replacement for `N` draws.
   - Pros: deterministic given the seeded RNG; layers cleanly on top of existing `build_board` gating; one tunable formula; fast (O(pool_size) per round).
   - Cons: heuristic over-corrects on tiny boards; can be tuned by the constants if it bothers.

2. **Hard caps per category** ("at most 4 confrontation-heavy jobs on the board")
   - Pros: bright-line guarantees.
   - Cons: brittle (carryover could already violate the cap); more knobs; doesn't address reward diversity unless we add more caps.

3. **Variance-minimizing exhaustive search**
   - Pros: provably optimal.
   - Cons: combinatorial; replay/resume reproducibility becomes annoying; way overkill.

**Decision**: Inverse-frequency weighting on dominant category + reward tier.

**Rationale**: Simple, tunable, deterministic, doesn't fight existing gating. The constants in the weight formula are dials we can adjust after playtest without changing the structure.

**Open dial**: if it under-corrects (boards still feel same-y), we can square the inverse term: `1/(1 + count)^2`. Spec SC-006 ("std-dev of category-count across 8 jobs ≤ 1.5") is the verification target.

---

## Question 3: Carrier for persisted reveals — UI delivery

**Context**: With persisted scout state on `Campaign.per_ai_scout_state`, when a round starts the team already has prior reveals. The Job tab's existing renderer reads `boardByAI` (the round's board, from the `job_board` event) and `scoutedByAI` / `revealByAI` (from `scouted` events as they arrive). We need to get the persisted reveals into the UI **without** having the UI reconstruct state from old sub-games.

**Options investigated**:

1. **New `scout_state_loaded` event at round start, per team** (chosen)
   - Emit a single event per team containing `{ reveals: {...}, exact_scores: {...} }` after `job_board` and before scouting starts.
   - Job tab adds a handler: merge these into `revealByAI` and `scoutedByAI`.
   - Pros: explicit; aligns with the two-lanes rule (engine emits, UI consumes); back-compat is easy (old games never emit it → no-op).
   - Cons: one new event type; the Job tab handler grows by one branch.

2. **Inline persisted reveals into the `job_board` payload**
   - Make `job_board` carry an additional `prior_reveals` field per team.
   - Pros: one fewer event type.
   - Cons: the `job_board` event today is broadcast to a per-team sub-game stream; per-team `prior_reveals` is naturally what each team sees, so this could work, but it bundles two concerns ("here is the board" + "here is your prior intel"). Slightly less clean than a dedicated event.

3. **UI reconstructs from prior sub-games' events**
   - The Job tab could fetch the prior round's sub-game and replay its `scouted` events to rebuild `scoutedByAI` / `revealByAI`.
   - Pros: no engine-side change.
   - Cons: **violates the two-lanes rule**. The UI lane "never reconstructs context the events didn't provide." Hard no.

**Decision**: A new `scout_state_loaded` event per team, emitted right after `job_board` at round start.

**Rationale**: Clean separation of concerns; the `job_board` event keeps its single responsibility (the board composition); persistence delivery is a clear, named event the UI handler can attach to.

**Backward-compat**: old sub-games / pre-feature saves never emit this event; the new handler does nothing if the event isn't present. Replays of old games still render as today.

---

## Smaller open items (resolved without dedicated research)

- **Probe-budget exact value**: 10 (Decision 3 in plan.md). Tune after playtest if the strategic balance feels off — bumping to 12 or dropping to 9 is a 1-line change.
- **Driver scout bonus**: dropped for MVP (folded into the flat budget). If drivers need a scouting differentiator, add a `driver_scout_bonus()` perk later as `+N` on top of the flat 10; the math doesn't change.
- **Visual indicator for "scouted prior round" vs "this round"**: nice-to-have; deferred to Phase C tasks (subtle dim/tint on prior reveals). Data model already supports it.
