# Data Model: Phase 4 — Hidden Location Info & Scouting

All types are Python `dataclasses` in `heist/state.py` unless noted. No database; persistence is JSON via `heist/persist.py` and SSE event dicts via `heist/serialize.py`.

## Changed entities

### `Character` (existing — populate)

`skill_scores: dict[str, int]` already exists and is empty. **Populate it (public).** Buckets are derived, not stored.

| Field | Type | Notes |
|-------|------|-------|
| `skills` | `dict[str, SkillLevel]` | KEEP — derived display bucket; may be computed from scores instead of hand-set |
| `skill_scores` | `dict[str, int]` | **NEW DATA** — 1-10 per owned skill; public; drives pricing + resolution |

Validation: each score 1-10; bucket(score) must equal the published `skills` bucket (1-3 Low, 4-7 Med, 8-10 High). Locked values per spec.md *Key Entities*.

### `Job` (existing — frozen constant; leave scores empty)

`challenge_scores` stays **empty** on the constant (Decision A). `tier` normalized to `"1" | "2" | "3"` (currently strings like `"easy"`).

| Field | Type | Notes |
|-------|------|-------|
| `profile` | `dict[str, ChallengeLevel]` | public bucket shape (kept for scene structure + viability hint) |
| `challenge_scores` | `dict[str,int]` | stays empty on constant; real values live on the round (below) |
| `tier` | `str` | normalize to `"1"/"2"/"3"`; drives fog band + content ladder |
| `reward_range` | `tuple[int,int]` | public (aiming reticle) |

### `Scene` (existing — add field)

| Field | Type | Notes |
|-------|------|-------|
| `challenge_score` | `int | None` | **NEW** — true 1-10 score for the scene's challenge, stamped by `scenes.generate_scenes` from the round's rolled scores; `None` for non-challenge scenes. Resolution reads this. |

### `HeistState` (existing — add field)

| Field | Type | Notes |
|-------|------|-------|
| `challenge_scores` | `dict[str,int]` | **NEW** — the round's rolled hidden scores per category (source for `Scene.challenge_score`) |
| `scout_state` | `ScoutState` | **NEW** — what's been revealed this round + probe budget |

## New entities

### `RevealLevel` (enum, `state.py`)

```python
class RevealLevel(IntEnum):
    HIDDEN = 0   # only flavor + reward range known
    BUCKET = 1   # bucket revealed (1 probe)
    EXACT  = 2   # exact 1-10 score revealed (2nd probe)
```

### `ScoutState` (dataclass, `state.py`)

**Purpose:** single source of truth for fog this round (Decision E). Read by prompts and serialize.

| Field | Type | Notes |
|-------|------|-------|
| `reveals` | `dict[str, dict[str, RevealLevel]]` | `job_name → {challenge_category → RevealLevel}` |
| `reward_reveal` | `dict[str, int]` | `job_name → narrow-step` (0 = public range, 1 = narrowed, 2 = exact) |
| `free_probes` | `int` | `crew size + best-driver bonus (+1/+2/+3)` for the round |
| `probes_spent_free` | `int` | counts against `free_probes` |
| `probes_paid` | `int` | each beyond free cost $100k |

Methods (pure): `reveal(job, category) -> RevealLevel` (advance HIDDEN→BUCKET→EXACT, no-op at EXACT), `budget_remaining()`, `level(job, category)`.

### Free-probe budget helper (`mechanics.py`)

```python
def driver_scout_bonus(crew) -> int:  # +1/+2/+3 by best driver bucket, +0 if none
def free_probe_budget(crew) -> int:   # len(crew) + driver_scout_bonus(crew)
```

## Changed pure functions (`mechanics.py`)

| Function | Change |
|----------|--------|
| `effective_skill_score(members, skill) -> int` | NEW primary: highest score, +1 if ≥2 have the skill, cap 10 |
| `effective_skill_bucket(members, skill) -> SkillLevel` | thin wrapper → `score_to_bucket(effective_skill_score(...))` for escape + `job_is_viable` |
| `score_to_bucket(score) -> SkillLevel` | NEW: 0→NONE, 1-3→LOW, 4-7→MED, 8-10→HIGH |
| `score_floor_cost(char) -> int` | NEW: `100_000 + Σ premium(score)`; replaces `base_cost`/`expected_floor_cost` |
| `resolve_by_margin(eff_score, challenge_score) -> Outcome` | NEW: margin table (Decision C); replaces `resolve_outcome` |
| `roll_challenge_scores(profile, tier, rng) -> dict[str,int]` | NEW: per-category score from tier fog band |
| `escape_resolves(...)` | unchanged body; now fed `effective_skill_bucket(... "driver")` |

`PREMIUM = {1:0,2:0,3:0,4:25_000,5:50_000,6:100_000,7:175_000,8:325_000,9:600_000,10:1_100_000}`; `SEAT = 100_000`.

## Migrations / persistence

- `persist.py`: add a `schema_version` tag to game records. **Tolerant load:** done games replay from their stored events (outcomes already baked in) — no re-resolution. **In-flight games** persisted under the pre-Phase-4 schema are marked errored on resume rather than resumed under mismatched mechanics (rare, local).
- Round snapshot gains `challenge_scores` + serialized `ScoutState` so a mid-round crash resumes with intel intact.

## Type-shape summary

```python
@dataclass(frozen=True)
class Scene: ...; challenge_score: int | None = None

@dataclass
class ScoutState:
    reveals: dict[str, dict[str, "RevealLevel"]] = field(default_factory=dict)
    reward_reveal: dict[str, int] = field(default_factory=dict)
    free_probes: int = 0
    probes_spent_free: int = 0
    probes_paid: int = 0

@dataclass
class HeistState:
    ...
    challenge_scores: dict[str, int] = field(default_factory=dict)
    scout_state: "ScoutState" = field(default_factory=ScoutState)
```
