# Feature Specification: Strategy-Prompt Wizard, Scouting Step & Premade Crews

**Feature branch:** `feat/crew-wizard`
**Created:** 2026-05-27
**Status:** Draft → Planning
**Input:** Recreate the old guided wizard that builds an AI's strategy prompt (it was replaced by a flat free-text form). Add a new **Scouting** step so the player can direct how the AI spends its scouting probes — scouting now exists on `main` and is prompt-driven, so this is a real, effective choice. Then let the player **save** a finished crew (name + agent + strategy prompt) as a reusable **premade crew** via an "Add Crew" button, and **reuse** saved crews when assembling a campaign and in Quick Test, so the same crews don't have to be rebuilt every time.

---

## Overview

Today, starting a campaign means writing a freeform strategy prompt in a plain textarea (`heist/web/setup.html`). Earlier the game had a guided **wizard** (The Job → The Crew → Decisions → Run It) that assembled that prompt from a few simple choices, with a final editable preview. That wizard was dropped.

This feature brings the wizard back, adds a **Scouting** step (scouting shipped to `main` in Phase 4 and is driven by the strategy prompt the AI reads), and then adds **persistence**: a finished crew can be saved server-side and reused. The player builds a crew once, names it, clicks **Add Crew**, and from then on can drop it into any campaign — including **Quick Test** — without rebuilding it.

A "crew" here is **one AI competitor profile**: a name, an agent (stub / codex / gemini / codex-mini), and a strategy prompt. (It is *not* the in-game hired roster the AI bids for — that stays AI-owned.) This matches how Quick Test already works: it launches several named competitor profiles against the same slate.

Scope is sequenced MVP-first:
- **P1** — recreate the wizard (with the new Scouting step) and produce a strategy prompt usable in campaign setup.
- **P2** — save / list / delete premade crews server-side; load a saved crew back into setup.
- **P3** — assemble Quick Test (and campaign setup) from saved premade crews instead of only the hardcoded presets.

This is a UI + thin-persistence feature. It does **not** change the engine, mechanics, scoring, or how scouting resolves — it only changes how the strategy prompt that drives those systems is authored, stored, and reused.

---

## User Scenarios & Testing

### User Story 1 — Guided strategy-prompt wizard with a Scouting step (Priority: P1)

As a **player setting up a campaign**, I want to build an AI's strategy prompt by answering a few guided questions — including how the AI should use its scouting probes — so that I get a coherent, complete strategy without staring at a blank textarea, and the scouting choice actually changes how the AI plays.

**Why this priority:** This is the core ask and the foundation for everything else. Premade crews (P2) save the *output* of this wizard; Quick Test reuse (P3) consumes saved crews. Without the wizard there is nothing to save or reuse. It must produce a prompt at least as usable as today's freeform box, and it must integrate with the existing campaign-launch flow.

**Independent Test:** Open the wizard from the lobby/setup. Step through The Job, The Crew, Scouting, and Decisions making selections; on the final step confirm the assembled strategy prompt reflects every choice (notably a scouting paragraph that matches the chosen scouting style), edit it freely, name the crew, pick an agent, and launch a campaign. Verify the campaign starts with that prompt and the AI's behavior reflects the strategy (including scouting) in the viewer.

**Acceptance Scenarios:**

1. **Given** the player opens the wizard, **When** they choose a Risk appetite (Lay Low / Balanced / Go Big), **Then** the assembled prompt's job-selection paragraph matches that choice.
2. **Given** the player is on the Crew step, **When** they choose a budget posture (Stretch Budget / Mix It Up / All Stars), **Then** the assembled prompt's crew-building paragraph matches that choice.
3. **Given** the player is on the **Scouting** step, **When** they choose a scouting style (e.g. Case Everything / Scout the Money / Move Fast), **Then** the assembled prompt contains a scouting instruction paragraph matching that choice, phrased so the engine's scouting turn acts on it.
4. **Given** the player is on the Decisions step, **When** they set bonus handling (Always / Smart / Stick to Plan) and failure handling (Push Through / Cut Losses), **Then** both choices appear in the assembled prompt.
5. **Given** any step, **When** the player types into that step's free-text override box, **Then** the override replaces the generated paragraph for that step (and the summary marks it "custom").
6. **Given** the final "Run It" step, **When** the player edits the assembled prompt directly, **Then** the edited text is what launches (the wizard never silently overrides manual edits).
7. **Given** a completed wizard, **When** the player launches, **Then** a campaign is created via the existing campaign API with the crew's name, agent, and prompt, and the player lands in the campaign viewer.

---

### User Story 2 — Save, list & reuse premade crews (Priority: P2)

As a **player**, I want to save a finished crew (name + agent + strategy prompt) with an **Add Crew** button and pull it back later, so that I don't rebuild the same crews every time I start a campaign.

**Why this priority:** This is the persistence the user explicitly asked for ("save so you don't have to redo this all the time"). It depends on P1 (something to save) but is independently valuable: once saved, crews can be loaded into the normal campaign setup even before Quick Test integration (P3) exists.

**Independent Test:** Build a crew in the wizard, click **Add Crew**, and confirm it persists server-side (survives a page reload and appears in the saved-crews list returned by the API). Load it back into setup and launch a campaign with it without re-running the wizard. Delete a saved crew and confirm it disappears from the list.

**Acceptance Scenarios:**

1. **Given** a completed crew in the wizard (name + agent + prompt), **When** the player clicks **Add Crew**, **Then** the crew is saved server-side and a confirmation is shown.
2. **Given** saved crews exist, **When** the setup screen loads, **Then** the player sees the list of saved crews and can pick one to add to the campaign.
3. **Given** a saved crew is picked, **When** the campaign launches, **Then** it uses the saved crew's stored name, agent, and prompt.
4. **Given** saved crews exist, **When** the player deletes one, **Then** it is removed from the store and no longer appears in the list (other crews are untouched).
5. **Given** a crew name that already exists, **When** the player saves, **Then** the system makes the result unambiguous (e.g. rejects the duplicate with a clear message, or saves under a distinct identifier) rather than silently corrupting the existing crew.
6. **Given** the server restarts, **When** the saved-crews list is requested again, **Then** previously saved crews are still present (persisted to disk, like game state).

---

### User Story 3 — Compose Quick Test (and campaign setup) from premade crews (Priority: P3)

As a **player**, I want Quick Test and campaign setup to let me pick from my saved premade crews instead of only the three hardcoded teams, so that I can quickly pit my own saved crews against each other.

**Why this priority:** This is the convenience payoff, but the game already ships working Quick Test presets, so it's the lowest-priority slice. It depends on P2 (saved crews must exist to choose from).

**Independent Test:** Save 2–3 crews via P2. Start a Quick Test composed of saved crews (rather than the default Operators/Wreckers/Ghost), and confirm the campaign runs those crews against the same slate and shows them in the viewer's competitor list.

**Acceptance Scenarios:**

1. **Given** saved crews exist, **When** the player starts a Quick Test, **Then** they can choose to run it with selected saved crews instead of the hardcoded preset.
2. **Given** no saved crews exist, **When** the player starts a Quick Test, **Then** the existing hardcoded preset still works unchanged (no regression).
3. **Given** the player selects N saved crews for a quick run, **When** it launches, **Then** exactly those N crews compete, with their stored names/agents/prompts, over the quick-test round count.

---

## Edge Cases

- **Empty / whitespace prompt at launch** → launch is blocked with a clear message; matches the existing API rule that a prompt must be a non-empty string.
- **Empty crew name** → falls back to a sensible default (the existing API already defaults to "AI N"); for *saved* crews a name is required so the player can identify it later.
- **No saved crews yet** → setup and Quick Test still work; the saved-crews UI shows an empty state, and the hardcoded Quick Test preset remains the default.
- **Duplicate crew name on save** → resolved deterministically (reject-with-message or distinct id); never silently overwrite a different crew. (Resolved in Assumptions.)
- **Corrupt / unparseable crews file on disk** → server treats it as "no saved crews" and does not crash (mirrors how game records load defensively), surfacing an empty list rather than a 500.
- **Override box used on a step** → the generated paragraph for that step is fully replaced by the override; the final prompt is always editable and wins over generated text.
- **Selecting more saved crews than the campaign supports** → bounded by the existing campaign limit (1–6 AIs); selection beyond the limit is prevented or rejected with a clear message.
- **Saved crew references an agent that's unavailable** → it still launches as far as the engine allows; agent validity is the engine's existing concern, not new behavior here.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a multi-step wizard that assembles an AI strategy prompt from guided choices, with steps for **The Job** (risk appetite), **The Crew** (budget posture), **Scouting** (probe usage), **Decisions** (bonus handling + failure handling), and a final **Run It** review step.
- **FR-002**: Each guided step MUST offer a small set of preset choices AND a free-text override that replaces that step's generated text when used.
- **FR-003**: The wizard MUST show a live, editable preview of the full assembled strategy prompt on the final step; manual edits MUST be preserved and used verbatim at launch (no silent regeneration over edits).
- **FR-004**: The **Scouting** step MUST produce a scouting-instruction paragraph phrased so the existing prompt-driven scouting turn acts on it (e.g. how aggressively to spend probes, whether to scout before committing, not reading difficulty off payout).
- **FR-005**: The wizard MUST let the player set a crew **name** and choose an **agent**, and MUST launch a campaign through the existing campaign-launch API using that name, agent, and prompt.
- **FR-006**: The wizard MUST NOT allow launching with an empty/whitespace-only prompt.
- **FR-007**: The system MUST let the player **save** a finished crew (name + agent + strategy prompt, plus enough to reload it) via an **Add Crew** action.
- **FR-008**: Saved crews MUST persist to disk server-side (so they survive server restarts) under the existing state directory, following the existing atomic-write / defensive-load pattern used for game records.
- **FR-009**: The system MUST expose endpoints to **list**, **save**, and **delete** premade crews.
- **FR-010**: The setup screen MUST let the player load a saved crew and add it to a campaign without re-running the wizard.
- **FR-011**: Saving a crew with a name that collides with an existing crew MUST be handled deterministically (reject with a clear message OR persist under a distinct identifier) — never a silent overwrite of a different crew.
- **FR-012**: Quick Test MUST be able to run a campaign composed of selected saved crews, while the existing hardcoded Quick Test preset MUST keep working when no saved crews are chosen (no regression).
- **FR-013**: A corrupt or missing crews store MUST degrade to an empty saved-crews list, not a server error.
- **FR-014**: All crew-derived text rendered in the UI MUST be HTML-escaped (the existing setup/lobby code already escapes user text; saved crews introduce stored player text that is re-displayed).

### Key Entities

- **Premade Crew** — a reusable AI competitor profile.
  - `id` — stable identifier (used for load/delete).
  - `name` — player-facing label (required for saved crews).
  - `agent` — which backend runs it (stub / codex / codex-mini / gemini).
  - `prompt` — the assembled (and possibly hand-edited) strategy prompt string.
  - `wizard` (optional) — the wizard selections (risk, budget, scouting, bonus, fail, overrides) captured at save time, so the crew can be reopened in the wizard for editing.
  - `created_at` — timestamp, for ordering/display.

---

## Success Criteria

- **SC-001**: A player can produce a launch-ready strategy prompt through the wizard in under ~60 seconds without typing any prose (selections only), and the prompt visibly reflects all chosen dimensions including scouting.
- **SC-002**: Changing only the Scouting step produces a visibly different scouting paragraph in the assembled prompt (the step is not cosmetic).
- **SC-003**: A crew saved with **Add Crew** is still present after a full server restart and can be launched without rebuilding.
- **SC-004**: Deleting a saved crew removes exactly that crew and leaves all others intact.
- **SC-005**: A Quick Test can be launched composed entirely of saved crews; with zero saved crews, the original hardcoded Quick Test still launches unchanged.
- **SC-006**: No regression: the existing freeform/flat campaign-launch path and the existing Quick Test / Medium Test presets continue to work end-to-end.

---

## Assumptions

- **"Crew" = AI competitor profile** (name + agent + prompt), not the in-game hired roster the AI bids for. The AI still owns roster selection at runtime.
- **Storage is server-side** at `state/crews.json` (under `HEIST_STATE_DIR`), using the existing atomic-write + defensive-load helpers in `heist/persist.py`. Rationale: game state is shared across all servers, and Quick Test launches from a server endpoint, so crews must live server-side (not browser localStorage) to be reusable there.
- **Duplicate-name policy:** save under a server-assigned distinct `id` and allow duplicate display names, but warn the player; this avoids destructive overwrite while keeping the flow frictionless. (Chosen over hard-reject so saving never fails unexpectedly.)
- **Scouting is prompt-driven on `main`** (the Phase 4 engine reads the strategy text and decides probe spend); therefore the Scouting step writes natural-language instructions into the prompt rather than calling any new engine API. No engine changes are needed.
- **Agent options** mirror what `setup.html` and the presets already use (stub / codex / codex-mini / gemini); no new agents are introduced.
- **The wizard targets the existing campaign flow** (`/api/new-campaign`, multi-AI). It builds **one crew at a time**; assembling multiple crews into a campaign is done by adding/loading several crews on the setup screen.
- **No multiplayer / no auth** — single local player, consistent with current Phase 1–4 scope; saved crews are global to the local install.

---

## Out of Scope

- Changing the scouting engine, scoring, mechanics, or resolution.
- Editing saved crews in place beyond reopening them in the wizard and re-saving.
- Sharing/exporting crews between machines or users.
- Replacing the hardcoded Quick Test presets (they remain as the zero-config default).
- Bidding/roster behavior (still AI-owned at runtime).
