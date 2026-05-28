# Tasks: Strategy-Prompt Wizard, Scouting Step & Premade Crews

**Prerequisites:** plan.md, plan-summary.md, spec.md, spec-acceptance.md, data-model.md, contracts/crews-api.yaml

## Format: `[ID] [P: file]? [Story]? Description`

- **[P: file]**: can run in parallel (disjoint file scope listed). Bare/absent = serial.
- **[US1/US2/US3]**: user story label (user-story phases only).
- Paths are repo-relative.

---

## Phase 1: Setup

**Purpose:** Baseline ready (branch already created off `origin/main`).

- [ ] T001 Confirm preflight baseline is green on `feat/crew-wizard`: `ruff check . && mypy heist/ agents.py demo.py && pytest -q`.

---

## Phase 2: Foundation

**Purpose:** None blocking *all* stories. US1 is frontend-only on `setup.html`; the crew store + endpoints are prerequisites for US2/US3 and are created at the top of the US2 phase. No shared foundation work precedes US1.

**Checkpoint:** Proceed directly to User Story 1.

---

## Phase 3: User Story 1 — Guided wizard with Scouting step (Priority: P1) 🎯 MVP

**Goal:** Build a complete, editable strategy prompt from guided selections (Job → Crew → Scouting → Decisions → Run It) and launch a campaign with it via the existing `/api/new-campaign`.

**Independent Test:** Open the wizard, make selections (incl. Scouting), confirm the assembled prompt reflects every choice, edit it, name + pick agent, Add to Campaign, Launch → campaign viewer opens and the AI plays the strategy.

### Implementation for User Story 1

- [ ] T002 [US1] In `heist/web/setup.html`, restructure into two views: a **campaign-assembler** view (rounds chips, an empty "crews added" list, "Build a crew" + "Add from saved crew" buttons, Launch) and a hidden **wizard overlay** container. Keep the existing dark theme/CSS tokens.
- [ ] T003 [US1] In `heist/web/setup.html`, build the wizard overlay markup: a progress track with steps **The Job / The Crew / Scouting / Decisions / Run It**, choice-cards per step (Risk: Lay Low/Balanced/Go Big; Budget: Stretch/Mix It Up/All Stars; Scouting: Case Everything/Scout the Money/Move Fast; Bonus: Always/Smart/Stick to Plan; Fail: Push Through/Cut Losses), and a per-step free-text **override** box.
- [ ] T004 [US1] In `heist/web/setup.html`, implement step navigation (next/back, clickable progress, one step visible at a time) mirroring the old wizard's UX.
- [ ] T005 [US1] In `heist/web/setup.html`, implement the **prompt builder**: map each choice to a paragraph (job, crew, scouting, decisions); a step's override replaces its generated paragraph; the **Scouting** paragraph has 3 distinct variants modeled on the shipped Wreckers/Ghost preset language ("case it before you crack it", "don't read difficulty off payout") so the engine's scouting turn acts on it.
- [ ] T006 [US1] In `heist/web/setup.html`, implement the **Run It** step: a name input, an agent `<select>` (stub / codex / codex-mini / gemini), an editable assembled-prompt textarea that is **never silently regenerated over manual edits**, and a summary that marks overridden steps "(custom)".
- [ ] T007 [US1] In `heist/web/setup.html`, wire **Add to Campaign**: append `{name, agent, prompt}` to the assembler list; render the list (name + agent badge + prompt preview + Remove); HTML-escape all rendered crew text.
- [ ] T008 [US1] In `heist/web/setup.html`, wire **Launch**: block empty/whitespace prompts and the zero-crew case with a clear message; POST `{num_rounds, ais:[...]}` to `/api/new-campaign`; on success redirect to `/campaign?game=<id>` (matches existing flow).

**Checkpoint:** US1 fully functional and testable standalone. **STOP for staging review (8001) before P2.**

---

## Phase 4: User Story 2 — Save, list & reuse premade crews (Priority: P2)

**Goal:** Persist a finished crew server-side (Add Crew), list/load/delete it, reuse without rebuilding.

**Independent Test:** Build a crew, Add Crew, reload, Add-from-saved into a campaign and launch; delete a saved crew; restart server and confirm persistence.

### Foundation for User Story 2 (crew store + API)

- [ ] T009 [P: heist/persist.py] [US2] In `heist/persist.py`, add `_crews_path()` (`_state_dir()/"crews.json"`), `load_crews()` (→ `payload.get("crews", [])`; `[]` on missing/corrupt/non-list; skip entries missing id/name/prompt), `save_crews(list)` (`_atomic_write(path, {"crews": crews})`), `add_crew(crew)` (assign `id`=uuid4 hex + `created_at`, append, save, return stored crew), `delete_crew(id)` (filter, save, return bool removed).
- [ ] T010 [US2] In `heist/server.py`, register routes: `GET /api/crews` → `_serve_crews` (return `{"crews": load_crews()}`); `POST /api/crews` → `_handle_save_crew` (read JSON, trim+validate non-empty `name` & `prompt`→400 else, default `agent` to `stub`, keep optional `wizard`, call `add_crew`, return `{ok, crew}`); `DELETE /api/crews/{id}` → `_handle_delete_crew` (404 if not removed, else `{ok}`). Add the `do_DELETE` branch for `/api/crews/<id>`.

### UI for User Story 2

- [ ] T011 [US2] In `heist/web/setup.html`, add **Add Crew** on the wizard Run It step: POST current `{name, agent, prompt, wizard}` to `/api/crews`; show a confirmation; if the name matches an existing saved crew, show a non-blocking duplicate-name warning (still saves under a new id).
- [ ] T012 [US2] In `heist/web/setup.html`, implement **Add from saved crew**: fetch `GET /api/crews`, show a picker (empty-state when none), append the chosen crew to the assembler list; add a delete control that calls `DELETE /api/crews/{id}` and refreshes the picker.

### Tests for User Story 2

- [ ] T013 [P: tests/test_crews_persist.py] [US2] Add `tests/test_crews_persist.py`: save→load round-trip; delete removes only the target; missing file → `[]`; corrupt/non-list file → `[]`; two crews with the same name keep distinct ids; uses a tmp `HEIST_STATE_DIR`.
- [ ] T014 [P: tests/test_crews_api.py] [US2] Add `tests/test_crews_api.py`: `POST /api/crews` happy path returns id+created_at; empty name/prompt → 400; `GET` lists saved; `DELETE` removes target and 404s on unknown id. (Follow the existing server-test harness pattern in `tests/`.)

**Checkpoint:** US2 fully functional. **STOP for staging review (8001) before P3.**

---

## Phase 5: User Story 3 — Quick Test from premade crews (Priority: P3)

**Goal:** Launch a Quick Test composed of selected saved crews; default (no selection) preset unchanged.

**Independent Test:** Save 2–3 crews, launch a Quick Test from them; separately confirm the default Quick Test still launches Operators/Wreckers/Ghost.

### Implementation for User Story 3

- [ ] T015 [US3] In `heist/server.py`, extend `_handle_quick_campaign` to read an optional JSON body `{crew_ids?, num_rounds?}`: when `crew_ids` is present & non-empty, build `ais` from `load_crews()` (preserve selection order; validate every id exists and count is 1–6 → 400 otherwise); when absent/empty, behavior is byte-for-byte the current preset path. `num_rounds` defaults to `QUICK_TEST_CAMPAIGN_ROUNDS`.
- [ ] T016 [US3] In `heist/lobby.html`, add a **Quick Test from saved crews** entry point: fetch `GET /api/crews`, let the player select crews (disabled/hidden when none saved), POST `{crew_ids}` to `/api/quick-campaign`, redirect to the campaign viewer. Leave the existing one-click Quick Test / Medium Test buttons working unchanged.
- [ ] T017 [P: tests/test_quick_campaign_crews.py] [US3] Add `tests/test_quick_campaign_crews.py`: `crew_ids` builds matching `ais` (right names/agents/prompts, right order); unknown id or count>6 → 400; empty/no body → the 3-team preset over `QUICK_TEST_CAMPAIGN_ROUNDS`.

**Checkpoint:** US3 complete. Staging review (8001).

---

## Phase 6: Polish & Cross-Cutting

- [ ] T018 [P: ARCHITECTURE.md] Document the `/api/crews` endpoints, the `state/crews.json` store, and the wizard view in `ARCHITECTURE.md`.
- [ ] T019 Run the full `quickstart.md` walkthrough on staging (8001) for US1–US3; confirm preflight green (`ruff`, `mypy`, `pytest -q`) before each push.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (P1)**: none.
- **Foundation (P2 phase header)**: none blocking US1.
- **US1 (P1)**: independent; frontend-only on `setup.html`.
- **US2 (P2)**: T009 (persist) → T010 (endpoints) → T011/T012 (UI). T013/T014 after T009/T010.
- **US3 (P3)**: needs the US2 crew store/endpoints (T009/T010) to exist; T015 → T016; T017 after T015.
- **Polish (P6)**: after the targeted stories complete.

### User Story Dependencies
- US1: independent after Setup.
- US2: depends on its own foundation tasks (T009/T010); independent of US1 at the engine level but UI lives in the same `setup.html`.
- US3: depends on US2's store/endpoints.

### Parallel Opportunities
- T009 (`persist.py`) is `[P]` vs the test files; the server route work (T010) depends on it.
- Test files T013/T014/T017 have disjoint paths and can be written in parallel with each other once their targets exist.
- UI tasks all touch `heist/web/setup.html` → **serial** within and across US1/US2 (same file).

### MVP-first / staging gates
- Ship + review **US1** on staging before starting US2.
- Ship + review **US2** on staging before starting US3.
- Each phase: commit → push → `.claude/scripts/refresh-staging.sh` → user reviews on 8001.
