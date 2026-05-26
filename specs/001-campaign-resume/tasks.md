# Tasks: Campaign Resume

**Prerequisites**: plan.md, spec.md, plan-summary.md, data-model.md, contracts/resume-api.yaml

## Format: `[ID] [P: file]? [Story]? Description`

- **[P: file]**: parallelizable — file scope listed; disjoint file sets may run together.
- **[Story]**: US1 / US2 / US3 (user-story phases only).
- Paths are repo-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Get the branch current and ready to implement.

- [X] T001 Rebase `feat/campaign-resume` onto `origin/main` (worktree is off `8dea0d3`; main has #69) so implementation lands on current code; re-run preflight after.

---

## Phase 2: Foundation (Blocking Prerequisites)

**Purpose**: The resume engine + supporting state. BOTH user stories US1 (auto) and US2 (manual) call into this, so it must land first.

⚠️ **CRITICAL**: No user story work begins until this phase is complete.

- [ ] T002 [P: heist/gamestate.py] Add `runtime.active_campaigns: set[int]` to `_Runtime` in heist/gamestate.py (double-conductor guard registry; init empty).
- [ ] T003 [P: tests/test_campaign_resume.py] Add a `campaign_from_dict` round-trip test: build a `Campaign`, snapshot it the way `snapshot_all` does (`campaign_to_dict` + extras), and confirm `campaign_from_dict` reconstructs `standing_crew` / `banked_loot` / `round_results` ignoring extra keys (`ai_idx`, `round_game_ids`, …). If it does NOT round-trip, fix `heist/serialize.py:campaign_from_dict` to read only campaign fields.
- [ ] T004 [heist/orchestration.py] In `run_campaign_conductor`, stamp `game["checkpoint_version"] = 1` inside `snapshot_all()` (so resumable campaigns are marked) and add the `resume: bool = False` parameter to the signature.
- [ ] T005 [heist/orchestration.py] Resume reconstruction in `run_campaign_conductor` (when `resume=True`): rebuild `campaigns[i]` from `game_states[i]` via `campaign_from_dict`; restore `round_gids_per_ai`, `hiring_gids`, `current_round_sub_gids` from persisted `round_game_ids`/`hiring_game_ids`; read `start_round=current_round_idx`, `start_stage=current_stage`. (depends on T004)
- [ ] T005b [heist/orchestration.py + heist/campaign.py] Heist-take checkpoint (plan Decision 3 / chosen Option B): after the heist stage (post-join) write each team's `pending_heist = {final_take, heat, caught_member_ids, job_name, aborted, escape_success}` into `game_states[i]`; clear it (null) once `settle_round` consumes it in reflection. Refactor `settle_round` to accept those fields (or a lightweight result object) so resume settles without a full `HeistState`. (depends on T005)
- [ ] T006 [heist/orchestration.py] Round/stage skip logic in the conductor loop: skip rounds `< start_round`; for `start_round`, resume at `start_stage`'s boundary per plan Decision 2 (opening_wire→…, hiring→…, heist→skip hire+redo heist+reflection, reflection→redo settle only); rounds `> start_round` run normally. Reconcile `settle_round`-once via `len(camp.round_results)` vs `start_round`. (depends on T005)
- [ ] T007 [heist/orchestration.py] Wrap the conductor body so it adds `campaign_id` to `runtime.active_campaigns` on entry and removes it in a `finally`. (depends on T002)
- [ ] T008 [P: tests/test_campaign_resume.py] Foundation tests: (a) stage-skip idempotency — a campaign reconstructed at `start_stage="heist"` does NOT re-run hiring (banked_loot unchanged) and does NOT double-append a `RoundResult`; (b) `settle_round` runs exactly once when the crash landed between settle and round-advance. (depends on T006)

**Checkpoint**: The conductor can resume a reconstructed campaign at a stage boundary without re-running completed stages.

---

## Phase 3: User Story 1 — A campaign survives a server restart (Priority: P1) 🎯 MVP

**Goal**: Interrupted campaigns auto-resume on startup; pre-existing stalls become `interrupted`.

**Independent Test**: Launch a campaign, complete round 1, restart the server, confirm it resumes and finishes with round-1 results intact (no restart from round 0); a campaign without `checkpoint_version` becomes `interrupted`.

- [ ] T009 [US1] [heist/orchestration.py] Add an `is_campaign` branch to `recover_games()`: for `status=="running"` campaign records — if `checkpoint_version >= 1`, spawn `run_campaign_conductor(gid, num_rounds, resume=True)`; else set `status="interrupted"` and persist. Ensure these records no longer fall into the single-game `ais`/auction path. (depends on T006)
- [ ] T010 [US1] [tests/test_campaign_resume.py] Test `recover_games` campaign branch: a running campaign WITH `checkpoint_version` is scheduled for resume (assert a conductor is spawned / state primed); a running campaign WITHOUT it is flipped to `interrupted`; a `done` campaign is untouched. (depends on T009)

**Checkpoint**: US1 fully functional — restart mid-campaign and it continues; old stalls go terminal.

---

## Phase 4: User Story 2 — Manually revive a stalled campaign (Priority: P2)

**Goal**: Resume a stalled campaign without a full server restart; guard against a second conductor.

**Independent Test**: POST `/api/campaign/<id>/resume` on a stalled campaign → it continues; on a live one → 409; other games unaffected.

- [ ] T011 [US2] [heist/server.py] Add route `POST /api/campaign/<id>/resume` → `_handle_resume_campaign`: 404 if no such game; 422 if not a campaign / already done|interrupted / missing `checkpoint_version`; 409 if `id` in `runtime.active_campaigns`; else spawn `run_campaign_conductor(id, num_rounds, resume=True)` and return `{ok, campaign_id, resumed_from:{round_idx,stage}}` per contracts/resume-api.yaml. (depends on T007, T009)
- [ ] T012 [US2] [heist/lobby.html] Add a "Resume" affordance on a stalled / `interrupted`-but-resumable campaign row that POSTs the new endpoint; surface failures (409/422) to the user. (depends on T011)
- [ ] T013 [US2] [tests/test_campaign_resume.py] Test the resume guard logic: refuses (409-equivalent) when the campaign id is in `active_campaigns`; proceeds when not; 422 path for a non-resumable campaign. (depends on T011)

**Checkpoint**: US2 functional — manual resume works and is guarded.

---

## Phase 5: User Story 3 — Resume is visibly correct (Priority: P3)

**Goal**: Resume re-emits normal events; no duplicated rounds/sub-games; `interrupted` shows in the UI.

**Independent Test**: War-room standings before/after a resume are unchanged for completed rounds; final round/sub-game counts have no duplicates.

- [ ] T014 [US3] [heist/orchestration.py] Confirm/ensure the resume path re-emits the normal campaign events (`campaign_stage`, per-AI heist events, `campaign_round_done`, `campaign_done`) via the existing `set_stage`/`emit_*` so the war room continues without UI-side reconstruction (two-lanes). No new event types. (depends on T006)
- [ ] T015 [US3] [tests/test_campaign_resume.py] Test no-duplication: a resumed campaign run to completion has exactly `num_rounds` `round_results` per team and no duplicate `round_game_ids`/`hiring_game_ids`. (depends on T006)
- [ ] T016 [P: heist/lobby.html] [US3] Display the `interrupted` status in the lobby campaign list (distinct from running/done). (depends on T009)

**Checkpoint**: US3 functional — resume is correct and visible.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T017 Run preflight: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q` — fix any failures at the root cause (no suppressions).
- [ ] T018 Manual verification from quickstart.md against an isolated-state staging-style server (US1 restart, US2 manual resume, US3 no-duplication, pre-existing stall → interrupted).
- [ ] T019 [P: ARCHITECTURE.md] Document campaign resume (the checkpoint model + auto/manual paths) in ARCHITECTURE.md.
- [ ] T020 Push branch; refresh staging; **stop for user review on staging before `/ship`** (do not auto-ship).

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (P1)**: none.
- **Foundation (P2)**: after Setup — BLOCKS all user stories (the resume engine lives here).
- **US1 / US2 / US3 (P3-5)**: after Foundation. US1 and US3 depend only on Foundation; US2 depends on Foundation + US1's `recover_games`/eligibility work (shares the campaign-detection + checkpoint_version semantics).
- **Polish (P6)**: after the desired stories.

### Within Foundation
- T002 (gamestate) and T003 (serialize round-trip test) are parallel (`[P]`, different files).
- T004→T005→T006 are sequential (all `heist/orchestration.py`). T007 depends on T002. T008 after T006.

### Parallel Opportunities
- T002 ∥ T003 (different files).
- T016 (lobby display) can proceed alongside T014/T015 once T009 lands.
- Test tasks (T008/T010/T013/T015) share `tests/test_campaign_resume.py` — run serially with each other.
