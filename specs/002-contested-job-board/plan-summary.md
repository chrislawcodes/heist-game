# Plan Summary: Contested Job Board

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/board.py` | create | Pure board builder: `build_board`, `pick_order`, `tier_rank`, `affordable`, gating + wilds + affordable guard. Deterministic via seeded rng. |
| `heist/state.py` | modify | `Campaign.consumed_jobs: set[str]`; `BoardRound` (round_idx, board, pick_order, claims, contested); `RoundResult.board`/`.contested`. |
| `heist/locations/__init__.py` | modify | Reward retune (all jobs: floor ≥$1M, climb, $15-18M jackpots, 1-2 edges) + ~35 new jobs (US5). |
| `heist/locations/locations_art.csv` | modify | Art rows for new jobs. |
| `heist/runner.py` | modify | `run_one_job(..., assigned_job=None, board=None)`: run assigned job; self-select fallback over `board` (defaults to full JOBS) preserves single-heist path. |
| `heist/campaign.py` | modify | Single-AI `run_campaign`: build board, consume attempted job, pass assigned job to `run_one_job`. |
| `heist/orchestration.py` | modify | NEW conductor "job board" stage before the parallel heist stage: build shared board, pick_order, walk teams in order, resolve claims/contention, update + mirror shared consumed set, emit events, snapshot. |
| `heist/prompts.py` | modify | `_job_prompt`/`_job_slate_summary`/`_scout_prompt` operate on the round's board, not `list(JOBS)`. |
| `heist/serialize.py` | modify | Round-trip `consumed_jobs`, board fields, claims. |
| `heist/persist.py` | modify | Persist board/claims/consumed in round + campaign-level record; tolerant legacy load. |
| `heist/server.py` | modify | Broadcast `job_board`/`job_claimed`; append to events buffer (no new route). |
| `heist/web/shell.js` | modify | Consume new events; track board/claims per round. |
| `heist/web/tabs/job.html` | modify | Render the round's board + who claimed what. |
| `heist_game_design.md` | modify | Core-mechanics truth-up to 1-10 scores; contested board + reward-climb; Phase 4 built. |
| `CLAUDE.md` | modify | Locked Decisions truth-up (scores, 21 roster, phase, board slate rule). |
| `tests/test_board.py` | create | build_board determinism, gating, wilds, affordable guard, no-repeat, pick_order. |
| `tests/test_contention.py` | create | conductor-level: pick order + claim resolution + global consumption (4 teams). |
| `tests/test_locations.py` | modify/create | reward shape: floor, monotonic band medians, jackpots, edges. |
| `tests/test_serialize*.py`, `tests/test_campaign*.py`, `tests/test_content.py` | modify | board/claims/consumed round-trip; board rotation; updated reward expectations. |

## Migration Steps

None (no DB). Persistence is JSON; legacy campaign records without `consumed_jobs` load as empty set via tolerant load.

## Data Model

- **Campaign** += `consumed_jobs: set[str]`.
- **BoardRound**: `round_idx, board: list[str], pick_order: list[int], claims: dict[int,str], contested: list[dict]`.
- **RoundResult** += `board: list[str]`, `contested: bool`.

## Key Constraints

- **Two-lane**: emit board/pick-order/claims/consumed as events + persist; viewer renders only from events — *Why: replay/resume + engine/UI contract.*
- **Determinism**: board + contention are pure functions of (seed, round_idx, standings) — *Why: replay, resume, reproducible tests.*
- **Conductor owns shared consumed set**; mirror into per-AI `Campaign.consumed_jobs` each round under `gamestate.lock` — *Why: per-AI campaigns run in parallel threads.*
- **One AI job-pick call per team per round**; contention re-resolution reuses the existing incomplete-pick system fallback — *Why: bound AI cost/latency.*
- **`run_one_job` back-compat**: `assigned_job=None` self-selects over `board` (default full JOBS) — *Why: keep single-heist + existing tests working.*
- **Reward**: floor ≥ $1M; take climbs with Hard-count then tier; 4-Hard ≥ $15M (Mint top); 1-2 edges; range brackets [0.55× .. clean+best bonus] — *Why: every job worth contesting; endgame arc.*
- **Build order**: pure board.py + single-AI path + reward (US1/US2) green on CLI first, THEN conductor contention (US3) — *Why: de-risk the conductor refactor.*
