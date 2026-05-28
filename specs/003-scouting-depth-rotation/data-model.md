# Data Model: Scouting Depth + Board Rotation

## Entities (extended; no new top-level entities)

### Entity 1: `Campaign` (extended)

**Purpose**: Holds the per-campaign state that persists across rounds.

**Storage**: JSON, serialized via `heist/serialize.py` → `state/games/<id>.json` (under the `campaign_state` key for campaign sub-games).

**Existing fields** (unchanged): `rounds_total`, `banked_loot`, `standing_crew`, `round_results`, `between_round_log`, `consumed_jobs`.

**New fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `carryover_board` | `list[str]` | `[]` | Job names that were on the prior round's board but unpicked. Length up to `BOARD_SIZE - 1` (at least one job is consumed each round in a normal multi-team round). Empty at round 0. |
| `persistent_slate_scores` | `dict[str, dict[str, int]]` | `{}` | Per-job hidden rolled challenge scores (`job_name → category → 1–10`). Rolled when a job first enters the board; carried until that job is consumed; deleted on consumption. |
| `per_ai_scout_state` | `dict[int, ScoutState]` | `{}` | Per-team persisted ScoutState. Keys are `ai_idx`. Values reset only their per-round counters at round start; `reveals` and `exact_scores` accumulate across rounds. |

**Indexes / lookups**: None (in-memory `dict`s).

**Relationships**: `carryover_board` ⊂ `set(persistent_slate_scores.keys())` should always hold; the conductor must keep them consistent (when a job is consumed, drop from `persistent_slate_scores` only if not still in the carryover).

**Validation rules**:
- After each round's settle: every name in `carryover_board` MUST be present in `persistent_slate_scores`. (Else the carryover would be revealed against missing hidden scores.)
- `per_ai_scout_state[i].free_probes` set to the flat budget at round start; `probes_spent_free` resets to 0.

---

### Entity 2: `ScoutState` (lifecycle extended; shape unchanged)

**Purpose**: A team's scouting record. Used both as per-round runtime state and as the carrier of persisted reveals.

**Storage**: Inside `Campaign.per_ai_scout_state` (new), also still passed to per-heist `HeistState` (existing).

**Existing fields** (unchanged shape; see `heist/state.py`):

| Field | Type | Description |
|-------|------|-------------|
| `reveals` | `dict[str, dict[str, RevealLevel]]` | What's revealed: `job_name → category → HIDDEN/BUCKET/EXACT`. **Persists across rounds (new).** |
| `exact_scores` | `dict[str, dict[str, int]]` | Revealed exact 1–10 scores. **Persists across rounds (new).** |
| `reward_reveal` | `dict[str, int]` | Reward narrow level (unchanged). |
| `free_probes` | `int` | Per-round budget. **Reset to 10 at round start (new flat budget).** |
| `probes_spent_free` | `int` | Per-round counter. **Reset to 0 at round start.** |
| `probes_paid` | `int` | Reserved for paid overflow (unchanged). |
| `rationale` | `str` | Last scout call's stated intent (carried for the recap; unchanged). |

**Lifecycle change**: Previously created fresh per round inside `_run_scout_turn`. Now created once per team at campaign start, persisted on `Campaign.per_ai_scout_state`. The conductor resets the per-round counters and tops up `free_probes` before each round's board stage; `reveals`/`exact_scores` accumulate.

---

### Entity 3: `RoundBoard` (logical; not a new dataclass)

**Purpose**: The composed list of ≤ `BOARD_SIZE` job names for a given round, derived each round from `carryover + replenish`.

**Storage**: Not separately stored; reconstructable each round from `Campaign.carryover_board` plus the round's fresh replenish draw (seeded by `(campaign_id, round_idx)`). The composed list is the input to `_run_scout_turn` and `pick_job_from_board`.

**Composition rule** (round R):
1. `carryover = Campaign.carryover_board` (∅ on round 0).
2. `available_pool = JOBS - Campaign.consumed_jobs - set(carryover)`.
3. `N = BOARD_SIZE - len(carryover)` (clamped to ≥ 0).
4. `new = mix_aware_replenish(available_pool, carryover, N, rng=Random((campaign_id, round_idx)))`.
5. `round_board = carryover + new` (order preserved; final length ≤ `BOARD_SIZE`).
6. For each `j in new`, roll its challenge scores and store in `Campaign.persistent_slate_scores[j]`.
7. After picks settle: set `Campaign.carryover_board = [j for j in round_board if j not in picked_this_round]`; drop picked jobs from `persistent_slate_scores`.

---

## Type definitions (Python)

```python
# heist/state.py — Campaign additions (excerpt; only the new fields shown)
@dataclass
class Campaign:
    # existing:
    rounds_total: int
    bankroll: int
    banked_loot: int
    standing_crew: list[Character] = field(default_factory=list)
    round_results: list[RoundResult] = field(default_factory=list)
    between_round_log: list[dict] = field(default_factory=list)
    consumed_jobs: set[str] = field(default_factory=set)
    # new:
    carryover_board: list[str] = field(default_factory=list)
    persistent_slate_scores: dict[str, dict[str, int]] = field(default_factory=dict)
    per_ai_scout_state: dict[int, "ScoutState"] = field(default_factory=dict)
```

`ScoutState` shape is **unchanged**; only its lifecycle and storage location change.

---

## Migrations / serialization

No DB migrations (JSON state).

**`heist/serialize.py` additions**:

`campaign_to_dict(campaign)` adds:
```python
{
    # existing keys ...
    "carryover_board": list(campaign.carryover_board),
    "persistent_slate_scores": {
        j: dict(cats) for j, cats in campaign.persistent_slate_scores.items()
    },
    "per_ai_scout_state": {
        str(i): scout_state_to_dict(ss)
        for i, ss in campaign.per_ai_scout_state.items()
    },
}
```

`campaign_from_dict(d)` adds (with defaults for backward-compat with pre-feature saves):
```python
campaign.carryover_board = list(d.get("carryover_board", []))
campaign.persistent_slate_scores = {
    j: {c: int(s) for c, s in cats.items()}
    for j, cats in d.get("persistent_slate_scores", {}).items()
}
campaign.per_ai_scout_state = {
    int(i): scout_state_from_dict(d_ss)
    for i, d_ss in d.get("per_ai_scout_state", {}).items()
}
```

**Backward-compat**: campaigns saved before this feature lack all three keys; loaders default to empty, so resume / replay still works.

**Event-stream additions** (for the UI lane):

| Event | When | Why |
|-------|------|-----|
| `job_board` (existing, payload extended) | Round start, before scouts | Add a `carryover` field (list of job names known to be carried) so the UI can highlight returning jobs. Backward-compat: field optional. |
| `scout_state_loaded` (new) | Round start, per team, before scouts | Emits the team's persisted `reveals` + `exact_scores` (the values it already had coming in). Lets the Job tab paint prior reveals **without reconstructing** from the event log. |

Both are emitted to each team's round sub-game stream (the existing per-team emit channel).

---

## Out of scope

- Paid scouting (overflow buy-in): the spec doesn't add this; `probes_paid` stays a reserved field.
- Scouting-related stats/leaderboards: out of scope.
- Visual diff for "newly-revealed-this-round" vs "carried-from-prior-round": will be addressed in Phase C if needed, but the data model already enables it (the UI knows reveal level + can compare against a prior-round snapshot if needed).
