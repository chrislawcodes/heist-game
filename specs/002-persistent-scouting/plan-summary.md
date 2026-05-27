# Plan Summary: Persistent Scouting

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/state.py` | modify | Add `slate_scores: dict[str,dict[str,int]]` and `scout_state: ScoutState` to the `Campaign` dataclass |
| `heist/runner.py` | modify | `run_one_job`: read `campaign.slate_scores` (roll-once if empty); pre-load `campaign.scout_state` into the round's working ScoutState with fresh `free_probes`; emit carried-forward `scouted` events at round start; merge new reveals back into `campaign.scout_state` |
| `heist/orchestration.py` | modify | `run_campaign_conductor`: roll locked scores once at campaign start, store on game record, inject the SAME dict into every team `Campaign.slate_scores`; on resume re-inject from the record (roll once if legacy/absent) |
| `heist/campaign.py` | modify | `run_campaign` (CLI): single `Campaign` carries `slate_scores`/`scout_state` across the round loop (mostly automatic once on the dataclass) |
| `heist/serialize.py` | modify | `campaign_to_dict`/`campaign_from_dict`: include `slate_scores` + `scout_state` (reuse `scout_state_to_dict`/`from_dict`); `.get(...)` defaults for legacy records |
| `tests/test_scout_persistence.py` | create | locked-score stability, cross-round reveal carry, per-team isolation, resume round-trip, legacy back-compat |
| `heist/web/tabs/job.html`, `heist/web/shell.js` | (likely none) | Already render cumulative `scouted` events; verify on staging, change only if needed |

## Migration Steps

None (no DB). JSON game records read with `.get(key, default)`; legacy campaigns lazily roll locked scores on first access. No destructive migration.

## Data Model

**Campaign** (`state.py`, in-memory + JSON): gains `slate_scores` (campaign-global locked 1-10 per job/category) and `scout_state` (persistent per-team reveals + exact_scores). Serialized inside `campaign_to_dict`/`campaign_from_dict`; locked scores also mirrored on the campaign game record for resume re-injection.

## Key Constraints

- **Roll-once / campaign-global scores**: locked scores rolled a single time and shared by all teams — *Why: a job's true difficulty is one world-fact (FR-002); per-team rolls would diverge.*
- **free_probes is per-round; only reveals/exact_scores persist** — *Why: scouting more each round is the intended progression (FR-005); a known cell must cost no probe (FR-006).*
- **Engine re-emits carried-forward reveals; UI unchanged** — *Why: two-lane rule (FR-007); the per-round replay only sees its own sub-game's events.*
- **Resume must not re-roll / lose / double-count** — *Why: resume/checkpoint is load-bearing; re-injection + idempotent re-emission protect it (FR-009).*
- **Legacy campaigns roll locked scores lazily, no crash** — *Why: back-compat for in-flight campaigns (FR-010).*
- **Hidden challenges stay hidden; buckets/+1/cascade untouched** — *Why: explicit design rules (FR-011/012/013); persistent scouting is the cascade's counterweight, not a softener.*
