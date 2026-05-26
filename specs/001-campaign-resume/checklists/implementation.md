# Implementation Quality Checklist

**Purpose**: Validate code quality during implementation
**Feature**: [tasks.md](../tasks.md)

(No formal constitution; references CLAUDE.md governance.)

## Two-Lanes (CLAUDE.md)
- [ ] Resume re-emits existing campaign events; no game state reconstructed in the UI
- [ ] No new presentation/pacing logic added to the engine path

## Idempotency / Correctness
- [ ] A completed stage is never re-run on resume (hiring not re-charged; take not re-banked)
- [ ] `settle_round` runs exactly once per round (reconciled via `len(round_results)` vs `current_round_idx`)
- [ ] Sub-game ids for completed rounds reused from persisted lists; new ids fresh (no duplicates)
- [ ] Double-conductor guard (`runtime.active_campaigns`) honored on both auto + manual paths
- [ ] Pre-existing stalls (no `checkpoint_version`) → `interrupted`, never force-resumed

## Code Quality (best practices)
- [ ] Consistent with existing `orchestration.py` style (closures, `gamestate.lock`, `save_game_record`)
- [ ] Reuses `campaign_from_dict`/`campaign_to_dict` rather than a parallel checkpoint store
- [ ] No hardcoded round/stage assumptions beyond the documented four stages
- [ ] No `# type: ignore` / `# noqa` / swallowed exceptions (CLAUDE.md preflight rule)
- [ ] Changes confined to the files in plan-summary.md "Files In Scope"
