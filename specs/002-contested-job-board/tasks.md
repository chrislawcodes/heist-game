# Tasks: Contested Job Board

**Prerequisites:** plan.md, plan-summary.md, spec.md, spec-acceptance.md, data-model.md, contracts/board-events.md

## Format: `[ID] [P: file]? [Story]? Description`

- **[P: repo/relative/file.ext]** — may run in parallel; the file list is the task's scope. Bare `[P]` = serial.
- **[US1…US7]** — user-story label (user-story phases only).
- **Conflict-prone serial files — never parallelize tasks touching the same one:** `heist/runner.py`, `heist/prompts.py`, `heist/serialize.py`, `heist/persist.py`, `heist/server.py`, `heist/web/shell.js`, `heist/orchestration.py`, `heist/locations/__init__.py`, `heist/state.py`.
- **Build order de-risks the conductor:** pure board module + single-AI path + reward (green on CLI) FIRST, then the conductor contention stage.
- **Verification gate at every checkpoint:** `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`.

---

## Phase 1: Setup

- [ ] T001 Confirm green baseline on `feat/phase4-scoring-scouting`: run the preflight gate; record any pre-existing issues so they aren't blamed on this work.

---

## Phase 2: Foundation (Blocking Prerequisites)

⚠️ **CRITICAL**: the pure board core + state fields block every user story.

- [x] T002 [P: heist/state.py] Add `Campaign.consumed_jobs: set[str] = field(default_factory=set)`; add `BoardRound` dataclass (`round_idx:int, board:list[str], pick_order:list[int], claims:dict[int,str], contested:list[dict]`); add `RoundResult.board: list[str] = []` and `RoundResult.contested: bool = False` (data-model.md).
- [x] T003 [P: heist/board.py] Create the pure board module: `tier_rank(job)->int` (Hard-count + tier), `affordable(job, bankroll)->bool` (reward-proxy heuristic), `pick_order(standings)->list[int]` (ascending banked, tiebreak ai_idx), and `build_board(pool, consumed, round_idx, rounds_total, total_banked, *, size=8, min_affordable=2, trailing_bankroll=0, rng)->list[str]` — gated slots + wild slots + affordable guard; returns ≤size job names from `pool − consumed`; if fewer remain, returns all. Deterministic given `rng`. (No gating tuning yet — a simple rank ceiling is fine; US4 refines.)
- [x] T004 [P: tests/test_board.py] Unit tests: `build_board` never returns a consumed job; returns ≤8 and all-remaining when pool runs low; deterministic for a fixed seed; `pick_order` orders trailing-first with ai_idx tiebreak; `affordable`/`tier_rank` boundaries. (Depends on T003.)

**Checkpoint:** `pytest -q tests/test_board.py` green; mypy/ruff clean. Board core + state ready.

---

## Phase 3: User Story 2 — Reward climbs with difficulty (Priority: P1) 🎯 MVP

**Goal:** take scales with difficulty; floor ≥ $1M; elite 4-Hard jobs are the $15–18M jackpots; 1–2 edges. (Independent of board plumbing — content + a shape test.)

**Independent Test:** band-median take ascends by Hard-count; min take ≥ $1M; the two 4-Hard jobs are the top two; every job still pays into an active challenge.

- [x] T005 [P: heist/locations/__init__.py] Retune every existing job's `scene_loot` (real take) and `reward_range` per Decision 6: floor ≥ $1M; take trends up with Hard-count then tier; Billionaire's Compound & The Mint ≥ $15M (Mint highest); designate ≥1 bargain edge (Corporate Server Farm) and ≥1 trap edge (City Hall Records); `reward_range ≈ [0.55× take .. clean take + best hidden-depth bonus]`; scale `reward_amounts` so the range top is reachable; keep per-category `scene_loot` split.
- [x] T006 [P: tests/test_locations.py] Shape tests: pool min take ≥ $1,000,000; band-median take strictly ascending across Hard-counts {0,1,2,4}; the two 4-Hard jobs are the two highest takes; each `reward_range` top reachable from `scene_loot + max(reward_amounts)`; every job's `scene_loot` pays into an active (non-NONE) challenge. (Depends on T005.)
- [x] T007 [heist/content.py + tests] Update any existing tests that assert old reward numbers (test_content.py "every job can pay out", any take/auction figures that reference job rewards). (Serial — touches shared expectations; run after T005.)

**Checkpoint:** preflight green; reward shape verified.

---

## Phase 4: User Story 1 — Rotating board + global consumption, single-AI (Priority: P1) 🎯 MVP

**Goal:** the campaign shows a ≤8-job board each round from `pool − consumed`; attempted jobs are consumed and never reappear; the AI sees only the board. Green on the CLI stub.

**Independent Test:** `python -m heist run-campaign --agent stub` runs; each round's board ≤8 from unconsumed; a job attempted in round N is absent thereafter.

- [x] T008 [heist/runner.py] Make `run_one_job` job-agnostic: add params `assigned_job: Job | None = None` and `board: list[Job] | None = None`. When `assigned_job` is set, skip internal selection and run that job's scenes/scout. When `assigned_job is None`, self-select over `board` (default `list(JOBS)` if `board is None`) so the existing single-heist path/tests are unchanged. Scouting (`_run_scout_turn`) and `_pick_job` operate over the board, not `list(JOBS)`. (Conflict-prone — serial.)
- [x] T009 [heist/campaign.py] In single-AI `run_campaign`: each round build the board via `heist.board.build_board(JOBS, campaign.consumed_jobs, round_idx, rounds_total, campaign.banked_loot, rng=...)`, pass it to `run_one_job`, and after the round add the attempted job to `campaign.consumed_jobs`; record `RoundResult.board`. Derive a per-round seeded rng for determinism. (Serial — depends on T002, T003, T008.)
- [x] T010 [heist/prompts.py] `_job_prompt`, `_job_slate_summary`, and `_scout_prompt` take the round's board (list of jobs) instead of reaching for `list(JOBS)`; show only board jobs. (Conflict-prone — serial.)
- [x] T011 [tests/test_campaign_board.py] New: single-AI stub campaign over several rounds asserts each board ≤8 from unconsumed, no attempted-job repeats across the campaign (SC-002), and graceful behavior when unconsumed < 8. (Depends on T008–T010.)
- [x] T012 [tests/test_runner_stub.py + tests/test_campaign_3d.py] Update existing campaign/runner tests for the board signature and board-only slate (keep them green). (Serial.)

**Checkpoint:** `python -m heist run-campaign --agent stub` runs clean; preflight green. **MVP (single-AI) shippable.**

---

## Phase 5: User Story 3 — Teams contend for jobs (trailing-first) (Priority: P1) 🎯 MVP

**Goal:** the conductor builds one shared board per round, orders teams by ascending banked loot, walks them through pick/scout/claim, resolves contention (lower-banked wins; loser falls back via the existing system fallback), and consumes attempted jobs globally — before the parallel heist stage.

**Independent Test:** a 4-team conductor harness over 10 rounds: pick order ascending banked each round; same-job collisions resolved lower-banked-first; every attempted job consumed globally; no repeats (SC-001, SC-002, SC-004).

- [x] T013 [heist/orchestration.py] Add a **job-board stage** to `run_campaign_conductor`, sequenced before the parallel heist stage: build the shared board once (seeded by campaign+round), compute `pick_order` from per-AI banked standings, then for each ai_idx in order run its scout + job-pick over the *remaining* board, resolve the claim (reuse the incomplete-pick fallback if its choice was taken), record the claim, remove the job from the remaining board, and add it to the shared consumed set. Store a `BoardRound` on the campaign-level record. (Conflict-prone — serial; highest-risk task.)
- [x] T014 [heist/orchestration.py] Mirror the shared consumed set into each per-AI `Campaign.consumed_jobs` and pass each team its claimed job into `run_one_job(assigned_job=...)` in the heist stage (under `gamestate.lock`). Handle the "board ran dry / no job for a team" edge (emit a skip, no crash). (Serial — same file as T013, after it.)
- [x] T015 [tests/test_contention.py] New conductor-level harness test with 4 stub AIs over 10 rounds: asserts pick order ascending banked (trailing first, ai_idx tiebreak), same-job collision → lower-banked claims it and the rival gets a fallback board job, global consumption (no attempted job reappears), and the campaign completes (SC-001). (Depends on T013, T014.)

**Checkpoint:** 4-team stub completes via the harness; pick order + contention + global consumption verified; preflight green. **Fought-over board functional.**

---

## Phase 6: User Story 4 — Progression gating + random wilds (Priority: P2)

**Goal:** board composition skews low-tier early, unlocks high tiers/jackpots late, reserves wild slots for surprises, and always includes ≥ the affordable minimum.

**Independent Test:** round 1 gated slots are low tier (no elite in gated slots); late rounds unlock elite; ≥2 affordable each round; same seed → identical board.

- [x] T016 [heist/board.py] Implement `unlocked_max_rank(round_idx, rounds_total, total_banked)` and wire it into `build_board`: gated slots draw only ≤ the rank ceiling; reserve `wild_slots` (e.g. 2) drawn from all unconsumed; enforce `min_affordable` against `trailing_bankroll`. Keep deterministic. (Serial — same file as T003; after Phase 4 so the simple version shipped first.)
- [x] T017 [tests/test_board.py] Extend: round-1 board excludes elite from gated slots; late/high-banked board admits elite; affordable-minimum always met; wild slot can surface an off-ceiling job; determinism for fixed seed. (Depends on T016.)

**Checkpoint:** gating + wilds verified; preflight green.

---

## Phase 7: User Story 5 — Expanded job pool (~50) (Priority: P2)

**Goal:** ~50 jobs so a 4-team/10-round campaign never runs dry; weighted easy/medium; all content invariants pass; reward per Decision 6.

**Independent Test:** pool ~50; all categories represented as gating challenges; all content tests pass; 4-team 10-round stub never exhausts the board.

- [x] T018 [heist/locations/__init__.py] Author ~35 new jobs (full content: name, flavor, profile, tier, `scene_loot`, `reward_range`, `reward_amounts`, `hidden_depth`), weighted to easy/medium, rewards on the Decision-6 curve, unique names, floor ≥ $1M. (Conflict-prone — serial; same file as T005, after it.)
- [x] T019 [P: heist/locations/locations_art.csv] Add an art row per new job matching the existing pipeline format.
- [x] T020 [tests/test_content.py + tests/test_locations.py] Update: assert pool size ~50, category coverage, all invariants + reward shape hold across the expanded pool; bump any hard-coded job-count assertions. (Serial — after T018.)

**Checkpoint:** ~50-job pool passes all invariants; 4-team 10-round stub stays full; preflight green.

---

## Phase 8: User Story 6 — Board & claims in the viewer + event/persist round-trip (Priority: P2)

**Goal:** emit board/claim events, persist board/claims/consumed for replay+resume, and render the board + who-claimed-what in the viewer — all two-lane (engine emits, UI renders).

**Independent Test:** replay shows each round's 8-job board and claims; consumed jobs gone; resume restores the in-flight board/pick-order/consumed; serialize round-trips.

- [ ] T021 [heist/serialize.py] Round-trip `Campaign.consumed_jobs`, `BoardRound`, and `RoundResult.board/contested` in `campaign_to_dict`/`campaign_from_dict` and round serialization; tolerant legacy load (missing → empty). (Conflict-prone — serial.)
- [ ] T022 [heist/persist.py] Persist `consumed_jobs` + per-round `BoardRound` in the campaign-level record and `board` in the per-AI round snapshot; bump `schema_version` tolerant load. (Conflict-prone — serial.)
- [ ] T023 [heist/orchestration.py + heist/server.py] Emit `job_board` and `job_claimed` events (contracts/board-events.md) from the board stage; ensure `server` broadcasts them on `/stream` and appends to the persisted events buffer (no new route). (Serial — orchestration.py after T013/T014; server.py conflict-prone.)
- [ ] T024 [P: heist/web/shell.js] Consume `job_board`/`job_claimed`; track per-round board + claims in the replay model (no client-side board reconstruction). (Conflict-prone — only this task touches shell.js this phase.)
- [ ] T025 [P: heist/web/tabs/job.html] Render the round's board (≤8) and the claiming team per job (and contested losses); reflect consumed jobs leaving the board.
- [ ] T026 [tests/test_serialize_board.py] New: campaign with consumed_jobs + BoardRound round-trips; a resume restores identical board/pick-order/consumed for the in-flight round (SC-005). (Depends on T021, T022.)

**Checkpoint:** events emitted + persisted + rendered; resume fidelity verified; preflight green.

---

## Phase 9: User Story 7 — Documentation truth-up (Priority: P3)

**Goal:** docs match shipped reality.

- [ ] T027 [P: heist_game_design.md] Correct core mechanics to the 1–10 score model (buckets 1-3/4-7/8-10, score-margin resolution, +1-point collaboration, scouting reveal ladder); mark Phase 4 built; document the contested board (shared, global-consumption, 8 shown, trailing-first, gating+wilds) and the reward-climb model ($1M floor, $15-18M jackpots, edges); update roster count to 21.
- [ ] T028 [P: CLAUDE.md] Update "Locked Design Decisions": skill scores (not buckets), 21-character roster, correct current phase, contested-board slate rule; update the job-slate line.

**Checkpoint:** docs consistent with shipped behavior.

---

## Phase 10: Polish & Cross-Cutting

- [ ] T029 Full preflight green: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`.
- [ ] T030 Run quickstart.md US1–US6 verifications (single-AI stub, 4-team harness, reward shape, gating, resume).
- [ ] T031 Commit, push, run `.claude/scripts/refresh-staging.sh`, then `/ship` as one PR.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)** → none.
- **Foundation (P2: T002–T004)** → after Setup; **BLOCKS all user stories** (board core + state).
- **US2 reward (P3)** → after Foundation; independent of board plumbing — can run parallel to US1.
- **US1 single-AI board (P4)** → after Foundation; the MVP slice.
- **US3 conductor contention (P5)** → after US1 (reuses `run_one_job(assigned_job)` + board); the highest-risk slice.
- **US4 gating (P6)** → after US1 (refines `build_board`); independent of US3.
- **US5 content (P7)** → after US2 (same file, reward curve); independent of mechanic.
- **US6 viewer+persist (P8)** → after US3 (renders board/claims events the conductor emits).
- **US7 docs (P9)** → after the mechanic stabilizes.
- **Polish (P10)** → last.

### Parallel Opportunities

- Foundation: T002 ∥ T003 (different files); T004 after T003.
- US2 (T005/T006) can run alongside US1 (T008–T010) — different files (locations vs runner/campaign/prompts).
- US7 docs: T027 ∥ T028 (different files).
- US6: T024 ∥ T025 (shell.js vs job.html); T021/T022/T023 serial (serialize/persist/orchestration/server).

### Conflict-prone files (never parallelize across these)

`heist/state.py` (T002), `heist/board.py` (T003, T016), `heist/runner.py` (T008), `heist/prompts.py` (T010), `heist/campaign.py` (T009), `heist/orchestration.py` (T013, T014, T023), `heist/serialize.py` (T021), `heist/persist.py` (T022), `heist/server.py` (T023), `heist/web/shell.js` (T024), `heist/locations/__init__.py` (T005, T018). Sequence tasks on each.
