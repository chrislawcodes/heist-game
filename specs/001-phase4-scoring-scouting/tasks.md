# Tasks: Phase 4 — Hidden Location Info & Scouting (Score-Based Resolution)

**Prerequisites:** plan.md, plan-summary.md, spec.md, spec-acceptance.md, data-model.md, contracts/phase4-contracts.md, research.md

## Format: `[ID] [P: file]? [Story]? Description`

- **[P: repo/relative/file.ext]** — may run in parallel; file list is the task's scope. Bare `[P]` = serial.
- **[US1/US2/US3/US4/US5]** — user story label (user-story phases only).
- Implementer note: per CLAUDE.md, medium/large coding is dispatched to **Codex from the worktree**; each task names exact files/functions (see plan-summary.md). **Conflict-prone files — never parallelize tasks touching the same one:** `heist/runner.py`, `heist/server.py`, `heist/web/shell.js`, `heist/prompts.py`, `heist/serialize.py`, `heist/persist.py`, `heist/locations/__init__.py`.

---

## Phase 1: Setup

- [ ] T001 Create worktree + branch: `git worktree add .claude/worktrees/phase4-scoring-scouting -b feat/phase4-scoring-scouting` (work happens in the worktree; main repo stays on `main` per CLAUDE.md).
- [ ] T002 Capture green baseline before changes: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`. Record any pre-existing failures so they aren't blamed on this work.

---

## Phase 2: Foundation (Blocking Prerequisites)

⚠️ **CRITICAL**: No user-story work begins until this phase is complete. These are the shared 1-10 primitives every story consumes.

- [ ] T003 [P: heist/state.py] Add `RevealLevel(IntEnum){HIDDEN,BUCKET,EXACT}`; add `ScoutState` dataclass (`reveals: dict[str,dict[str,RevealLevel]]`, `reward_reveal: dict[str,int]`, `free_probes:int`, `probes_spent_free:int`, `probes_paid:int`, with pure helpers `reveal/level/budget_remaining`); add `Scene.challenge_score: int | None = None`; add `HeistState.challenge_scores: dict[str,int]` + `scout_state: ScoutState` (see data-model.md).
- [ ] T004 [P: heist/mechanics.py] Add `score_to_bucket(score)->SkillLevel` (0→NONE,1-3→LOW,4-7→MED,8-10→HIGH); `effective_skill_score(members,skill)->int` (max score, **+1 if ≥2 members have the skill**, cap 10); `effective_skill_bucket(...)` = `score_to_bucket(effective_skill_score(...))`; `PREMIUM`/`SEAT` + `score_floor_cost(char)` (`100_000 + Σ premium(score)`) replacing `base_cost`/`expected_floor_cost`; `resolve_by_margin(eff_score,challenge_score)->Outcome` per the margin table (CLEAN ≥2 / SQUEAK 0..1 / FAIL −1..−3 / CAUGHT ≤−4 — research.md Q1); `roll_challenge_scores(profile,tier,rng)->dict[str,int]` per tier fog bands; `driver_scout_bonus(crew)` (+1/+2/+3 by best driver bucket, +0 none) + `free_probe_budget(crew)`. Keep `escape_resolves` body; it will be fed the derived driver bucket.
- [ ] T005 [tests/test_mechanics.py] Unit-test the foundation pure functions: `score_floor_cost` matches the spec table to the dollar; `effective_skill_score` gives `min(best+1,10)` for ≥2 members; `score_to_bucket` boundaries; `resolve_by_margin` table; `roll_challenge_scores` stays within tier bands. (Depends on T004.)

**Checkpoint:** state + mechanics compile, `mypy` clean, `pytest -q tests/test_mechanics.py` green. User stories can begin.

---

## Phase 3: User Story 1 — True-score resolution, pricing, collaboration (Priority: P1) 🎯 MVP

**Goal:** the engine runs end-to-end on 1-10 scores — pricing, collaboration (+1 point), score-vs-score resolution, escape via derived bucket — without breaking `run_heist`/`run_campaign`.

**Independent Test:** `python -m heist run --agent stub` and `run-campaign --agent stub` complete with no traceback; floor costs match the curve; resolution is `effective_score ≥ challenge_score`; graded outcomes + heat still emit.

- [ ] T006 [P: heist/characters/__init__.py] [US1] Populate `skill_scores` for all 16 characters (locked table in spec.md). Derive each character's public `skills` bucket from its scores via `score_to_bucket` (single source of truth — research.md Q5); keep names/personalities untouched.
- [ ] T007 [P: heist/resolution.py] [US1] In `_resolve_challenge_scene`, replace `effective_skill`+`resolve_outcome` with `effective_skill_score(assigned, scene.challenge_skill)` vs `scene.challenge_score`, graded by `resolve_by_margin`.
- [ ] T008 [P: heist/scenes.py] [US1] In `generate_scenes`, stamp `Scene.challenge_score` from the round's rolled `challenge_scores` (passed in). Scene **structure** (which scenes exist, `is_core`) still derives from the public bucket profile.
- [ ] T009 [heist/runner.py] [US1] After `_pick_job`, call `roll_challenge_scores(job.profile, job.tier, rng)` into `HeistState.challenge_scores` and pass to `generate_scenes`. Feed the escape `effective_skill_bucket(free_members,"driver")` so `escape_resolves` is unchanged. Switch `_draft_crew` / bid validation to `score_floor_cost`. (Conflict-prone — serial.)
- [ ] T010 [P: heist/prompts.py] [US1] In `_roster_summary` expose **public** character scores (e.g. "Safecracker 9") and floor costs from `score_floor_cost`. (Job-slate defense fog is deferred to US2; here the slate still shows buckets as today.)
- [ ] T011 [P: heist/serialize.py] [US1] `character_to_dict`: emit populated `skill_scores`. (Job/scene fog deferred to US2.)
- [ ] T012 [P: heist/persist.py] [US1] Add a `schema_version` tag to game records; tolerant legacy load (done games replay from stored events, no re-resolution; pre-Phase-4 in-flight games marked errored on resume — research.md Q3); include `challenge_scores` in the round snapshot.
- [ ] T013 [heist/auction.py + any residual callers] [US1] Sweep for remaining `expected_floor_cost`/`base_cost` references (auction bid validation, server, runner) and replace with `score_floor_cost`. (Serial — multi-file; run after T009/T010.)
- [ ] T014 [P: tests/test_resolution.py] [US1] Replace the bucket-vs-bucket table with a score-vs-score table covering each margin band.
- [ ] T015 [P: tests/test_scenes.py] [US1] Assert `Scene.challenge_score` is stamped for challenge scenes and `None` otherwise.
- [ ] T016 [tests/test_runner_stub.py] [US1] End-to-end: stub single heist + stub 3-round campaign run green on the new engine and emit the existing event types. (Serial — integration.)
- [ ] T017 [P: heist_game_design.md] [US1] Update bucket boundaries (1-3 Low / 4-7 Med / 8-10 High), collaboration = +1 point, score-based resolution supersedes the bucket model, and the scouting-applies-to-locations-only note.

**Checkpoint:** US1 fully functional — `pytest -q` green, both stub modes run, pricing exact. MVP shippable.

---

## Phase 4: User Story 2 — Scout a location (Priority: P2)

**Goal:** an in-thread, AI-driven scouting phase reveals fogged defenses bucket→exact; free probes = crew + driver bonus; overflow costs $100k.

**Independent Test:** stub campaign emits `scouted` events; budget arithmetic correct per driver tier; 1st probe = bucket, 2nd = exact; overflow charges $100k or refuses; serialize hides unscouted scores.

- [ ] T018 [P: heist/prompts.py] [US2] Add `_scout_prompt`: list the fogged slate + crew + `free_probe_budget` + the $100k overflow price; instruct the probes JSON (contracts/phase4-contracts.md §1). (prompts.py — serialize-fog edits in T022 are also prompts.py; run T018 before T022, no overlap with T010's phase.)
- [ ] T019 [heist/runner.py] [US2] Add a scouting decision turn (sibling to `_pick_job`) in `run_one_job`/`run_heist`: compute `free_probe_budget`, call the AI with `_scout_prompt`, validate probes, apply to `ScoutState` (bucket→exact, no-op/no-charge past EXACT), deduct $100k per over-budget probe (skip if unaffordable), emit `scouted` events. (Conflict-prone — serial.)
- [ ] T020 [heist/campaign.py] [US2] Initialize a fresh `ScoutState` per round with `free_probes = free_probe_budget(standing_crew)`; wire the scouting turn before job commitment in the round loop.
- [ ] T021 [P: heist/serialize.py] [US2] Gate `job_to_dict` + `scene_to_dict` on `ScoutState`: `profile[cat]` becomes `{reveal, bucket?, score?}` (contracts §3); add `scout_state_to_dict`; add the `scouted` event payload builder. Reward **range** stays public.
- [ ] T022 [heist/prompts.py] [US2] Update `_job_slate_summary` + `_scene_assign_prompt` to fog defenses via `ScoutState` (show unknown/bucket/exact per reveal level) so the AI never sees an unscouted exact. (Serial after T018 — same file.)
- [ ] T023 [P: heist/stub_responses.py] [US2] Add a scouting-decision response (dispatch on the `_scout_prompt` marker) returning a small probes list so the stub campaign exercises scouting.
- [ ] T024 [heist/persist.py] [US2] Serialize `ScoutState` into the round snapshot so a mid-round resume keeps intel. (Serial — same file as T012.)
- [ ] T025 [P: tests/test_scouting.py] [US2] New tests: free-probe budget per driver tier; bucket→exact order; $100k overflow + unaffordable-refusal; serialize fog hides unscouted score; reward range public.
- [ ] T026 [heist/server.py] [US2] Ensure `scouted` events are broadcast on `/stream` and appended to the persisted `events` buffer (no new route). (Conflict-prone — serial.)

**Checkpoint:** US2 functional — scouting budget/reveals correct, fog enforced in both prompts and serialize, `pytest -q tests/test_scouting.py` green.

---

## Phase 5: User Story 3 — Fog in the viewer (Priority: P2)

**Goal:** the viewer shows public flavor/reward-range, fogged defenses, public character scores, and incremental reveals from `scouted` events.

**Independent Test:** in a campaign replay, a slate location reads fogged pre-scout, updates to bucket then exact across `scouted` events; no unscouted exact ever appears.

- [ ] T027 [P: heist/web/shell.js] [US3] Add helpers to render public character scores and the three defense states (hidden / bucket / exact); extend `helpers.skillVal`/diff helpers. (Conflict-prone — only this task touches shell.js in this phase.)
- [ ] T028 [P: heist/web/tabs/job.html] [US3] Consume `profile[cat].reveal`; render fog vs bucket vs score; always show the reward range; handle `scouted` events incrementally.
- [ ] T029 [P: heist/web/tabs/hiring.html] [US3] Show public character scores on crew cards; add a scout panel reflecting `scouted` events / `ScoutState`.
- [ ] T030 [US3] Browser verification via preview: pre-scout fog, post-scout bucket→exact reveal, reward range visible, no unscouted exact shown. (Manual/preview — serial, last in phase.)

**Checkpoint:** US3 — fog and reveals are visible and correct in replay.

---

## Phase 6: User Story 4 — Tiered ladder + edge jobs (Priority: P3)

**Goal:** jobs span a 0/1/2-3-High ladder; reward is correlated-with-slack so mispriced "edge" jobs exist.

**Independent Test:** Tier-1 Hard rolls 8; Tier-3 gating Hards roll {9,10}; each skill gates a fair share across 15 jobs; ≥1 edge job.

- [ ] T031 [heist/locations/__init__.py] [US4] Normalize every job's `tier` to `"1"/"2"/"3"` (currently strings like "easy"); verify each of the 5 challenge categories gates a fair share across the 15 jobs; align profiles so tier fog bands apply cleanly. (Conflict-prone — serial.)
- [ ] T032 [heist/locations/__init__.py] [US4] Implement correlation-with-slack reward generation (research.md Q4): per-cleared-challenge baseline `Reward(C)=round(2930×2^C)` summed, times a per-job slack factor; set `reward_range` to bracket the slack-perturbed prize, exact amount scoutable. (Serial — same file as T031.)
- [ ] T033 [P: tests/test_locations.py] [US4] Assert tier fog bands (T1 Hard=8, T3 Hard∈{9,10}); assert ≥1 job presents a high reward range over below-trend defenses (an edge).

**Checkpoint:** US4 — ladder and edges verified.

---

## Phase 7: User Story 5 — Second Medium Hacker (Priority: P3)

**Goal:** electronic gets a collaboration fallback; roster grows to 17.

**Independent Test:** 17 characters; ≥2 Medium-band hackers; new char curve-correct cost + portrait; new(7)+Sasha(6) → effective 8.

- [ ] T034 [P: heist/characters/__init__.py] [US5] Add a 17th character: a Medium Hacker (Hacker score 6-7, optional Low rider) with full personality fields (backstory, voice, motivation, quirk, crew_dynamic, weakness, look, signature_line) and `skill_scores`; floor cost follows the curve automatically.
- [ ] T035 [P: heist/characters/c17_<name>.jpeg + heist/characters/portraits.csv] [US5] Add the portrait asset and its `portraits.csv` row (match the existing crop/format pipeline).
- [ ] T036 [P: tests/test_characters.py] [US5] Assert 17 characters; ≥2 Medium-band hackers; new char's `score_floor_cost` matches the curve; `effective_skill_score([new, sasha], "hacker") == 8`.

**Checkpoint:** US5 — electronic has a two-medium path; roster at 17.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T037 Full preflight green: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`.
- [ ] T038 Run quickstart.md US1-US5 manual verifications (stub heist, stub campaign, browser fog).
- [ ] T039 [P: heist_game_design.md] Final design-doc pass: tier ladder, reward correlation-with-slack, scouting reveal ladder — consistent with shipped behavior.
- [ ] T040 Commit, push branch, run `.claude/scripts/refresh-staging.sh`, review on http://127.0.0.1:8001/ (staging rule), then `/ship`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)** → no deps.
- **Foundation (P2)** → after Setup; **BLOCKS all user stories** (state + mechanics primitives).
- **US1 (P3, P1-priority)** → after Foundation. MVP.
- **US2 (P4)** → after Foundation; reads `ScoutState` (Foundation) + integrates with runner/campaign (touches files US1 also touches — runner.py, prompts.py, serialize.py, persist.py — so run US2 **after** US1 to avoid serial-file churn).
- **US3 (P5)** → after US2 (renders `scouted` events + fogged `job_to_dict` from US2).
- **US4 (P6)** → after Foundation; independent of US2/US3 (content/generation). Can run parallel to US2/US3 if staffed, but T031/T032 share `locations/__init__.py` (serial within).
- **US5 (P7)** → after Foundation; independent (content). Shares `characters/__init__.py` with T006 (US1) — run after US1's T006.
- **Polish (P8)** → after the user stories you intend to ship.

### Parallel Opportunities

- Foundation: T003 ∥ T004 (different files); T005 after T004.
- US1: T006 ∥ T007 ∥ T008 ∥ T010 ∥ T011 ∥ T012 ∥ T014 ∥ T015 ∥ T017 (all distinct files); T009, T013, T016 serial.
- US2: T018, T021, T023, T025 parallel (distinct files); T019, T020, T022, T024, T026 serial (runner/prompts/persist/server — conflict-prone or same-file).
- US3: T027 ∥ T028 ∥ T029 (distinct files); T030 last.
- US4: T033 ∥ while T031→T032 run serially on locations.
- US5: T034 ∥ T035 ∥ T036 (distinct files), all after US1's T006.

### Conflict-prone files (never parallelize across these)

`heist/runner.py` (T009, T019), `heist/prompts.py` (T010, T018, T022), `heist/serialize.py` (T011, T021), `heist/persist.py` (T012, T024), `heist/server.py` (T026), `heist/web/shell.js` (T027), `heist/locations/__init__.py` (T031, T032), `heist/characters/__init__.py` (T006, T034). Sequence tasks on each.
