# Plan Summary: Scouting Depth + Board Rotation

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/orchestration.py` | modify | Conductor board stage: parallel scouts via ThreadPoolExecutor, then sort-then-pick. Wire carryover + persistence. |
| `heist/board.py` | modify | `pick_order` accepts `(ai_idx, probes_spent, banked_loot)` tuples; add a `replenish_mix_aware(...)` helper for new-draw weighting. |
| `heist/state.py` | modify | Add 3 fields to `Campaign`: `carryover_board`, `persistent_slate_scores`, `per_ai_scout_state`. ScoutState shape unchanged. |
| `heist/mechanics.py` | modify | `free_probe_budget()` → flat 10 (drop crew_size + driver_bonus formula). |
| `heist/scouting.py` | modify | Use the persisted `ScoutState` from Campaign; reset per-round counters at round start. |
| `heist/serialize.py` | modify | `campaign_to_dict` / `campaign_from_dict` round-trip the 3 new Campaign fields (with empty defaults for back-compat). |
| `heist/prompts.py` | modify | `_TRADECRAFT` updates: 10-probe budget, least-probes-first pick order with bankroll tiebreak, board carryover, persistent reveals. |
| `heist/web/tabs/job.html` | modify | Phase C: render persisted reveals on board cards (use the same renderer; subtle marker for "scouted prior round" optional). |
| `tests/test_board.py` | modify | Add `pick_order` tests on `(ai_idx, probes, bankroll)` tuples; carryover + mix-aware replenish tests. |
| `tests/test_scouting.py` | modify | Flat-10 budget; persisted `reveals`/`exact_scores` across rounds. |
| `tests/test_campaign.py` | modify | End-to-end carryover + persistence over a stub 2-round campaign. |
| `tests/test_orchestration.py` | create | New: parallel scout fan-out timing test using a mocked slow scout-turn; per-team error containment. |

## Migration Steps

No SQL — JSON state only. Backward-compat on load:

1. `campaign_from_dict` defaults the 3 new fields to empty (`[]`, `{}`, `{}`) when keys absent — pre-feature saved campaigns load and play continues with the new rules from the next round.
2. No data backfill needed: persistence accumulates from the next live round forward.

## Data Model

- **`Campaign`** (`heist/state.py`) — extended:
  - `carryover_board: list[str]` (unpicked job names from the prior round)
  - `persistent_slate_scores: dict[str, dict[str, int]]` (per-job hidden 1–10 scores, sticky until the job is consumed)
  - `per_ai_scout_state: dict[int, ScoutState]` (ai_idx → persisted ScoutState; `reveals` and `exact_scores` accumulate across rounds; counters reset per round)
- **`ScoutState`** — shape unchanged; lifecycle lifted from per-round to per-campaign.
- **No new entities.** `RoundBoard` is derived each round from `carryover + replenish` and is not separately stored.

## Key Constraints

- **Parallel scouts only — picks stay sequential.** Picks need contention resolution against a shared remaining-jobs set; sequential walk is the only correct way. *Why: two teams can't safely pick "the same job" in parallel — the pick order and contention rule depend on a serial walk.*
- **Carried-over jobs keep their rolled hidden scores.** A job's `persistent_slate_scores[j]` is rolled once (when first drawn) and reused until consumption. *Why: persisted reveals (US5) would lie if the underlying number changed under them — a "scouted HARD" badge must still mean HARD next round.*
- **Drop the `crew_size + driver_bonus` formula entirely.** Flat 10 probes per team. *Why: making the scouting axis a player-choice axis, not a crew-composition consequence; also keeps budget stable if crew shrinks.*
- **Banked-loot stays as the tiebreak in pick order.** Probes_spent ascending → banked_loot ascending → ai_idx ascending. *Why: preserves a soft anti-snowball among teams that scouted identically, without overriding the new strategic axis.*
- **`build_board`'s campaign-progress + wild gating is layered under the mix-aware draw.** The mix-aware replenisher draws from `build_board`'s already-gated candidate pool, then biases weights. *Why: don't fight the existing tier/progress curve; mix-balancing is a tweak, not a replacement.*
- **`job_board` event stays the same shape (carryover field is additive)**, and the `#84` emit timing (before scouts) is preserved. *Why: don't break the Job tab's board fallback or the recently-shipped fix that made the tab show 8 jobs during scouting.*
- **`pick_order` remains a pure function.** It takes inputs and returns an order; no shared state. *Why: easy unit testing; lets the conductor inject any scoring it wants without coupling.*
- **MVP-first staging gate between phases.** Phase A (US1/2/3) ships and is reviewed on staging before Phase B begins; same between B and C. *Why: the cascade re-tunes are observable in playtest; we want each layer's effect isolated before adding the next.*
