# Contract: Scout Persistence — events & persisted fields

This feature adds no HTTP endpoints. The cross-lane contract is (a) the event stream the engine emits into each round's heist sub-game, and (b) the new persisted fields. Both are listed so the UI lane and resume path can rely on them.

## Event: `scouted` (existing shape, new emission timing)

Already defined; unchanged shape:
```json
{ "type": "scouted", "job": "<name>", "category": "electronic|physical|confrontation|social",
  "reveal_level": "EXACT", "bucket": "LOW|MEDIUM|HIGH", "score": 1-10,
  "probes_remaining_free": <int> }
```

**New timing (FR-007)**: at the start of each campaign round, the engine emits one `scouted` event per cell the team already knew from prior rounds — *before* the round's scout turn. New probes this round emit additional `scouted` events as before. Carried-forward events MAY set `probes_remaining_free` to the current round's full budget (they spend nothing).

**UI contract**: `JobTab.handleEvent` accumulates every `scouted` event into `scoutedByAI` and renders the badge. No UI change required — cumulative display falls out of re-emission.

## Persisted fields (resume contract)

Per-team campaign entry (`game["game_states"][i]`, written by `campaign_to_dict`):
```json
{ "...existing campaign fields...":  "...",
  "slate_scores": { "<job>": { "<category>": 1-10 } },
  "scout_state":  { "reveals": { "<job>": { "<category>": "EXACT" } },
                    "exact_scores": { "<job>": { "<category>": 1-10 } } } }
```

Campaign game record (conductor-level, for resume re-injection):
```json
{ "...campaign record...": "...",
  "slate_scores": { "<job>": { "<category>": 1-10 } } }
```

**Guarantees**:
- `slate_scores` is identical across every team's entry and the record (campaign-global).
- On resume, locked scores are re-injected (not re-rolled); each team's `scout_state` is restored verbatim.
- Re-emitting carried-forward `scouted` events on a resumed round consumes no probe budget (idempotent).

## Negative contract (FR-013)

The engine MUST NOT emit `scouted` (or any reveal) for hidden-depth elements. `_roll_hidden_depth` output is never exposed via scouting in any round; only a job's published challenge categories are scoutable.
