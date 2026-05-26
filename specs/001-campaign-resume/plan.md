# Implementation Plan: Campaign Resume

**Branch**: `feat/campaign-resume` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)

## Summary

Make `run_campaign_conductor` resumable at a **stage boundary**: on resume it rebuilds each team's in‑memory `Campaign` from the already‑persisted `game_states[i]`, restores the per‑round sub‑game id lists, and re‑enters the round loop at the persisted `current_round_idx`/`current_stage` — skipping every round and stage already completed so nothing is re‑run or double‑counted. Wire two entry points: **auto‑resume** from `recover_games()` at server startup, and a **manual** `POST /api/campaign/<id>/resume`. A persisted **`checkpoint_version`** marker distinguishes campaigns started under the new checkpointing (resumable) from pre‑existing stalls (marked `interrupted`).

## Technical Context

**Language/Version**: Python 3.14 (stdlib only — `http.server`, `threading`, `dataclasses`)
**Primary Dependencies**: none new — reuse `heist.serialize` (`campaign_to_dict`/`campaign_from_dict`, `crew_to_dict`), `heist.persist` (`save_game_record`/`load_game_records`), `heist.orchestration`
**Storage**: JSON file per game under `state/games/<id>.json` (no DB)
**Testing**: pytest (`tests/`), plus the `/ship` smoke test (stub agent end‑to‑end)
**Target Platform**: long‑running local `python -m heist serve` process (8000 prod / 8001 staging)
**Performance Goals**: resume must complete startup recovery within seconds (SC‑003); correctness over speed
**Constraints**: two‑lanes rule (engine emits events, UI only displays); engine owns deterministic mechanics; no mechanics/auction changes
**Scale/Scope**: ≤ a handful of concurrent campaigns, 3 AIs, ≤ ~10 rounds; single process

## Constitution Check

**Status**: PASS (no formal constitution; validated against CLAUDE.md governance)

- **Two‑lanes**: resume re‑emits the normal campaign events (`campaign_stage`, per‑AI heist events, `campaign_round_done`, `campaign_done`) so the war room reflects continuation without reconstructing state in the UI. ✅
- **Locked design decisions**: no change to skill levels, collaboration, resolution, bankroll, roster, or job slate. ✅
- **Worktree workflow**: all work on `feat/campaign-resume`; merge via `/ship`. ✅

## Architecture Decisions

### Decision 1: The persisted record IS the checkpoint (no parallel store)

**Chosen**: Resume reconstructs in‑memory state from the existing `game_states[i]` written by `snapshot_all()` after every stage, plus `current_round_idx`/`current_stage` written by `set_stage()`.

**Rationale**:
- `snapshot_all()` already serializes each team's full `Campaign` (`campaign_to_dict`: `standing_crew`, `banked_loot`, `round_results`, …) and the `round_game_ids`/`hiring_game_ids` lists, after each of the four stages.
- `set_stage()` already persists `current_stage` + `current_round_idx` via `update_game()`.
- So the data needed to resume already lands on disk at each stage boundary — we add reconstruction, not new persistence.

**Alternatives considered**:
- A separate per‑round checkpoint file: rejected — duplicates state already in `game_states`, risks divergence.
- Mid‑heist snapshot resume (reuse `resume_heist`): rejected for v1 — finer than the chosen stage granularity and far more coupling with the parallel‑heist stage (see Decision 3).

**Tradeoffs**: Pro — minimal new persistence, reuses tested serializers. Con — resume granularity is limited to stage boundaries (an interrupted heist re‑runs that round's heist, not the exact scene).

### Decision 2: `run_campaign_conductor(..., resume=False)` rebuilds + skips completed work

**Chosen**: Add a `resume: bool = False` parameter. When `resume=True`:
1. Rebuild `campaigns[i]` from `game_states[i]` via `campaign_from_dict` (instead of leaving them `None` until the round‑0 auction).
2. Restore `round_gids_per_ai`, `hiring_gids`, `current_round_sub_gids` from the persisted `round_game_ids`/`hiring_game_ids`.
3. Read `start_round = current_round_idx`, `start_stage = current_stage`.
4. Round loop skips rounds `< start_round` entirely (their `round_results` are already present). For `start_round`, skip the stages at or before the last completed one and resume from `start_stage`'s boundary:
   - died in `opening_wire` → redo opening_wire → hiring → heist → reflection for this round
   - died in `hiring` → redo hiring → heist → reflection (opening_wire already done; it has no economy side‑effects so re‑emitting is also acceptable, but we skip for cleanliness)
   - died in `heist` → **skip** opening_wire + hiring (crew already hired & banked already deducted in `run_rehire_auction`/`run_initial_auction`), redo heist → reflection
   - died in `reflection` → redo only reflection + `settle_round`
   - Rounds `> start_round` run normally.

**Rationale**: Stage‑boundary skipping is what makes resume idempotent (FR‑003). The economy side effects live in specific stages — hiring deducts `banked_loot` and commits crew; heist computes take; reflection/`settle_round` banks the take and removes caught crew. Re‑running a stage whose side effects already persisted would double‑count, so we must not re‑enter a completed stage.

**Idempotency guards (FR‑003/004/005)**:
- `settle_round` must run **exactly once** per round. If the crash was after `settle_round` appended the `RoundResult` but before `current_round_idx` advanced, detect it by comparing `len(camp.round_results)` to `start_round` and skip the duplicate settle.
- Sub‑game ids for completed rounds come from the restored lists; new sub‑games for the resumed/remaining rounds get fresh ids (`runtime.next_id`, already advanced by `recover_games`).

**Alternatives considered**: round‑boundary only (re‑run whole interrupted round) — simpler but re‑runs hiring → double‑charge risk; rejected per the resolved stage‑boundary decision.

### Decision 3: Interrupted parallel‑heist stage re‑runs the whole heist stage for the round

**Chosen**: If `start_stage == "heist"`, re‑run the heist stage for **all** still‑active teams in `start_round` (the existing thread‑per‑AI fan‑out), discarding any partially‑written round sub‑games for that round and opening fresh ones.

**Rationale**: Heists run as parallel daemon threads joined before reflection; mid‑stage there is no per‑team "this heist already settled" record (settle happens once, after the join, in reflection). Re‑running the heist stage for the round is safe because the round's take is only banked in `settle_round` (reflection), which has not yet run. This keeps v1 simple and correct at the cost of re‑playing in‑progress heists.

**Tradeoffs**: Pro — no need to reconcile half‑finished parallel heists or reuse `resume_heist`. Con — an almost‑finished heist is replayed (extra AI cost). Acceptable for ≤3 AIs; `resume_heist`‑based mid‑scene resume is a future enhancement.

### Decision 4: Eligibility via `checkpoint_version`; old stalls → `interrupted`

**Chosen**: The conductor stamps `game["checkpoint_version"] = 1` (in `snapshot_all`). `recover_games()` gains a campaign branch:
- `is_campaign` + `status == "running"` + `checkpoint_version >= 1` → re‑spawn `run_campaign_conductor(gid, num_rounds, resume=True)`.
- `is_campaign` + `status == "running"` + no/old `checkpoint_version` → set `status = "interrupted"` and persist (pre‑existing stalls, e.g. game 14).

**Rationale**: Implements the resolved "pre‑existing stalls are always terminal" decision deterministically without guessing whether old `game_states` are complete.

### Decision 5: Double‑conductor guard via an in‑process active set

**Chosen**: Maintain `gamestate.runtime.active_campaigns: set[int]` (campaign ids with a live conductor this process). The conductor adds its id on start and removes it in a `finally`. Manual resume refuses if the id is in the set; auto‑recover only runs at startup (set empty), so no race there.

**Rationale**: A process that just started has no live conductor threads, so a campaign marked "running" on disk but absent from `active_campaigns` is provably stalled and safe to resume. Prevents two conductors (FR‑009).

## Project Structure

Monolithic Python package `heist/`. Files this feature touches:

```
heist/
├── orchestration.py   - run_campaign_conductor: add resume= param + rebuild/skip logic;
│                         recover_games: add is_campaign branch (resume vs mark interrupted);
│                         add active_campaigns guard (add/remove around the conductor)
├── server.py          - new route POST /api/campaign/<id>/resume → _handle_resume_campaign;
│                         (recover_games call at startup already exists)
├── gamestate.py       - runtime.active_campaigns: set[int] (the guard registry)
├── serialize.py       - reuse campaign_from_dict (verify it round-trips game_states[i]); no new API expected
├── lobby.html         - "Resume" affordance on a stalled campaign row (calls the new endpoint)
└── (state/games/*.json gains checkpoint_version + possibly status="interrupted")

tests/
└── test_campaign_resume.py  - new: rebuild-from-snapshot, stage-skip idempotency,
                               recover_games campaign branch, double-conductor guard
```

**Structure Decision**: Engine changes are concentrated in `orchestration.py` (the conductor + recovery). `server.py` gets one thin route; `gamestate.py` gets the guard set; `lobby.html` gets a small affordance (the only UI change, per spec scope). No new modules.

## Risks & Mitigations

- **Re‑emitting events on resume confuses the war‑room replay** → resume emits the same event types; the war room already tolerates a live event stream. Verify the round‑reveal/standings render correctly mid‑resume.
- **`campaign_from_dict` doesn't perfectly round‑trip `game_states[i]`** (entry has extra keys like `ai_idx`, `round_game_ids`) → reconstruction must read only the campaign fields; add a focused round‑trip test.
- **Crash exactly at a stage boundary** (settle done, round not advanced) → the `len(round_results)` vs `start_round` reconciliation in Decision 2 handles it; cover with a test.
- **Manual resume double‑fires with auto‑recover** → `active_campaigns` guard (Decision 5).
