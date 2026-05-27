# Implementation Quality Checklist

**Purpose**: Validate code quality during implementation
**Feature**: [tasks.md](../tasks.md)

(No constitution file — best-practices + project conventions from `CLAUDE.md`.)

## Code Quality
- [ ] Consistent with existing `heist/` style (dataclasses, type hints, structured `log.*`)
- [ ] `run_one_job` reads locked scores from `campaign.slate_scores` — no stray `roll_slate_scores` re-roll left in the per-round path
- [ ] Persistent vs per-round state cleanly separated: only `reveals`/`exact_scores` carry forward; `free_probes` resets each round
- [ ] No hardcoded job/category names; iterate the slate and `ScoutState` generically
- [ ] No new dependencies

## Two-lane discipline (project core rule)
- [ ] Carried-forward reveals are EMITTED by the engine each round; the browser/JobTab is NOT taught to reconstruct prior rounds
- [ ] No display/pacing logic added to the compute path

## Serialization & resume safety
- [ ] `campaign_to_dict`/`campaign_from_dict` round-trip `slate_scores` + `scout_state` losslessly
- [ ] Legacy records (missing keys) load via `.get(..., default)` without error
- [ ] Resume re-injects locked scores (never re-rolls) and restores per-team reveals
- [ ] Re-emitting carried-forward `scouted` on a resumed round spends no probe / banks no loot twice

## Guardrails
- [ ] Buckets, +1 collaboration, escape/cascade math untouched
- [ ] `_roll_hidden_depth` output never exposed via scouting (FR-013)
- [ ] Single-job `run_heist` path behavior unchanged
