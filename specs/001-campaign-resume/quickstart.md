# Quickstart: Campaign Resume (manual testing)

## Prerequisites
- [ ] Branch `feat/campaign-resume` running on a spare port against an **isolated** state dir, e.g.
      `HEIST_STATE_DIR=$(mktemp -d) python3 -m heist serve --port 8123`
- [ ] Use the stub agent where possible for speed/no API spend (single games). For campaign behavior, a Quick/Medium Test uses real codex agents — slower; prefer a short campaign.

## US1 — A campaign survives a server restart (P1)

**Goal**: An interrupted campaign auto‑resumes and finishes (FR‑001/002, SC‑001/002).

**Steps**:
1. Launch a multi‑round campaign; let it complete round 1 and enter round 2.
2. Note the war‑room standings (banked loot + crew per team) and `current_round_idx`/`current_stage` in `state/games/<id>.json`.
3. Kill the server (`kill <pid>`), then start it again on the same state dir.
4. Watch the campaign continue.

**Expected**:
- The campaign resumes (does NOT restart at round 0) and runs to completion.
- Round‑1 results (job, take, banked, crew, caught) are byte‑for‑byte unchanged.
- No duplicate round or sub‑game; final standings match an uninterrupted run.

**Verification**:
- `state/games/<id>.json`: `round_results` length never decreases; no duplicate `round_idx`; `banked_loot` for round 1 unchanged across the restart.
- Server log shows a campaign recovery line (not the single‑game auction path).

## US2 — Manual resume of a stalled campaign (P2)

**Goal**: Revive a stalled campaign without a full restart (FR‑008/009, SC‑004).

**Steps**:
1. With the server up, simulate a dead conductor (e.g., a campaign whose thread crashed / a campaign whose `progress.updated_at` is older than the stall threshold and which is not in `active_campaigns`).
2. `curl -X POST http://localhost:8123/api/campaign/<id>/resume -d '{}'`.

**Expected**:
- 200 + `{ ok: true, resumed_from: {round_idx, stage} }`; the campaign continues.
- Other running games are unaffected.
- Calling resume on a campaign that is genuinely still running returns **409** (no second conductor).

## US3 — Resume is visibly correct (P3)

**Goal**: Completed rounds intact, nothing duplicated (FR‑004/007, SC‑005).

**Steps**:
1. Open the war room before and after a resume.

**Expected**:
- Every previously‑completed round shows the same job / take / banked / crew / caught.
- On completion, round count and sub‑game count match the campaign length (no duplicates).

## Pre‑existing stalls (resolved decision)

**Steps**:
1. Take a campaign that has NO `checkpoint_version` (e.g., the current game 14), restart the server.

**Expected**:
- It is marked `status="interrupted"` (not resumed, not left "running"). It should be deleted and re‑run.

## Troubleshooting
- **Resumed campaign restarts from round 0** → reconstruction didn't read `current_round_idx`, or `campaigns[i]` weren't rebuilt from `game_states[i]`.
- **Banked loot doubled** → a completed stage (hiring or settle) was re‑run; check the stage‑skip logic and the `settle_round`‑once reconciliation.
- **Two conductors / duplicated rounds** → `active_campaigns` guard not honored.
