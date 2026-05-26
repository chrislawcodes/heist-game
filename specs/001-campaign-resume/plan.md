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

### Decision 3: Persist each team's heist result so reflection resumes without re‑running the heist (REFINED — chose heist‑take checkpointing, 2026‑05‑26)

**Discovery during implementation**: The persisted record only cleanly captures (a) completed rounds (`round_results`, written after reflection) and (b) post‑hiring `standing_crew`/`banked_loot`. The heist's outcome lives only in the in‑memory `heist_states` and is **never persisted** — `settle_round` (in reflection) is the first thing that writes a round's result. Mid‑hiring snapshots are also inconsistent (banked loot is deducted only at the end of the auction). So the plan's clean four‑stage boundaries did not all exist on disk.

**Chosen** (heist‑take checkpointing): After the heist stage (post‑join), persist each team's minimal heist result — `final_take`, `heat`, `caught_member_ids`, `job_name`, `aborted`, `escape_success` — into `game_states[i].pending_heist`. After `settle_round` consumes it (reflection), clear `pending_heist`. This makes all four stage boundaries genuinely resumable:

| Persisted `current_stage` of `start_round` | Resume action |
|---|---|
| `opening_wire` / `hiring` | hiring not cleanly committed → redo the round from the top (re‑run hiring → heist → reflection). Reconstructed `camp` is pre‑hiring, so no double‑charge. |
| `heist` | hiring done; heist was in progress (its `pending_heist` not yet persisted) → re‑run heist → reflection. |
| `reflection` | heist done + `pending_heist` persisted → load `pending_heist`, run reflection/`settle_round` **without re‑running the heist**. |

**Idempotency guards**:
- **Settle‑once**: a round is settled iff its `RoundResult` is in `round_results`. `effective_start = min(len(camp.round_results))` over active teams; skip rounds `< effective_start`. If `round_results` already contains `start_round` (crash after the post‑reflection snapshot), skip the round.
- **`settle_round` needs only** `final_take`/`heat`/`caught_member_ids`/`job`/`aborted`/`escape_success` from the `HeistState`; on resume we feed it a lightweight object built from `pending_heist` (refactor `settle_round` to accept those fields, or wrap them) — no full `HeistState` reconstruction.
- **Sub‑game ids**: truncate `round_gids_per_ai[i]` / `heist_states` to `effective_start` length before re‑running a round so a re‑run heist appends one fresh sub‑game id (the partial pre‑crash sub‑game becomes a harmless orphaned record).

**Tradeoffs**: Pro — faithful resume; a crash during reflection wastes **zero** Codex calls. Con — one new persisted field (`pending_heist`) + its reconstruction; a crash *during* the heist still re‑runs that round's heist (its output genuinely wasn't saved).

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
