# Implementation Plan: Strategy-Prompt Wizard, Scouting Step & Premade Crews

**Branch:** `feat/crew-wizard` | **Date:** 2026-05-27 | **Spec:** [spec.md](spec.md)

## Summary

Recreate the guided strategy-prompt wizard (Job → Crew → **Scouting** → Decisions → Run It) as an in-page overlay on `setup.html`, switch campaign setup to an "add crews to a list" model, persist finished crews to a single `state/crews.json` via the existing `persist.py` helpers, expose `GET/POST/DELETE /api/crews`, and let Quick Test optionally launch from selected saved crews. No engine, mechanics, scoring, or scouting-resolution changes — scouting is already prompt-driven on `main`, so the Scouting step just writes instructions into the prompt.

## Technical Context

**Language/Version:** Python 3 (stdlib `http.server`, no web framework) + vanilla HTML/CSS/JS (no build step).
**Primary Dependencies:** none new. Reuses `heist/persist.py` (atomic write / defensive load), `heist/server.py` (routing), `heist/content.py` (presets), `heist/web/setup.html` + `heist/lobby.html` (UI).
**Storage:** JSON files under `HEIST_STATE_DIR` (default `./state/`). New: `state/crews.json` (a single JSON list).
**Testing:** `pytest -q`; lint `ruff`; types `mypy heist/ agents.py demo.py` (the project preflight).
**Target Platform:** local single-player web app; one shared state dir across the 8000/8001 servers.
**Performance Goals:** SC-001 — build a launch-ready prompt in <~60s via selections only; saved-crew list loads instantly (tiny file).
**Constraints:** no regression to existing freeform launch + Quick/Medium Test presets (SC-006); HTML-escape all stored/redisplayed player text (FR-014); degrade a corrupt/missing crews file to an empty list (FR-013).
**Scale/Scope:** a single local user with on the order of tens of saved crews; campaign supports 1–6 AIs (existing limit).

## Constitution Check

**Status:** SKIPPED — no constitution file found (`CONSTITUTION.md` / `docs/constitution.md` absent). The repo's CLAUDE.md "Locked Design Decisions" were reviewed: this feature changes none of them (it doesn't touch skills/scoring/collaboration/pricing/roster/board/resolution). It also honors the **two-lanes** rule — the wizard only authors the strategy prompt the AI lane consumes; it adds no UI-side game-state computation.

## Architecture Decisions

### Decision 1: Crew storage — single `state/crews.json` list

**Chosen:** Persist all premade crews as one JSON array in `state/crews.json`, read/written through the existing `heist/persist.py` `_atomic_write` / `_safe_load` / `_state_dir` helpers. Add `load_crews()`, `save_crews(list)`, plus thin `add_crew(crew)` / `delete_crew(id)` helpers.

**Rationale:**
- Mirrors the existing persistence pattern (atomic temp-file + `os.replace`, forgiving load) — same durability and crash-safety as game records.
- Server-side (not browser localStorage) so Quick Test, which launches from a server endpoint, can compose campaigns from saved crews.
- One small global list is simpler than a per-crew directory; the data is tiny and read/written whole.

**Alternatives considered:**
- *One file per crew under `state/crews/<id>.json`* (like `state/games/`): more moving parts than a handful of crews needs; rejected.
- *Browser `localStorage`*: invisible to the server, so Quick Test couldn't use saved crews; rejected.

**Tradeoffs:** Pros — trivial, durable, matches house style. Cons — whole-file rewrite per save (irrelevant at this scale).

### Decision 2: Crew identity & duplicate names

**Chosen:** Each crew gets a server-assigned stable `id` (string, e.g. `crew-<int counter>` or `uuid4().hex`). Display `name` is required but **need not be unique**; saving a duplicate name succeeds under a new `id` and the UI surfaces a non-blocking warning.

**Rationale:** Saving should never fail unexpectedly (FR-011); a server `id` makes load/delete unambiguous even with duplicate names, and avoids destructive overwrite.

**Alternatives considered:** *Name as primary key with hard-reject on collision* — more friction, and risks accidental overwrite if "update" were added later; rejected for MVP.

### Decision 3: Wizard as an in-page overlay; setup becomes an "add crews" list

**Chosen:** Keep one page (`setup.html`) with two views: (A) the **campaign assembler** — rounds selector, the list of crews added so far (each with name/agent/prompt-preview + remove), "Build a crew" and "Add from saved crew" actions, and Launch; (B) the **wizard overlay** — the guided steps (Job, Crew, Scouting, Decisions, Run It). "Run It" assembles an editable prompt, takes a name + agent, and offers **Add to Campaign** (append to the assembler list) and **Add Crew** (save to `crews.json`). Launch POSTs the whole list to the existing `/api/new-campaign`.

**Rationale:**
- Recreates the *guided, one-step-at-a-time* feel the user asked for, while fitting the current multi-AI campaign flow.
- Single page keeps the "campaign being assembled" state in one place — no cross-page state passing (the old wizard pushed to a server-side staging game; the campaign flow builds the AI list client-side then posts once).
- No new server route for the wizard; `/api/new-campaign` already accepts `{num_rounds, ais:[{name,prompt,agent}]}` unchanged.

**Alternatives considered:** *Separate `/wizard` route* — would need to stash the in-progress campaign across navigation; rejected. *Inline per-card mini-wizard* — loses the guided step-by-step flow the user wants; rejected.

**Tradeoffs:** Pros — faithful to the old wizard, minimal backend change, no regression to `/api/new-campaign`. Cons — replaces the current fixed "AI count 2/3/4 + N cards" control with a dynamic list (intended improvement, but it's a visible UI change to setup).

### Decision 4: Scouting step is prompt-text only

**Chosen:** The Scouting step picks a scouting *style*; the wizard's prompt builder emits a matching natural-language paragraph (modeled on the shipped Wreckers/Ghost preset language). No engine call, no new field on the campaign payload.

**Rationale:** Scouting on `main` is driven by the AI reading its strategy prompt and deciding probe spend; the effective lever is prompt text. This keeps the feature UI-only and avoids engine risk.

### Decision 5: Quick Test from saved crews — extend `/api/quick-campaign`

**Chosen:** `/api/quick-campaign` accepts an optional JSON body `{ "crew_ids": [...], "num_rounds": N }`. With `crew_ids`, it builds `ais` from those saved crews (falling back to the hardcoded `QUICK_TEST_CAMPAIGN` when absent/empty). Existing zero-body behavior is unchanged.

**Rationale:** Smallest change that satisfies P3 with no regression (SC-006); reuses the handler's existing game-dict construction.

## Project Structure

Monolithic Python package `heist/` + static web assets in `heist/web/` and `heist/lobby.html`.

```
heist/
├── persist.py        - MODIFY: add load_crews/save_crews/add_crew/delete_crew + crews-file path
├── server.py         - MODIFY: route GET/POST/DELETE /api/crews; extend /api/quick-campaign to accept crew_ids
├── web/
│   └── setup.html    - MODIFY: campaign-assembler view + wizard overlay (5 steps incl. Scouting) + Add Crew / Add from saved
└── lobby.html        - MODIFY (P3): "Quick Test from saved crews" entry point
specs/003-crew-wizard/
└── contracts/crews-api.yaml  - the /api/crews + quick-campaign contract
```

**Structure Decision:** All work lands in `heist/persist.py`, `heist/server.py`, `heist/web/setup.html`, and `heist/lobby.html`. `server.py` and `shell.js` are flagged in CLAUDE.md as high-conflict files; this feature touches `server.py` (additively) but **not** `shell.js`. No engine modules (`mechanics`, `resolution`, `scouting`-logic, `runner`, `orchestration`, `content` data) change, except an optional read of saved crews in the quick-campaign handler.

## Testing Strategy

- **Unit (pytest):** `persist` crew round-trip (save→load), delete removes only the target, corrupt/missing file → empty list, duplicate names keep distinct ids. Endpoint-level: `GET/POST/DELETE /api/crews` happy-path + validation (empty name/prompt rejected), `/api/quick-campaign` with `crew_ids` builds the right `ais` and with no body still uses the preset.
- **Manual (quickstart.md):** the per-user-story browser walkthroughs, verified on staging (8001) at each phase boundary.
- **Preflight before each push:** `ruff check . && mypy heist/ agents.py demo.py && pytest -q`.
