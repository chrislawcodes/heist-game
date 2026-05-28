# Quickstart: Strategy-Prompt Wizard, Scouting Step & Premade Crews

Manual test guide. Run the staging server from the staging worktree (Python is
loaded once, so restart it after Python changes; HTML/JS is read per request).

## Prerequisites

- [ ] Staging server running: `cd /Users/chrislaw/heist-game/.claude/worktrees/staging && python -m heist serve --port 8001`
- [ ] Staging refreshed to include `feat/crew-wizard` (`.claude/scripts/refresh-staging.sh` with the branch listed in `.claude/staging-branches.txt`)
- [ ] Browser at http://127.0.0.1:8001/

## Testing User Story 1 — Guided wizard with Scouting step (P1)

**Goal:** Build a launch-ready strategy prompt from selections, including a scouting paragraph that matches the chosen style.

**Steps:**
1. From the lobby, start a New Campaign → setup screen.
2. Click "Build a crew" to open the wizard overlay.
3. Step **The Job**: pick a Risk appetite (try Go Big).
4. Step **The Crew**: pick a budget posture (try All Stars).
5. Step **Scouting**: pick a scouting style (try "Case Everything").
6. Step **Decisions**: set bonus (Always) and on-fail (Push Through).
7. Step **Run It**: read the assembled prompt.

**Expected:**
- The prompt has a job paragraph for Go Big, a crew paragraph for All Stars, a **scouting paragraph** instructing heavy probe use before committing, and decision lines for Always-chase + Push-through.
- Switching the Scouting step to "Move Fast" and returning to Run It produces a **visibly different** scouting paragraph (SC-002).
- Typing into a step's override box replaces that step's generated paragraph; the summary marks it "(custom)".
- Editing the Run It textarea directly is preserved; relaunching the preview does not clobber manual edits.

**Verification:** Set name + agent, click "Add to Campaign", then Launch. The campaign viewer shows that crew; the AI's behavior (and scouting) reflects the strategy.

## Testing User Story 2 — Save / list / reuse premade crews (P2)

**Goal:** Persist a crew and reuse it without rebuilding.

**Steps:**
1. Build a crew in the wizard (US1). On Run It, give it a name and click **Add Crew**.
2. Reload the setup page.
3. Click "Add from saved crew" and pick the crew you saved.
4. Launch a campaign with it.
5. Delete the saved crew from the saved list.

**Expected:**
- After **Add Crew**, a confirmation shows; `curl -s localhost:8001/api/crews` lists the crew with an `id`, `name`, `agent`, `prompt`, `created_at`.
- After reload, the saved crew appears in "Add from saved crew" (persisted to disk).
- Launching uses the saved crew's stored name/agent/prompt.
- Saving a second crew with the **same name** succeeds under a new `id` and warns; the first crew is untouched.
- Delete removes exactly that crew; others remain (`GET /api/crews` confirms).

**Verification:** Restart the server, `GET /api/crews` — previously saved crews are still present (SC-003). Corrupt `state/crews.json` by hand → `GET /api/crews` returns `{"crews": []}`, server does not 500 (FR-013).

## Testing User Story 3 — Quick Test from saved crews (P3)

**Goal:** Run a Quick Test composed of selected saved crews.

**Steps:**
1. Save 2–3 crews (US2).
2. Choose "Quick Test from saved crews", select them, launch.
3. Separately, with the saved list empty (or via the default button), launch the normal Quick Test.

**Expected:**
- The custom quick run pits exactly the selected crews against the same slate over the quick-test round count; the viewer's competitor list shows their names.
- The default Quick Test (no crew_ids) still launches Operators/Wreckers/Ghost unchanged (SC-006).

**Verification:** `curl -s -X POST localhost:8001/api/quick-campaign -d '{"crew_ids":["<id1>","<id2>"]}'` returns a `campaign_id`; the campaign's `ais_cfg` matches the chosen crews. `curl -s -X POST localhost:8001/api/quick-campaign -d '{}'` returns the 3-team preset.

## Troubleshooting

- **Python changes not reflected:** restart the staging server (Python loads once). HTML/JS is per-request.
- **Saved crews not appearing across servers:** confirm both servers share the same `HEIST_STATE_DIR` (state is shared by design).
- **Wizard prompt not updating:** the Run It preview rebuilds on entering the step; manual edits are intentionally preserved over regeneration.
