# Tasks: Persistent Scouting in Campaigns

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/scout-persistence.md

## Format: `[ID] [P: file]? [Story]? Description`

- **[P: repo/relative/file.ext]**: can run in parallel (file scope listed). Bare `[P]` = serial.
- **[Story]**: US1 / US2 / US3
- Paths are repo-relative within the `feat/scout-persistence` worktree.

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before touching engine code.

- [X] T001 Confirm baseline preflight is green on `feat/scout-persistence` before changes: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`

---

## Phase 2: Foundation (Blocking Prerequisites)

**Purpose**: Extend the campaign state model + serialization. ALL user stories depend on this.

⚠️ **CRITICAL**: No user story work begins until this phase is complete.

- [X] T002 [P: heist/state.py] Add two fields to the `Campaign` dataclass in `heist/state.py`: `slate_scores: dict[str, dict[str, int]] = field(default_factory=dict)` (campaign-global locked scores) and `scout_state: ScoutState = field(default_factory=ScoutState)` (persistent per-team reveals). Import `ScoutState` if not already in scope.
- [X] T003 [heist/serialize.py] Extend `campaign_to_dict` and `campaign_from_dict` in `heist/serialize.py` to (de)serialize `slate_scores` and `scout_state`, reusing `scout_state_to_dict`/`scout_state_from_dict`; use `.get(..., default)` so legacy records (no keys) load as empty. (Depends on T002 — references the new fields.)

**Checkpoint**: `Campaign` carries and round-trips `slate_scores` + `scout_state`.

---

## Phase 3: User Story 1 - Locked scores per campaign (Priority: P1) 🎯 MVP

**Goal**: A job's hidden scores are rolled once and identical in every round.

**Independent Test**: 2-round stub campaign — a job's `challenge_scores` match between round 0 and round 1.

- [X] T004 [US1] In `heist/runner.py` `run_one_job`: replace the per-round `slate_scores = roll_slate_scores(available_jobs, rng)` with: use `campaign.slate_scores` when non-empty; otherwise roll once via `roll_slate_scores` and store the result on `campaign.slate_scores`. The round uses these locked scores for the picked job (`challenge_scores=dict(slate_scores.get(job.name, {}))`).
- [X] T005 [US1] In `heist/orchestration.py` `run_campaign_conductor`: roll the locked slate scores **once** at campaign start (when team Campaigns are created in `run_initial_auction`, or just before the round loop), store the dict on the campaign game record (`game["slate_scores"]`), and inject the **same** dict into every team's `Campaign.slate_scores`. (Depends on T002, T004.)
- [X] T006 [US1] In `heist/campaign.py` `run_campaign` (CLI loop): confirm the single `Campaign` carries `slate_scores` across the round loop via T004's roll-once-store; add an explicit one-time roll only if the loop bypasses it. (Depends on T004.)
- [X] T007 [P: tests/test_scout_persistence.py] [US1] Tests: a job's challenge scores are identical across ≥2 rounds (SC-001); a scouted value equals the locked value; all teams in a conductor campaign see identical locked scores.

**Checkpoint**: Scores no longer re-roll round-to-round.

---

## Phase 4: User Story 2 - Scouting stays scouted (Priority: P1) 🎯 MVP

**Goal**: A team's scouted cells carry forward across rounds and the replay shows the cumulative set.

**Independent Test**: scout a cell in round 0; in round 1 it is known with no new probe and its badge shows in the replay; a second team that didn't scout it does not know it.

- [ ] T008 [US2] In `heist/runner.py` `run_one_job`: build the round's working `ScoutState` pre-loaded from `campaign.scout_state` (`reveals` + `exact_scores`) but with a **fresh** `free_probes = free_probe_budget(crew.members)`; after the scout turn, merge newly revealed cells back into `campaign.scout_state`. (Same file as T004 — serial after it.)
- [ ] T009 [US2] In `heist/runner.py` `run_one_job`: at round start, after pre-loading and before the scout turn, emit one `scouted` event per already-known cell (job, category, score, bucket) so the replay renders cumulative intel (FR-007). (Same file as T008 — serial.)
- [ ] T010 [US2] In `heist/prompts.py`: verify `_scout_prompt`/`_job_prompt` show already-known cells (they read `scout_state`; pre-loading in T008 should suffice). Adjust only if known cells aren't surfaced so the AI doesn't re-scout.
- [ ] T011 [P: tests/test_scout_persistence.py] [US2] Tests: a cell scouted in round 0 is known in round 1 with zero probes spent (SC-002, SC-004); re-issuing a probe for a known cell is a no-op; per-team isolation (SC-005); carried-forward `scouted` events are emitted at round start.

**Checkpoint (MVP)**: 🚩 **Staging review** — restart the 8001 server, run a multi-round stub campaign, confirm a team's scouted badges accumulate across rounds and scores are stable. Get the user's eyes on it before US3.

---

## Phase 5: User Story 3 - Resume keeps locked scores + memory (Priority: P2)

**Goal**: A resumed campaign restores locked scores and every team's scouting memory exactly.

**Independent Test**: run round 0 with scouting, stall, resume — round 1 sees identical locked scores and the round-0 reveals intact.

- [ ] T012 [US3] In `heist/orchestration.py` resume reconstruction: re-inject `game["slate_scores"]` into each rebuilt team `Campaign.slate_scores`; if the record lacks `slate_scores` (legacy campaign), roll once and persist (FR-010). (Depends on T005.)
- [ ] T013 [US3] Confirm per-team `scout_state` restores via `campaign_from_dict` on resume (automatic from T003); add an assertion/guard that reveals survive a `campaign_to_dict → campaign_from_dict` round trip.
- [ ] T014 [P: tests/test_scout_persistence.py] [US3] Tests: resume preserves locked scores (not re-rolled) and 100% of reveals (SC-003); a legacy record with no `slate_scores` initializes once and continues; no probe/loot double-count on a resumed round.

**Checkpoint**: Resume is score- and scout-safe.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T015 Run full preflight and fix all: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`.
- [ ] T016 🚩 **Staging review** — on the restarted 8001 server, verify via the replay that cumulative scouting shows across rounds AND that hidden-depth/hidden challenges are NOT revealed by scouting (FR-013).
- [ ] T017 [P: specs/002-persistent-scouting/quickstart.md] Update quickstart notes if observed behavior differs. Do NOT edit CLAUDE.md, AGENTS.md, or MEMORY.md.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: none.
- **Foundation (Phase 2)**: T003 depends on T002. Blocks all user stories.
- **US1 (Phase 3)**: depends on Foundation. T005 depends on T004; T006 depends on T004.
- **US2 (Phase 4)**: depends on Foundation + US1 (locked scores must exist for persisted reveals to stay valid). T008→T009 serial (same file); T010 after T008.
- **US3 (Phase 5)**: depends on US1 (T012 needs T005's record-level scores).
- **Polish (Phase 6)**: after the slices you intend to ship.

### Parallel Opportunities
- T002 and T007/T011/T014 (test files) are on different files from the engine edits — tests can be authored alongside but assert against completed behavior.
- Most engine edits touch `heist/runner.py` (T004, T008, T009) → serial.

### MVP scope
- **MVP = Phase 3 (US1) + Phase 4 (US2)** — locked scores + persistent reveals + re-emission. Ship + staging review here.
- **Then Phase 5 (US3)** — resume/back-compat hardening.
