# Implementation Plan: Contested Job Board

**Branch**: `feat/phase4-scoring-scouting` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)

## Summary

Turn the static campaign slate into a rotating, fought-over board. A pure, deterministic **board module** builds an 8-job board from `pool − consumed` with progression gating + wild slots. The **conductor** (`orchestration.py`) gains a new **job-board stage** before the parallel heist stage: it builds the shared board, orders teams by ascending banked loot, walks them through pick/scout/claim, resolves contention (lower-banked wins, loser falls back), and records the global consumed set — then each team's `run_one_job` runs its **assigned** job. The single-AI CLI path (`run_campaign`) uses the same board module with no contention. Reward is re-tuned across an expanded ~50-job pool so take climbs with difficulty.

## Technical Context

**Language/Version**: Python 3.11 (stdlib only — dataclasses, http.server, threading).
**Primary Dependencies**: none new. Existing: `heist.mechanics` (scores/tiers), `random.Random` (seeded determinism).
**Storage**: JSON game records under `state/games/` via `heist/persist.py`; per-AI sub-games + a campaign-level record (conductor-owned).
**Testing**: `pytest`; `ruff`; `mypy heist/ agents.py demo.py`.
**Target Platform**: local `http.server`; CLI (`python -m heist run-campaign --agent stub`).
**Performance Goals**: board build is O(pool) per round, negligible. No new network calls beyond the existing one job-pick AI call per team per round.
**Constraints**: deterministic given seed + standings (replay/resume); two-lane rule (engine emits, UI renders); one job-pick AI call per team per round (no extra round-trips for contention — reuse the system fallback).
**Scale/Scope**: ≤4 teams, 10 rounds, ~50-job pool (~40 consumed worst case + buffer).

## Constitution Check (CLAUDE.md as governance)

**Status: PASS**

- **Two-lane rule** — the board, pick order, per-team claims, contested losses, and the running consumed set are all emitted as events and persisted in the round snapshot; the viewer renders only from events (Decision 7). No client-side board reconstruction.
- **System owns deterministic mechanics** — board composition, gating, wild draw, pick order, and contention resolution are deterministic functions of (seed, round_idx, standings). The AI only *chooses* among offered board jobs (Decision 1, 4).
- **Locked decisions** — encoded verbatim from spec; not re-opened.
- **Files that conflict often** — this touches `runner.py`, `prompts.py`, `serialize.py`, `persist.py`, `server.py`, `shell.js`. Implementation is sequenced (tasks.md) so these are edited serially, never in parallel.

## Architecture Decisions

### Decision 1: A pure `heist/board.py` module is the single source of board logic

**Chosen**: New module `heist/board.py` with pure functions:
- `build_board(pool, consumed, round_idx, rounds_total, total_banked, *, size=8, rng) -> list[str]` — returns the round's board (job names), applying progression gating + wild slots + affordable-minimum guard.
- `pick_order(standings) -> list[int]` — ai_idx sorted by ascending banked loot, tiebreak ai_idx.
- `tier_rank(job) -> int` and `affordable(job, bankroll) -> bool` heuristics (difficulty/reward proxy).

**Rationale**: both the multi-AI conductor and the single-AI `run_campaign` need identical board math; a pure module keeps it testable in isolation (no threads, no AI) and keeps determinism auditable. Mirrors the existing pure `heist/scouting.py`.

**Alternatives**: putting board logic in `runner.py` (couples it to the heist loop, untestable across teams) — rejected.

**Tradeoffs**: +1 module; clean and unit-testable.

### Decision 2: Global consumed set — conductor-owned for multiplayer, `Campaign`-owned for single-AI

**Chosen**: Add `Campaign.consumed_jobs: set[str]` (single-AI path). For the conductor, the **shared** consumed set lives in the campaign-level record (conductor state), and is mirrored into each per-AI `Campaign.consumed_jobs` at the start of the board stage so `run_one_job`/serialize see a consistent view.

**Rationale**: per-AI `Campaign`s run in parallel threads; the authoritative shared set must be conductor-owned and snapshotted at the campaign level. Single-AI has exactly one campaign, so its own set suffices.

**Tradeoffs**: a small sync step (conductor → per-AI) each round; acceptable, happens under `gamestate.lock` in the serial board stage.

### Decision 3: Split job selection out of `run_one_job` into a board stage

**Chosen**: Today `run_one_job` does scout + `_pick_job` internally over `list(JOBS)`. Refactor so:
- The **board stage** (conductor; and an inline equivalent in single-AI `run_campaign`) builds the board, runs scouting + the job-pick AI call **per team in pick order**, resolves claims, and assigns each team a job.
- `run_one_job` gains an `assigned_job: Job | None` (and `board: list[Job]`) parameter; when assigned, it skips internal job selection and runs that job's scenes. Back-compat: `assigned_job=None` falls back to today's behavior over the passed `board` (defaulting to full `JOBS` if no board), so existing single-heist tests still pass.

**Rationale**: contention can only be resolved where all teams are visible — above the parallel heist threads. Keeping `run_one_job` able to self-select (over a board) preserves the single-AI and unit-test paths.

**Tradeoffs**: moderate refactor of `runner.py` signatures + `orchestration.py` stage order; mitigated by the `assigned_job=None` fallback.

### Decision 4: Contention = trailing-team-first sequential claim, reusing the system fallback

**Chosen**: `pick_order` = ascending banked loot. Walk teams in order; each team scouts the board and makes its job-pick AI call; if its chosen job is already claimed this round, the **existing incomplete-pick fallback** (system picks an affordable available board job) resolves it — no second AI round-trip. Each claimed job is removed from the remaining board and added to consumed.

**Rationale**: anti-snowball (locked); reuses proven fallback logic; bounds AI calls to one per team per round.

**Tradeoffs**: a team that named only a taken job gets a system-chosen fallback rather than re-deliberating — acceptable and matches today's incomplete-pick behavior.

### Decision 5: Board composition — gating + wilds + affordable guard (deterministic)

**Chosen**: `build_board` fills 8 slots = `gated_slots` (skew to tiers unlocked by progression: a function of `round_idx`/`rounds_total` and `total_banked`) + `wild_slots` (drawn from the whole unconsumed pool) + an **affordable-minimum** guarantee (≥ N jobs whose reward proxy ≤ trailing bankroll). All draws use the seeded `rng` derived from (campaign seed, round_idx) so the board is reproducible.

**Rationale**: realizes the locked "global progression gating + surprises + never starved." Determinism is required for replay/resume and tests.

**Tradeoffs**: gating heuristic is coarse (tier-by-progress), not a crew-cost solve — documented as an assumption.

### Decision 6: Reward retune is content-level, formula-guided, hand-set

**Chosen**: In `heist/locations/__init__.py`, re-set every job's `scene_loot` (the real take) and `reward_range` per the spec's climb model: floor ≥ $1M, take trends up with Hard-count then tier, 4-Hard jobs ≥ $15M (Mint highest), 1–2 deliberate edges; `reward_range ≈ [0.55× take .. clean take + best hidden-depth bonus]`; `reward_amounts` (bonus pool) scaled so the range top is reachable. Keep the per-category `scene_loot` split.

**Rationale**: 15→~50 curated jobs; edges are intentional deviations a generator would fight. A documented formula keeps future jobs consistent.

**Tradeoffs**: hand-set values need a test that asserts the *shape* (monotonic band medians, floor, jackpots) rather than exact numbers.

### Decision 7: Events, serialize, persistence (two-lane)

**Chosen**: New events emitted in the board stage:
- `job_board` — the round's 8 jobs (names + public summaries) + pick order + round_idx.
- `job_claimed` — `{ai_idx, job, contested: bool, lost_choice?: str}` per team.
- `board_consumed` — the updated consumed list (or fold into round snapshot).
Persist `board`, `pick_order`, `claims`, `consumed_jobs` in the round snapshot (per-AI round sub-game) and the shared consumed set in the campaign-level record. `serialize.py` round-trips them; `server.py` broadcasts the new events and appends to the events buffer.

**Rationale**: replay/resume fidelity + two-lane compliance.

**Tradeoffs**: snapshot schema grows; covered by a serialize round-trip test + a resume test.

### Decision 8: Pool expansion to ~50 jobs

**Chosen**: Add ~35 jobs to `heist/locations/__init__.py`, weighted easy/medium, each with full content (flavor, profile, tier, `scene_loot`, `reward_range`, `reward_amounts`, `hidden_depth`) and a `locations_art.csv` row. Reward per Decision 6.

**Rationale**: 4 teams × 10 rounds consumes ~40; ~50 keeps boards full with buffer + variety.

**Tradeoffs**: large content task; gated behind US5 so the mechanic ships first on the current 15.

## Project Structure

Monolithic Python package `heist/`. Files this feature creates/changes:

```
heist/
├── board.py              - NEW. Pure board builder, pick_order, gating/wild/affordable helpers.
├── state.py              - Campaign.consumed_jobs; per-round board/claims fields on RoundResult or a new BoardRound.
├── locations/__init__.py - Reward retune (all jobs) + ~35 new jobs.
├── locations/locations_art.csv - art rows for new jobs.
├── runner.py             - run_one_job(assigned_job, board); split selection out; keep self-select fallback.
├── campaign.py           - single-AI run_campaign: build board, consume, pass assigned job.
├── orchestration.py      - NEW conductor "job board" stage before heist; shared consumed set; pick-order claim loop.
├── prompts.py            - _job_prompt/_job_slate_summary/_scout_prompt operate on the board, not list(JOBS).
├── serialize.py          - round-trip board/claims/consumed.
├── persist.py            - persist board/claims/consumed in round + campaign records.
├── server.py             - broadcast job_board/job_claimed events; append to events buffer.
├── web/shell.js          - consume new events; track board/claims per round.
├── web/tabs/job.html     - render the round's board + who claimed what.
heist_game_design.md      - core-mechanics truth-up + contested board + reward-climb; mark Phase 4 built.
CLAUDE.md                 - Locked Decisions truth-up (scores, 21 roster, phase, board slate rule).
tests/
├── test_board.py         - NEW. build_board determinism, gating, wilds, affordable guard, no-repeat.
├── test_contention.py    - NEW. pick order + claim resolution + global consumption (conductor-level harness).
├── test_locations.py     - reward shape: floor, monotonic band medians, jackpots, edges.
├── test_serialize*.py    - board/claims/consumed round-trip.
└── (existing campaign/runner/content tests updated for board + reward)
```

**Structure Decision**: the pure `board.py` is the shared core; the conductor owns cross-team contention + the shared consumed set; `run_one_job` becomes job-agnostic (runs an assigned job). This is the minimal seam that supports both the single-AI CLI path and the multi-AI conductor without duplicating board math.

## Risks

- **Conductor refactor** (stage insertion + moving selection above parallel heists) is the highest-risk change; mitigated by building the pure board module + single-AI path first (US1/US2 green on CLI), then the conductor stage (US3).
- **Resume fidelity**: the shared consumed set must be reconstructable on resume; covered by persisting it at the campaign level + a resume test.
- **Test reachability of 4-team contention**: add a lightweight conductor-level test harness (or a multi-AI helper) rather than relying on the server; SC-001 verified there.
