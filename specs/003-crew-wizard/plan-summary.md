# Plan Summary: Strategy-Prompt Wizard, Scouting Step & Premade Crews

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/persist.py` | modify | Add `_crews_path`, `load_crews`, `save_crews`, `add_crew`, `delete_crew`; store as `{"crews":[...]}` in `state/crews.json` via existing atomic-write/safe-load. |
| `heist/server.py` | modify | Route `GET/POST /api/crews` and `DELETE /api/crews/{id}`; add handlers `_serve_crews`, `_handle_save_crew`, `_handle_delete_crew`; extend `_handle_quick_campaign` to accept optional `{crew_ids, num_rounds}`. |
| `heist/web/setup.html` | modify | Two views: campaign assembler (rounds + added-crew list + Build/Add-from-saved + Launch) and the wizard overlay (Job→Crew→Scouting→Decisions→Run It) with prompt builder, Add to Campaign, and **Add Crew**. |
| `heist/lobby.html` | modify (P3) | "Quick Test from saved crews" entry point posting `crew_ids` to `/api/quick-campaign`. |
| `specs/003-crew-wizard/contracts/crews-api.yaml` | (done) | Endpoint contract. |

## Migration Steps

None. New file `state/crews.json`; absent file == empty list. No changes to existing game records.

## Data Model

**Premade Crew**: `state/crews.json` (`{"crews":[...]}`) — `id` (server-assigned, unique), `name` (required, non-unique), `agent` (stub|codex|codex-mini|gemini), `prompt` (required), optional `wizard` snapshot `{risk,budget,scouting,bonus,fail,overrides}`, `created_at`. Copied by value into a campaign's `ais_cfg` at launch (no id reference).

## Key Constraints

- **Server-side store at `state/crews.json`** via `persist.py` helpers — *Why: Quick Test launches from a server endpoint, so crews must be server-side, not browser localStorage.*
- **Scouting step writes prompt text only**, no engine call — *Why: scouting on main is prompt-driven (AI reads strategy text and decides probe spend); keeps the feature UI-only and engine-risk-free.*
- **Duplicate names allowed under distinct server `id`, with a warning** — *Why: saving must never fail unexpectedly or silently overwrite a different crew (FR-011).*
- **Corrupt/missing crews file → `[]`, never 500** — *Why: mirrors forgiving game-record loading; a bad file can't down the server.*
- **HTML-escape all stored/redisplayed crew text** — *Why: saved crews are stored player text re-rendered in the UI (XSS).* 
- **`/api/quick-campaign` with no body is byte-for-byte the old behavior** — *Why: no regression to the shipped Quick/Medium Test presets (SC-006).*
- **Wizard targets existing `/api/new-campaign` (`{num_rounds, ais:[{name,prompt,agent}]}`)** unchanged — *Why: no backend change needed for launch; lowers blast radius.*
- **Run It preview never clobbers manual edits** — *Why: FR-003; the final prompt is the contract and the player can hand-tune it.*
