# Data Model: Premade Crews

## Entities

### Entity 1: Premade Crew

**Purpose:** A reusable AI-competitor profile the player can save once and drop into any campaign or Quick Test.

**Storage:** `state/crews.json` (under `HEIST_STATE_DIR`) — a single JSON **array** of crew objects, written atomically via `persist._atomic_write` and read via `persist._safe_load`. (Note: `_atomic_write` currently types its payload as `dict`; the crews store wraps the list as `{"crews": [...]}` to stay compatible with that signature and to leave room for future top-level metadata.)

**Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | string | required, server-assigned, unique | Stable identifier for load/delete (e.g. `uuid4().hex`). |
| `name` | string | required, non-empty (trimmed) | Player-facing label; **not** required to be unique. |
| `agent` | string | required; one of `stub` / `codex` / `codex-mini` / `gemini` | Which backend runs this crew. |
| `prompt` | string | required, non-empty (trimmed) | The assembled (and possibly hand-edited) strategy prompt. |
| `wizard` | object | optional | Snapshot of the wizard selections so the crew can be reopened/edited. |
| `created_at` | number | server-assigned (epoch seconds) | For ordering/display. |

**`wizard` sub-shape (optional):**

| Field | Type | Values |
|-------|------|--------|
| `risk` | string | `low` / `mid` / `high` |
| `budget` | string | `bargain` / `balanced` / `stars` |
| `scouting` | string | `heavy` / `targeted` / `skip` |
| `bonus` | string | `always` / `smart` / `never` |
| `fail` | string | `push` / `abort` |
| `overrides` | object | `{ job, crew, scouting, decisions }` free-text override strings (any may be empty) |

**Relationships:** none (standalone). A crew is *copied by value* into a campaign's `ais_cfg` at launch (`{name, prompt, agent}`); the campaign does not reference the crew `id`, so deleting a crew never affects a running/finished campaign.

**Validation Rules:**
- `name` and `prompt` must be non-empty after trimming, else the save endpoint returns 400.
- `agent` defaults to `stub` if missing/blank (consistent with `_handle_new_campaign` normalization).
- Unknown/extra fields on input are ignored (only the known fields are persisted).
- On load, any entry missing `id`/`name`/`prompt` is skipped (defensive), and a non-list / unparseable file yields `[]`.

## On-disk shape

```json
{
  "crews": [
    {
      "id": "9f2c1a7b8e4d4f0a",
      "name": "The Operators",
      "agent": "codex-mini",
      "prompt": "We are professionals. Run a quiet, surgical heist...",
      "wizard": {
        "risk": "low", "budget": "balanced", "scouting": "targeted",
        "bonus": "never", "fail": "abort",
        "overrides": { "job": "", "crew": "", "scouting": "", "decisions": "" }
      },
      "created_at": 1748300000
    }
  ]
}
```

## Migrations

None (new file; absent file == empty list). No schema changes to existing game records.

## Python helpers (in `heist/persist.py`)

```python
def _crews_path() -> Path:                  # _state_dir() / "crews.json"
def load_crews() -> list[dict]:             # _safe_load → payload.get("crews", []); [] on missing/corrupt
def save_crews(crews: list[dict]) -> None:  # _atomic_write(_crews_path(), {"crews": crews})
def add_crew(crew: dict) -> dict:           # assign id+created_at, append, save, return stored crew
def delete_crew(crew_id: str) -> bool:      # filter by id, save, return whether something was removed
```
