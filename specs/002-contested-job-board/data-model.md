# Data Model: Contested Job Board

## Entities

### Campaign (extended) — `heist/state.py`

Add a global consumed set (single-AI authoritative; mirror of conductor's shared set in multi-AI).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `consumed_jobs` | `set[str]` | `set()` | Job names attempted by any team; never re-offered. |

### BoardRound (per-round board state) — `heist/state.py`

Captures one round's contested board so it can be emitted + persisted + replayed. Stored per round (e.g. appended alongside `RoundResult`, or embedded in the round snapshot).

| Field | Type | Description |
|-------|------|-------------|
| `round_idx` | `int` | The round this board belongs to. |
| `board` | `list[str]` | The ≤8 job names shown this round. |
| `pick_order` | `list[int]` | ai_idx ordered ascending by banked loot (trailing first). |
| `claims` | `dict[int, str]` | ai_idx → claimed job name. |
| `contested` | `list[dict]` | `[{ai_idx, wanted, got}]` for teams whose first choice was taken. |

### RoundResult (extended) — `heist/state.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `board` | `list[str]` | `[]` | The board this team saw (for replay). |
| `contested` | `bool` | `False` | Whether this team lost its first choice to a lower-banked rival. |

(`scouted` already exists.)

## Pure functions — `heist/board.py`

```python
def pick_order(standings: list[tuple[int, int]]) -> list[int]:
    """standings: [(ai_idx, banked_loot)]. Returns ai_idx ascending by banked, tiebreak ai_idx."""

def tier_rank(job: Job) -> int:
    """0..3 difficulty rank from Hard-count + tier (for gating + affordable proxy)."""

def affordable(job: Job, bankroll: int) -> bool:
    """Coarse: estimated crew cost (reward proxy) <= bankroll."""

def build_board(
    pool: list[Job],
    consumed: set[str],
    round_idx: int,
    rounds_total: int,
    total_banked: int,
    *,
    size: int = 8,
    min_affordable: int = 2,
    trailing_bankroll: int = 0,
    rng: random.Random,
) -> list[str]:
    """Deterministic board: gated slots (tiers unlocked by progression) + wild slots
    (any unconsumed) + affordable-minimum guarantee. Returns job names. If fewer than
    `size` unconsumed jobs remain, returns all of them."""
```

**Determinism**: `rng` is seeded from `(campaign_seed, round_idx)` so a board is reproducible for replay/resume and tests.

## Gating model (Decision 5)

- `unlocked_max_rank(round_idx, rounds_total, total_banked)` → the highest `tier_rank` allowed in **gated** slots this round. Early rounds cap at low ranks; rank ceiling rises with round progress and total banked loot. Elite (rank 3) only unlocks in the later third / once total banked crosses a threshold.
- Gated slots: draw from `{unconsumed jobs with tier_rank ≤ ceiling}`.
- Wild slots (e.g. 2 of 8): draw from **all** unconsumed jobs (can surface a reach jackpot or off-tier surprise).
- Affordable guard: after filling, ensure ≥ `min_affordable` board jobs satisfy `affordable(job, trailing_bankroll)`; if not, swap a wild/gated slot for an affordable one.

## Persistence (Decision 7)

- Per-AI round sub-game snapshot: add `board`, `contested` (this team's view).
- Campaign-level record: add `consumed_jobs` (the shared authoritative set) and the per-round `BoardRound` (board, pick_order, claims, contested) for replay.
- `serialize.py`: `campaign_to_dict`/`campaign_from_dict` round-trip `consumed_jobs`; round serialization round-trips board fields.
