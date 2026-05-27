# Tasks: Scouting v2 — Two-Stage Hidden-Bucket Reveal (persistent + redesigned cards)

**Prerequisites**: spec.md, plan.md, data-model.md, contracts/scout-persistence.md

## Format: `[ID] [P: file]? [Story]? Description`

---

## Phase 1-3 — Locked scores + state foundation (BUILT)

- [X] T001 Baseline preflight green
- [X] T002 `Campaign.slate_scores` + `Campaign.scout_state` fields (state.py)
- [X] T003 Serialize both in `campaign_to_dict`/`from_dict` (serialize.py)
- [X] T004 `run_one_job` reads campaign.slate_scores (roll once if empty)
- [X] T005 Conductor rolls locked scores once + shares across teams
- [X] T006 CLI `run_campaign` reuses one Campaign
- [X] T007 Tests: locked scores stable / copy-safe / scouted==locked

## Phase 3.5 — Carry-forward scaffolding (BUILT, revised in Phase 5)

- [X] T008 `run_one_job` pre-loads carried scout_state with fresh probe budget
- [X] T009 `_emit_carried_scout` re-emits known cells at round start
- [X] T010 Prompts read scout_state (pre-load surfaces known cells)
- [X] T011 Tests: reveals carry forward / per-team isolation

---

## Phase 4: User Story 2 — Two-stage hidden reveal (Priority: P1) 🎯 MVP

**Goal**: A probe advances a cell one level (HIDDEN→BUCKET→EXACT); buckets are no longer public.

- [X] T018 [US2] In `heist/scouting.py` `apply_probes`: change from "jump to EXACT" to **advance one level** per probe via `scout_state.reveal()`. On reaching BUCKET, set the level only and emit a `scouted` event with `reveal_level:"BUCKET"`, `bucket` (from `score_to_bucket(slate_scores[job][cat])`), and **no** `score`. On reaching EXACT, set `exact_scores` and emit with `reveal_level:"EXACT"`, `bucket`, and `score`. EXACT cell → no-op, no probe spent.
- [X] T019 [US2] In `heist/prompts.py` `_job_slate_summary`: render each cell by reveal level — HIDDEN → category name only (no difficulty), BUCKET → `category <Bucket>`, EXACT → `category <Bucket> (N/10)`. Update `_scout_prompt` wording ("first probe reveals the bucket, a second reveals the exact 1-10"); `_job_prompt` reasoning text as needed.
- [X] T020 [P: tests/test_scout_persistence.py] [US2] Tests: 1 probe → BUCKET (no exact); 2nd probe → EXACT; EXACT re-probe is no-op; revealed bucket == published bucket of the locked score; HIDDEN cell absent from the slate summary's difficulty.

**Checkpoint**: scouting is two-stage; buckets hidden until probed.

---

## Phase 5: User Story 3 — Persist at reveal level (Priority: P1) 🎯 MVP

**Goal**: carried knowledge composes with new probes; carried reveals re-emit at their level.

- [X] T021 [US3] In `heist/runner.py` `_emit_carried_scout`: emit each carried cell at its level — BUCKET cells emit `reveal_level:"BUCKET"` (bucket, no score), EXACT cells emit `reveal_level:"EXACT"` (bucket + score). Mark `carried:true`.
- [X] T022 [US3] In `heist/runner.py` `_merge_scout_reveals`: merge by **max** level (never downgrade a cell); keep exact_scores. Confirm pre-load carries levels so a carried-BUCKET cell can advance to EXACT this round.
- [X] T023 [P: tests/test_scout_persistence.py] [US3] Revise/add tests: BUCKET cell carries to next round at BUCKET (no probe); a probe then advances it to EXACT; per-team isolation holds; carried events re-emitted at correct level.

**Checkpoint**: two-stage knowledge accumulates across rounds.

---

## Phase 6: User Story 4 — Card redesign (Priority: P1) 🎯 MVP

**Goal**: cards show hidden/bucket/exact from reveal state, this-turn highlight, number right, no 🔍.

- [ ] T024 [US4] In `heist/web/tabs/job.html`: store per-cell reveal state from `scouted` events as `{ level, bucket, score, carried }` (extend `scoutedByAI`). In `renderSlate` and the picked-job `render`, draw each challenge row from that state — NOT `j.profile`: HIDDEN → empty bars + no number; BUCKET → bars filled to bucket + no number; EXACT → bars filled to bucket + exact number to the **right of the bars**. Remove the `🔍` badge.
- [ ] T025 [US4] In `heist/web/tabs/job.html`: add a subtle highlight class on rows whose reveal is **not** `carried` (revealed this round); style it (thin outline or low-opacity tint). Add/adjust CSS; remove the old magnifying-glass styling.
- [ ] T026 [US4] In `heist/web/shell.js` if needed: ensure `bucket`/`reveal_level` ride through to JobTab (they already flow via the event); no reconstruction in the browser.

**Checkpoint (MVP)**: 🚩 **Staging review** — restart 8001, run a multi-round stub campaign, confirm the three card states, the this-turn highlight, hidden-until-probed difficulty, and accumulation across rounds. Get the user's eyes on it before US5.

---

## Phase 7: User Story 5 — Resume preserves levels (Priority: P2)

- [ ] T027 [US5] Conductor resume: re-inject locked scores from the game record (roll once if legacy).
- [ ] T028 [P: tests/test_scout_persistence.py] [US5] Tests: resume preserves per-cell levels (BUCKET stays BUCKET, EXACT stays EXACT) + exact scores + locked scores; legacy back-compat; no double-count.

**Checkpoint**: resume is level-safe.

---

## Phase 8: Polish

- [ ] T029 Full preflight: ruff + mypy + pytest.
- [ ] T030 🚩 Staging: verify cards + that hidden-depth is NOT revealed (FR-011) and reward stays public.

---

## Notes

- MVP = Phase 4 (US2) + Phase 5 (US3) + Phase 6 (US4): the two-stage model, persistence at level, and the card redesign. Ship + staging review there; US5 (resume) follows.
- The old "scout jumps to EXACT, buckets public" behavior is replaced by the two-stage model. Existing carry tests get revised for level semantics.
