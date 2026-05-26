# Data Model: Campaign Resume

No database. State is a JSON record per game at `state/games/<id>.json`. This feature adds **two fields** to the existing campaign record and reuses the rest as the resume checkpoint. No new entity/store.

## Entity: Campaign record (existing, extended)

**Storage**: `state/games/<id>.json`

| Field | Type | New? | Description |
|-------|------|------|-------------|
| `id` | int | — | Campaign / game id |
| `is_campaign` | bool | — | True for campaigns (vs single Phase‑1 games) |
| `status` | str | — | `running` / `done` / `error` / **`interrupted`** (new terminal value) |
| `num_rounds` | int | — | Total rounds |
| `current_round_idx` | int | — | Round in progress — written by `set_stage()`. **Resume start round.** |
| `current_stage` | str | — | `opening_wire`/`hiring`/`heist`/`reflection` — written by `set_stage()`. **Resume start stage.** |
| `progress` | obj | — | Heartbeat (`updated_at`, …) — used for stall detection |
| `game_states[i]` | obj | — | Per‑team snapshot from `snapshot_all()`: `campaign_to_dict(camp)` (standing_crew, banked_loot, round_results) + `round_game_ids`, `hiring_game_ids`, `ai_idx`, `ai_name`, `status`. **The per‑team checkpoint.** |
| `game_states[i].pending_heist` | obj/null | ✅ | Heist‑take checkpoint, written after the heist stage: `{final_take, heat, caught_member_ids, job_name, aborted, escape_success}`. Lets reflection resume + settle without re‑running the heist. Cleared (set null) once `settle_round` consumes it. |
| `ais_cfg` | list | — | Per‑AI `{name, agent, prompt}` — rebuilds the backends on resume |
| **`checkpoint_version`** | int | ✅ | Stamped by the conductor (`=1`). Marks a campaign as resumable under the new checkpointing. Absent ⇒ pre‑existing stall ⇒ marked `interrupted`. |
| **`resumed_count`** | int | ✅ (optional) | Times this campaign has been resumed (observability; supports repeatable‑resume, FR‑011). |

**Validation / invariants**:
- A round is "complete" iff its `RoundResult` is present in every active team's `round_results`. Resume skips rounds `< current_round_idx`.
- `settle_round` appends exactly one `RoundResult` per round per team; resume must not append a duplicate (reconcile via `len(round_results)` vs `current_round_idx`).
- `banked_loot` in `game_states[i]` already reflects all completed stages (hiring deductions + banked takes); resume must not re‑apply a completed stage's economy effects.

## Reconstruction (in‑memory, on resume)

```
campaigns[i]            = campaign_from_dict(game_states[i])      # standing_crew, banked_loot, round_results
round_gids_per_ai[i]    = game_states[i]["round_game_ids"]
hiring_gids             = game_states[i]["hiring_game_ids"]       # same list across teams
start_round             = record["current_round_idx"]
start_stage             = record["current_stage"]
```

No migration script — the two new fields are additive and default‑absent on old records (which are handled by the `interrupted` path).
