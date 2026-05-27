# Data Model: Persistent Scouting in Campaigns

No database. State lives in Python dataclasses serialized to JSON game records. This feature extends two existing shapes.

## Entities

### Entity 1: Campaign (extended)

**Purpose**: Per-team campaign state that already carries crew/loot/round results across rounds. Gains the two persistent scouting fields.

**Location**: `heist/state.py` (`@dataclass class Campaign`)

**New fields**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slate_scores` | `dict[str, dict[str, int]]` | `{}` (empty) | Locked hidden 1-10 challenge scores: `{job_name → {category → score}}`. Rolled once; reused every round. Campaign-global (same dict injected into every team in the conductor). Empty ⇒ "not yet rolled" (roll on first use). |
| `scout_state` | `ScoutState` | `field(default_factory=ScoutState)` | Persistent per-team scouting memory. Only `reveals` + `exact_scores` are meaningful here; `free_probes`/`probes_spent_*` are per-round and not carried. |

**Validation / invariants**:
- `slate_scores`, once non-empty, is never re-rolled for the life of the campaign.
- A `(job, category)` present in any team's `scout_state.exact_scores` MUST equal `slate_scores[job][category]`.

### Entity 2: ScoutState (unchanged shape, new lifecycle)

**Location**: `heist/state.py` (already exists). No field changes.

**Lifecycle change**: today it is created fresh per round inside `run_one_job`. Now the **persistent** copy lives on `Campaign.scout_state`; each round a **working** copy is built from it with a fresh `free_probes`, and newly revealed cells are merged back.

## Serialization

Reuses existing helpers in `heist/serialize.py`:
- `scout_state_to_dict` / `scout_state_from_dict` (already serialize `reveals` + `exact_scores`).

**`campaign_to_dict` (MODIFY)** — add:
```python
"slate_scores": {j: dict(cats) for j, cats in campaign.slate_scores.items()},
"scout_state": scout_state_to_dict(campaign.scout_state),
```

**`campaign_from_dict` (MODIFY)** — add (with safe defaults for legacy records):
```python
slate_scores={j: {c: int(s) for c, s in cats.items()}
              for j, cats in d.get("slate_scores", {}).items()},
scout_state=scout_state_from_dict(d.get("scout_state")),
```

**Game record (conductor)** — also store the campaign-global locked scores at the record level so resume can re-inject before per-team Campaigns exist:
```python
game["slate_scores"] = {j: dict(cats) for j, cats in locked.items()}
```

## Back-compat / "migration"

No schema migration step — JSON records are read with `.get(..., default)`. A campaign persisted before this feature simply has no `slate_scores`/`scout_state` keys:
- `campaign_from_dict` yields empty `slate_scores` (→ rolled once on first use) and an empty `ScoutState`.
- The conductor, on resume, rolls + persists locked scores if the record lacks them.

This satisfies FR-010 with zero destructive migration.
