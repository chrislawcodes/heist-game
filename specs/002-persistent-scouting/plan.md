# Implementation Plan: Persistent Scouting in Campaigns

**Branch**: `feat/scout-persistence` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)

## Summary

Lock each job's hidden 1-10 challenge scores once per campaign (campaign-global) and carry each team's scouted reveals forward across rounds (per-team), so a location scouted once stays known for the rest of the campaign. The engine re-emits a team's known cells at the start of each round so the existing replay viewer shows cumulative intel. All new state serializes through the existing campaign save format and survives resume.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: stdlib only (`random`, `dataclasses`); no new deps
**Storage**: JSON game records under `state/games/*.json` (no DB). Campaign state persisted via `heist/persist.save_game_record`; per-team campaign objects via `campaign_to_dict`/`campaign_from_dict`.
**Testing**: pytest (216 tests today); add unit tests under `tests/`
**Target Platform**: local HTTP server (`python -m heist serve`)
**Performance Goals**: N/A (turn-based, single-process); correctness-driven
**Constraints**: must not break campaign resume/checkpoint (`checkpoint_version`, `game_states`); must not change buckets / +1 collaboration / heat cascade (FR-011); scouting locations-only, hidden challenges stay hidden (FR-012, FR-013)
**Scale/Scope**: campaigns of 1-6 teams × up to 20 rounds; ~15 jobs × 4 categories

## Constitution Check

**Status**: SKIPPED — no constitution file found (`CONSTITUTION.md`, `docs/constitution.md`, `.specify/memory/constitution.md` all absent).

Project guardrails from `CLAUDE.md` and the spec are treated as hard constraints instead: locked design decisions (buckets, +1 collaboration, steep heat cascade) are untouched; the two-lane rule (engine emits all events; UI only displays) drives Decision 3.

## Architecture Decisions

### Decision 1: Where locked scores live

**Chosen**: Add `slate_scores: dict[str, dict[str, int]]` to the `Campaign` dataclass ([state.py:210](../../heist/state.py)). `run_one_job` reads `campaign.slate_scores`; if empty it rolls once via `roll_slate_scores` and stores it on the campaign (covers the CLI `run_campaign` path and legacy back-compat). In the **multi-team conductor**, the scores are rolled **once at campaign start** and the *same* dict is injected into every team's `Campaign.slate_scores`, and also stored on the campaign game record so resume can re-inject it.

**Rationale**:
- A job's true difficulty is a property of the world, identical for all teams (FR-002) → must be rolled once at the campaign level, not per-team.
- Putting the field on `Campaign` gives `run_one_job` one uniform read path for both the CLI loop and the conductor.
- Storing on the game record (conductor) makes it the durable, resume-safe source of truth that's re-injected into rebuilt per-team Campaigns.

**Alternatives considered**:
- *Re-derive from a fixed seed each round*: rejected — fragile (any change to roll order drifts scores); storing the dict is explicit and safe (spec Assumption).
- *Store only on the game record, not on Campaign*: rejected — the CLI `run_campaign` path has no game record; the `Campaign` field unifies both.

**Tradeoffs**: Pros: one read path, resume-safe, deterministic-by-storage. Cons: the value is duplicated (game record + each team's Campaign), so the conductor must keep them consistent on injection — acceptable since it's set once.

### Decision 2: Per-team persistent scout memory

**Chosen**: Add `scout_state: ScoutState` to the `Campaign` dataclass, holding the **persistent** portion (`reveals` + `exact_scores`). Each round `run_one_job`: (a) builds the round's working `ScoutState` pre-loaded from `campaign.scout_state` but with a **fresh per-round `free_probes`** budget; (b) runs the scout turn (new probes); (c) merges newly revealed cells back into `campaign.scout_state`. Serialized via the existing `scout_state_to_dict`/`scout_state_from_dict` inside `campaign_to_dict`/`campaign_from_dict`.

**Rationale**:
- The conductor already persists each team via `campaign_to_dict(camp)` into `game_states[i]` ([orchestration.py:668](../../heist/orchestration.py)); adding the field + its serialization makes per-team memory persist for free.
- `free_probes` stays per-round (FR-005), so only `reveals`/`exact_scores` carry forward.
- `apply_probes` already no-ops a cell already at `EXACT` ([scouting.py:46](../../heist/scouting.py)), so a known cell costs no probe across rounds (FR-006) once the prior reveals are pre-loaded.

**Alternatives considered**:
- *Persist the whole ScoutState including `free_probes`/`probes_spent`*: rejected — budget must reset per round.
- *Store reveals on the game record like locked scores*: rejected — reveals are per-team; the per-team Campaign is the right home.

**Tradeoffs**: Pros: reuses existing serialization, per-team isolation is automatic. Cons: must separate "persistent" (reveals/exact_scores) from "per-round" (probe budget) when constructing the round's working state — handled in `run_one_job`.

### Decision 3: Re-emit carried-forward reveals each round (two-lane rule)

**Chosen**: At the start of each round, after pre-loading `campaign.scout_state`, `run_one_job` emits one `scouted` event per already-known cell (before the scout turn). The existing `JobTab` accumulates `scouted` events into `scoutedByAI` and renders badges, so cumulative intel appears with **no UI change**.

**Rationale**: The engine owns the event stream (FR-007); the per-round replay only sees that round's sub-game events, so prior reveals must be re-emitted into the new round's stream. The replay UI built earlier already consumes `scouted` events — re-emission is sufficient.

**Alternatives considered**:
- *Have the browser fetch prior rounds' scouted cells*: rejected — violates the two-lane rule; UI must not reconstruct state.

**Tradeoffs**: Pros: zero UI change, clean lane separation. Cons: the round's event log carries a few extra `scouted` events at the top — acceptable and self-documenting.

### Decision 4: Resume + back-compat

**Chosen**:
- **Locked scores**: persisted on the campaign game record; on resume, re-injected into each rebuilt team `Campaign.slate_scores`. If absent (campaign created before this feature), roll once and persist (FR-010).
- **Scout memory**: serialized per team in `game_states[i]` via `campaign_to_dict`; `campaign_from_dict` restores it on resume.
- **Idempotency**: re-emitting carried-forward `scouted` events on a resumed round is safe — they only re-assert known cells; `free_probes` is freshly granted per round, so no probe/loot double-count (FR-009).

**Rationale**: Mirrors the existing checkpoint model (Decision 3/Option B in the conductor) — minimal in-memory state, everything reconstructable from the persisted record.

**Tradeoffs**: Pros: leans on the proven resume path. Cons: requires a careful read of `run_campaign_conductor`'s resume reconstruction to inject locked scores at the right point — flagged as the highest-risk task.

## Project Structure

### Monolithic Python package (`heist/`)

```
heist/
├── state.py          - MODIFY: add `slate_scores` + `scout_state` to Campaign dataclass
├── runner.py         - MODIFY: run_one_job uses campaign.slate_scores (roll-once),
│                       pre-loads + re-emits + merges persistent scout reveals
├── orchestration.py  - MODIFY: roll locked scores once at campaign start, inject into
│                       every team Campaign + persist on game record; resume re-injection
├── campaign.py       - MODIFY: run_campaign (CLI) carries slate_scores/scout_state on the
│                       single Campaign across its loop; settle_round unchanged in intent
├── serialize.py      - MODIFY: campaign_to_dict/from_dict include slate_scores + scout_state
├── scouting.py        - (likely unchanged) apply_probes already no-ops known cells
└── web/
    ├── tabs/job.html - (no change expected) already renders scouted events cumulatively
    └── shell.js      - (no change expected) already routes scouted events to JobTab
tests/
└── test_scout_persistence.py - NEW: locked-score stability, cross-round reveal carry,
                                 per-team isolation, resume round-trip, legacy back-compat
```

**Structure Decision**: Pure engine + serialization change in `heist/`. The replay UI built in the prior scouting work already handles cumulative `scouted` events, so no frontend change is expected — the plan treats any UI tweak as contingent and verified on staging, not assumed.

## Risk & Sequencing

- **Highest risk**: Decision 4 resume re-injection in `run_campaign_conductor`. Sequence it as its own slice with a resume round-trip test before declaring done.
- **MVP (P1)**: Decisions 1 + 2 + 3 — locked scores, persistent per-team reveals, re-emission. Verifiable end-to-end via a stub campaign on staging.
- **Then (P2)**: Decision 4 — resume + legacy back-compat hardening.
