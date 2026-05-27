# Event Contracts: Contested Job Board

The engine emits these on the stream and appends them to the persisted events buffer (two-lane rule). The viewer renders board state **only** from these — it never recomputes the board or claims.

## `job_board`

Emitted once per round at the start of the board stage, after the board is built.

```json
{
  "type": "job_board",
  "campaign_id": "<id>",
  "round_idx": 3,
  "board": [
    {"name": "The Cargo Yard", "tier": "easy", "reward_range": [1500000, 4000000],
     "profile": {"electronic": "LOW", "physical": "HARD", "confrontation": "MEDIUM"}}
  ],
  "pick_order": [2, 0, 3, 1],
  "consumed_count": 6
}
```

- `board`: the ≤8 jobs shown this round (public fields only — fog from `ScoutState` still applies to challenge scores per the existing scouting contract).
- `pick_order`: ai_idx ascending by banked loot (trailing team first).
- `consumed_count`: size of the global consumed set entering this round.

## `job_claimed`

Emitted per team as the pick order resolves (in order), after the team selects.

```json
{
  "type": "job_claimed",
  "campaign_id": "<id>",
  "round_idx": 3,
  "ai_idx": 2,
  "job": "The Casino Vault",
  "contested": true,
  "wanted": "The Casino Vault",
  "got": "The Casino Vault"
}
```

- `contested`: true if ≥1 later team also wanted this job (informational) OR if this team's first choice was already taken.
- `wanted` / `got`: present when a team's first choice was taken and the system resolved it to a fallback (`wanted` != `got`).

## Round snapshot additions (persisted, not a stream event)

Per-AI round sub-game gains:
```json
{ "board": ["...job names..."], "contested": false }
```

Campaign-level record gains:
```json
{ "consumed_jobs": ["The Cargo Yard", "..."],
  "board_rounds": [ {"round_idx": 0, "board": ["..."], "pick_order": [..], "claims": {"0": "..."}, "contested": [...]} ] }
```

## Backward compatibility

- Legacy campaign records with no `consumed_jobs` load as an empty set (no consumption history) — tolerant load per `persist.py` `schema_version`.
- Existing single-heist event consumers ignore the new event types (additive).
