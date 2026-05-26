# Plan Summary: Campaign Resume

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/orchestration.py` | modify | `run_campaign_conductor(..., resume=False)`: rebuild `campaigns[i]` from `game_states[i]`, restore `round_gids_per_ai`/`hiring_gids`, re‑enter the round loop at `current_round_idx`/`current_stage`, skip completed rounds+stages. Stamp `checkpoint_version=1` in `snapshot_all`. `recover_games()`: add `is_campaign` branch — resume if `checkpoint_version>=1`, else set `status="interrupted"`. Add `active_campaigns` add/remove around the conductor. |
| `heist/gamestate.py` | modify | `runtime.active_campaigns: set[int]` (double‑conductor guard registry). |
| `heist/server.py` | modify | New route `POST /api/campaign/<id>/resume` → `_handle_resume_campaign` (guard, then spawn `run_campaign_conductor(resume=True)`). Startup `recover_games()` call already exists. |
| `heist/serialize.py` | verify | Confirm `campaign_from_dict` round‑trips a `game_states[i]` entry (reads only campaign fields, ignores extras). Add nothing unless a gap is found. |
| `heist/lobby.html` | modify | Small "Resume" affordance on a stalled campaign row (POSTs the new endpoint); show `interrupted` status. Only UI change in scope. |
| `tests/test_campaign_resume.py` | create | rebuild‑from‑snapshot round‑trip; stage‑skip idempotency (no double‑bank, settle‑once); `recover_games` campaign branch (resume vs interrupted); double‑conductor guard. |
| `state/games/*.json` | data | gains `checkpoint_version` (and optional `resumed_count`); pre‑existing running campaigns become `interrupted`. |

## Migration Steps

None (schema is additive JSON fields; no migration script). On first startup after deploy, `recover_games()` marks any currently‑`running` campaign without `checkpoint_version` as `interrupted`.

## Data Model

**Campaign record** (`state/games/<id>.json`) — extended, not new:
- New: `checkpoint_version: int` (=1 ⇒ resumable), optional `resumed_count: int`, new terminal `status="interrupted"`.
- Checkpoint = existing `current_round_idx` + `current_stage` + per‑team `game_states[i]` (`campaign_to_dict`: standing_crew, banked_loot, round_results) + `round_game_ids`/`hiring_game_ids`.

## Key Constraints

- **Stage‑boundary resume** — resume re‑enters at `current_stage`, skipping stages at/before the last completed one. *Why: hiring deducts banked loot and settle banks the take; re‑running a completed stage double‑counts.*
- **`settle_round` exactly once per round** — reconcile via `len(round_results)` vs `current_round_idx` if the crash landed between settle and round‑advance. *Why: a duplicate settle double‑banks and double‑removes caught crew.*
- **Eligibility = `checkpoint_version>=1`** — else mark `interrupted`. *Why: resolved decision — pre‑existing stalls (game 14) aren't guaranteed to have sufficient checkpoint state.*
- **Double‑conductor guard** — `runtime.active_campaigns` set; manual resume returns 409 if the id is live. *Why: two conductors on one campaign duplicate rounds and corrupt economy.*
- **Two‑lanes** — resume re‑emits the normal campaign events (`campaign_stage`, heist events, `campaign_round_done`, `campaign_done`). *Why: UI only displays; it must not reconstruct resumed state itself.*
- **Reuse existing persistence** — no parallel checkpoint store; reconstruct from `game_states`. *Why: avoids divergence and reuses tested serializers.*
