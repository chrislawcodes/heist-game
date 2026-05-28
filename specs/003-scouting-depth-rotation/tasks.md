# Tasks: Scouting Depth + Board Rotation

**Prerequisites**: [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md), [plan-summary.md](./plan-summary.md), [spec-acceptance.md](./spec-acceptance.md), [research.md](./research.md), [quickstart.md](./quickstart.md)

## Format

`[ID] [P: file]? [Story]? Description`

- **[P: repo/relative/file.ext]** — parallel-safe; the file list is its scope so the implementer can detect overlap. Bare `[P]` is treated as serial.
- **[Story]** — US1 / US2 / US3 / US4 / US5 (matches spec.md priorities).
- File paths are repo-relative.

**Phase ordering note**: P1 stories are implemented in *dependency* order (US3 → US2 → US1), not the spec's numbering order — US1's parallel-scout orchestration consumes US2's new `pick_order` signature, and US2 calls `free_probe_budget` set by US3. The MVP ships when all three are done.

---

## Phase 1: Setup

**Purpose**: Confirm clean baseline + scaffold the new test file.

- [X] T001 Run preflight from worktree root to confirm clean baseline before any edits: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`. All green.
- [X] T002 [P: tests/test_orchestration.py] Create `tests/test_orchestration.py` with module-level imports (`import pytest`, the relevant heist helpers, `concurrent.futures`). Empty test placeholder so US1 tests have a home.

---

## Phase 2: Foundation

**Purpose**: Extend `Campaign` with the new persistent fields (defaulted empty). These block US4 and US5 but are harmless to add now — earlier P1 work can land without using them.

⚠️ **CRITICAL**: Phase 2 must be complete before US4/US5 begin. P1 stories (US1/2/3) do not depend on it.

- [X] T003 [heist/state.py] Add three new fields to the `Campaign` dataclass: `carryover_board: list[str] = field(default_factory=list)`, `persistent_slate_scores: dict[str, dict[str, int]] = field(default_factory=dict)`, `per_ai_scout_state: dict[int, "ScoutState"] = field(default_factory=dict)`. Place after the existing `consumed_jobs` field. No behavior wiring yet.
- [X] T004 [heist/serialize.py] In `campaign_to_dict` emit the 3 new keys (`carryover_board`, `persistent_slate_scores`, `per_ai_scout_state` — the last using `scout_state_to_dict` per entry); in `campaign_from_dict` read them with empty defaults via `d.get(..., ...)` for backward compat. Depends on T003.
- [X] T005 [tests/test_campaign.py] Add a round-trip test: build a Campaign with the 3 new fields populated → `campaign_to_dict` → `campaign_from_dict` → asserts. Also test that a pre-feature dict (missing the keys) loads with empty defaults (no crash). Depends on T004. *(Placed in tests/test_serialize_board.py with the existing campaign round-trip tests — better cohesion.)*

**Checkpoint**: Foundation ready — P2 stories can later attach behavior to these fields.

---

## Phase 3: User Story 3 — Bigger free probe budget (Priority: P1, part of MVP)

**Goal**: Each team gets a flat **10** free probes per round, regardless of crew size or driver.

**Independent Test**: `free_probe_budget()` returns 10 for every crew composition; the scout-turn prompt reports 10.

### Implementation for US3

- [X] T006 [heist/mechanics.py] [US3] Change `free_probe_budget(members)` (line ~191) to return a flat `10` (drop the `len(members) + driver_scout_bonus(members)` formula). Decide whether to keep the parameter for ABI stability (recommended: keep param but ignore it; mark with a `# noqa: ARG001` is forbidden — instead, prefix the param with `_` so the unused-arg lint stays clean, or just drop the param and update callers). Find callers via `grep -n free_probe_budget heist/ -r` and update accordingly. *(Kept param, added docstring + `_ = members` hint.)*
- [X] T007 [P: tests/test_scouting.py] [US3] Add a test that `free_probe_budget()` returns 10 for: empty crew, 4 members no driver, 4 members with High driver, 6 members. Replace any existing test that asserted the old formula. *(Updated test_scouting.py and test_mechanics.py existing budget tests in place.)*

**Checkpoint**: US3 complete (budget = 10, independently testable).

---

## Phase 4: User Story 2 — Pick order by fewest probes used (Priority: P1, part of MVP)

**Goal**: Pick order is ascending by `probes_spent`, with `banked_loot` ascending as the first tiebreak and `ai_idx` ascending as the final tiebreak.

**Independent Test**: Pure-function unit tests on `pick_order` against synthetic standings.

### Implementation for US2

- [ ] T008 [heist/board.py] [US2] Change `pick_order(standings: list[tuple[int, int]]) -> list[int]` (line ~64) to accept `list[tuple[int, int, int]]` interpreted as `(ai_idx, probes_spent, banked_loot)`. Sort by `(probes_spent, banked_loot, ai_idx)` ascending. Update the docstring to reflect the new semantics and tiebreak chain. The single existing call site in `orchestration.py` will be updated in US1 (T012); leave a `# TODO: caller update in US1` comment if helpful — but do NOT update orchestration.py here.
- [ ] T009 [P: tests/test_board.py] [US2] Add `pick_order` unit tests: (a) ascending probes — `[(0,2,1_000_000),(1,7,500_000),(2,4,750_000)]` → `[0,2,1]`; (b) bankroll tiebreak — `[(0,4,1_000_000),(1,4,500_000)]` → `[1,0]`; (c) ai_idx tiebreak — `[(0,4,500_000),(1,4,500_000)]` → `[0,1]`; (d) all-zero-probes — falls through to bankroll then ai_idx; (e) empty input → `[]`.

**Checkpoint**: US2 complete (`pick_order` accepts probes-aware standings, unit-tested).

---

## Phase 5: User Story 1 — Parallel scouting (Priority: P1, completes MVP) 🎯

**Goal**: All teams' scout turns run concurrently in the board stage; collected `probes_spent` feeds the new `pick_order` from US2; picks run sequentially with the existing contention resolution.

**Independent Test**: Time the board stage end-to-end with a slow-mock scout; assert wall-clock ≤ 1.2 × single-scout time, not ~3×. Also: one team's mock raises → other teams complete + failing team's `probes_spent` treated as 0.

### Implementation for US1

- [ ] T010 [heist/orchestration.py] [US1] Refactor the existing `_pick_for(ai_idx, ...)` nested closure inside `run_campaign_conductor`'s board stage: split into `_scout_one(ai_idx, board_objs_round, board_slate_scores, scout_state)` (returns `(updated_scout_state, probes_spent)`) and `_pick_one(ai_idx, remaining_jobs, scout_state)` (returns chosen job name via `pick_job_from_board`). Preserve the `job_board` emit at round start (the #84 timing fix). Behavior remains sequential after the refactor.
- [ ] T011 [heist/orchestration.py] [US1] Replace the sequential per-team walk in the board stage with parallel scouts: (a) open all per-team round sub-games and emit `job_board` per team upfront (already in place per #84 — preserve), (b) spawn a `concurrent.futures.ThreadPoolExecutor(max_workers=len(active_teams))`, (c) submit one future per active team running `_scout_one`, (d) `concurrent.futures.wait(...)` for all futures, (e) for each future, on success record `probes_spent[i]`; on exception log via `log.warn(...)` and set `probes_spent[i] = 0`. Depends on T010.
- [ ] T012 [heist/orchestration.py] [US1] After all scouts: compute pick order as `pick_order([(i, probes_spent[i], camp.banked_loot) for i, camp in active_camps.items()])` (uses US2's new signature). Walk the order; for each team call `_pick_one(...)` against the diminishing slate, applying existing contention resolution. Depends on T010, T011, and T008 (US2).
- [ ] T013 [P: tests/test_orchestration.py] [US1] Add two tests covering parallel scout: (a) **timing** — monkey-patch `_scout_one` (or `_run_scout_turn`) to `time.sleep(0.5)` per call; run the conductor board-stage with 3 active teams; assert total elapsed ≤ 0.8s (versus serial 1.5s); (b) **error containment** — patch one team's scout to `raise RuntimeError("boom")`; assert other teams complete normally and the failing team is sorted to the front of `pick_order` (probes_spent = 0). Tests should use a stub conductor harness rather than spinning up a server.

**Checkpoint**: US1 complete (parallel scouting wired up, pick order honors probes). MVP done.

---

🎯 **STAGING REVIEW — Phase A (MVP)** *(after T013)*

Push the branch, refresh staging, restart 8001 (it's safe — no campaign mid-run after the last ship). Launch a Quick Test:

- [ ] **Board stage runs in parallel** — visible as a noticeable speedup vs prior sequential runs (~3× faster for 3 teams).
- [ ] **Probe budget = 10** — confirm in any team's `scout` `turn_start` prompt.
- [ ] **Least-probes-first picks first** — the team that spent the fewest probes is the first to receive `job_claimed`.

Stop and confirm with the user before Phase 6.

---

## Phase 6: User Story 4 — Board carryover with mix-aware replenish (Priority: P2)

**Goal**: Each round, carry forward `(BOARD_SIZE − N)` unpicked jobs; draw `N` new jobs with a weighted bias toward filling carryover's category-emphasis and reward-tier gaps; persist rolled hidden scores per carried job.

**Independent Test**: Stub 2-round campaign — round 2's board includes 5 carryover names from round 1 with rolled scores intact; new draws shift category/reward distribution toward balance.

### Implementation for US4

- [ ] T014 [heist/board.py] [US4] Add helper `replenish_mix_aware(pool: list[Job], carryover_jobs: list[Job], n: int, rng) -> list[Job]`: compute dominant-category distribution + reward-tier (3-bin) distribution from `carryover_jobs`; per candidate weight `w(j) = 1 + 1/(1 + count_of_j_dominant) + 1/(1 + count_of_j_tier)`; weighted-sample without replacement `n` jobs. The `pool` is whatever `build_board` would normally consider after gating. Documented in research.md § "Mix-aware replenish heuristic."
- [ ] T015 [heist/orchestration.py] [US4] In the board stage, before the parallel scout: compose the round's board as `carryover + replenish_mix_aware(...)` using `Campaign.carryover_board` (T003). Reuse `Campaign.persistent_slate_scores` for carried jobs; roll fresh hidden scores for new draws and store them in `persistent_slate_scores`. Pass the merged `slate_scores` to `_scout_one`. After picks settle: set `Campaign.carryover_board = [j for j in round_board if j not in picks_this_round]` and drop picked jobs from `persistent_slate_scores`. Update `Campaign.consumed_jobs` with picked jobs (existing behavior).
- [ ] T016 [P: tests/test_board.py] [US4] Test `replenish_mix_aware`: with a seeded RNG and a synthetic carryover of 5 all-confrontation-dominant + low-reward jobs, assert the 3 new draws collectively contain ≥1 non-confrontation-dominant and ≥1 higher reward-tier. Also test pool-exhaustion: when fewer than `n` candidates remain, return what's available (board may end up < BOARD_SIZE).
- [ ] T017 [P: tests/test_campaign.py] [US4] End-to-end: build a stub 2-round / 3-team campaign with stub AIs; capture round 1's board, run picks, then check round 2: assert (a) exactly 5 round-1 board names appear in round 2's board, (b) `Campaign.persistent_slate_scores` contains entries for all 5 carryover jobs and their values equal round 1's rolled scores, (c) 3 new jobs are present.
- [ ] T018 [heist/prompts.py] [US4] Update `_TRADECRAFT`: add a bullet noting that unpicked jobs may persist on the next round's board (so scouting an unpicked job is not necessarily wasted).

**Checkpoint**: US4 complete (board carries 8−N, mix-aware replenish, persistent rolled scores).

---

🎯 **STAGING REVIEW — Phase B** *(after T018)*

Push the branch, refresh staging, restart 8001. Launch a Quick Test:

- [ ] **Round 2's board carries ~5 jobs from round 1.**
- [ ] **3 new jobs visibly diversify the mix** (not three more of whatever dominated round 1).
- [ ] **Carryover jobs preserve their hidden scores** (no inconsistency in any prior reveals you scouted in round 1).

Stop and confirm with the user before Phase 7.

---

## Phase 7: User Story 5 — Persistent scout intel across rounds (Priority: P2)

**Goal**: Each team's `reveals` and `exact_scores` persist on `Campaign.per_ai_scout_state` across rounds. Per-round counters reset; intel does not.

**Independent Test**: 2-round stub campaign. In round 1 scout a job that goes unpicked. In round 2 assert that team's reveals on the carryover job are present in both the scout-turn prompt and the Job tab's slate.

### Implementation for US5

- [ ] T019 [heist/orchestration.py] [US5] In the board stage, replace per-round `ScoutState` instantiation: for each active team, take `Campaign.per_ai_scout_state.get(ai_idx)` if present, else create a fresh ScoutState and store it. At round start (before parallel scout fan-out), reset only `probes_spent_free = 0` and set `free_probes = free_probe_budget()` on each. Pass the persisted ScoutState into `_scout_one`; mutations flow back via the same object. Depends on T011 (US1).
- [ ] T020 [heist/orchestration.py] [US5] Right after `job_board` (per team) and before scouts spawn, emit a new `scout_state_loaded` event per team carrying `{ai_idx, reveals: ..., exact_scores: ...}` (serialize via `scout_state_to_dict` minus the round-counter fields, or just the two dicts directly). This is the engine→UI carrier for persisted reveals (research.md § Question 3). Backward-compat: never emitted by old code, so old replays are unaffected.
- [ ] T021 [P: heist/web/tabs/job.html] [US5] Add a `handleEvent` branch for `e.type === 'scout_state_loaded'`: merge `e.reveals` into `revealByAI[aiIdx]` and `e.exact_scores` into `scoutedByAI[aiIdx]`, then `render()` if `aiIdx === Shell.currentAI`. The existing slate renderer (which already paints based on these maps) handles display without further changes.
- [ ] T022 [P: tests/test_scouting.py] [US5] Test the persistence semantics: build a Campaign, call the board-stage entry with stubbed AI agents, run round 1 (team A scouts Job X to BUCKET); call again for round 2; assert `Campaign.per_ai_scout_state[A].reveals['X']` is intact at round 2 start and that `probes_spent_free` was reset to 0 between rounds.
- [ ] T023 [P: tests/test_campaign.py] [US5] End-to-end: stub 2-round campaign, force team A to scout Job X in round 1 (Job X must not be picked — choose a low-reward filler so stubs avoid it). In round 2 assert (a) Job X is in `carryover_board`, (b) team A's scout-turn prompt for round 2 shows the BUCKET reveal text for Job X's scouted cell, (c) the Job tab's slate for team A renders that cell as `(estimate)`, not `???`.
- [ ] T024 [heist/prompts.py] [US5] Update `_TRADECRAFT`: add a bullet noting that scouting persists across rounds — your reveals on a carried-over job carry forward, and a second probe on a cell scouted last round still advances it to EXACT.

**Checkpoint**: US5 complete (persistent intel via Campaign.per_ai_scout_state + scout_state_loaded event).

---

🎯 **STAGING REVIEW — Phase C** *(after T024)*

Push the branch, refresh staging, restart 8001. Launch a Quick Test:

- [ ] **Round 2's Job tab shows prior reveals on carried-over cards** — cells you scouted in round 1 still show `(estimate)` or `🔍 N/10` in round 2.
- [ ] **A team's scout-turn prompt in round 2 lists their persisted reveals** instead of `???` for previously scouted cells.
- [ ] **Compounding is visible**: a team that scouted across multiple rounds picks a job it actually scouted (validates SC-007).

Stop and confirm with the user before shipping.

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Final consistency pass + verification.

- [ ] T025 [heist/prompts.py] Read-through `_TRADECRAFT` end-to-end and confirm all four new rule additions land together coherently (probe budget, least-probes-first pick order with bankroll tiebreak, board carryover, persistent scouting intel). Tighten wording if any bullet feels redundant.
- [ ] T026 Run the manual playtest from quickstart.md end-to-end on staging (full Quick Test). Walk through every Success Criterion (SC-001 through SC-007) and check ✓/✗ in spec.md if any need adjustment based on observed behavior.
- [ ] T027 Final preflight + isolated server smoke test from the worktree: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q && python3 -c "import agents, demo, heist, heist.runner, heist.scenes, heist.mechanics, heist.server, heist.persist"` then the standard smoke test (boot server with `HEIST_STATE_DIR=$(mktemp -d) HEIST_TURN_DELAY=0` on a throwaway port, run a stub game to `status=done`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundation (Phase 2)**: Depends on Setup. Blocks Phase 6 (US4) and Phase 7 (US5). Does **not** block Phase 3–5 (P1 stories).
- **US3 (Phase 3)**: Depends on Setup.
- **US2 (Phase 4)**: Depends on Setup. Independent of US3.
- **US1 (Phase 5)**: Depends on US2 (T008 — pick_order signature). Independent of US3 in terms of code, but US3 should land first so the new budget is in effect when US1 wires up the conductor.
- **US4 (Phase 6)**: Depends on Foundation + US1 (uses the parallel-scout flow as a base for the carryover wiring). Sequential after MVP staging review.
- **US5 (Phase 7)**: Depends on Foundation + US4 (carryover provides the jobs whose intel persists). Sequential after Phase B staging review.
- **Polish (Phase 8)**: After all user stories.

### User Story Dependencies (within MVP)

- **US3** can be done in parallel with **US2** (different files, no shared logic). US1 needs them both first.
- **US1** must come last in the MVP — it integrates the new `pick_order` signature from US2 and the new probe budget from US3.

### Parallel Opportunities

Within phases, `[P: file]` markers identify tasks that can run together:

- Phase 3: T006 ↔ T007 (mechanics.py vs tests/test_scouting.py).
- Phase 4: T008 ↔ T009 (board.py vs tests/test_board.py).
- Phase 5: T013 can run alongside T010–T012 as soon as the structure of `_scout_one` is set (different file: tests/test_orchestration.py).
- Phase 6: T016 ↔ T017 (tests/test_board.py vs tests/test_campaign.py).
- Phase 7: T021 ↔ T022 ↔ T023 (job.html vs test_scouting.py vs test_campaign.py).

Across phases: **none** — staging reviews are explicit human gates between Phase A (MVP) → Phase B (US4) → Phase C (US5).

---

## Task Statistics

- **Total tasks**: 27
- **Phases**: 8 (Setup, Foundation, US3, US2, US1, US4, US5, Polish)
- **MVP scope (P1)**: US3 + US2 + US1 = T006–T013 (8 tasks)
- **P2 scope**: US4 + US5 = T014–T024 (11 tasks)
- **Parallel-marked tasks**: 9 (T002, T007, T009, T013, T016, T017, T021, T022, T023)
- **User-visible mechanic changes** (prompts.py updates): T018 (US4), T024 (US5), and implicitly the US3 rule update will land alongside T006 or be batched into T025. (No P1 _TRADECRAFT update task is currently listed — add to T025 if not done by T012.)
- **Staging review gates**: 3 (after T013 — MVP; after T018 — Phase B; after T024 — Phase C)
