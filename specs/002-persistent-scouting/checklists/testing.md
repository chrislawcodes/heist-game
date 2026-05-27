# Testing Quality Checklist

**Purpose**: Validate test coverage and quality
**Feature**: [tasks.md](../tasks.md)

(No constitution — project preflight from `CLAUDE.md` is the gate.)

## Preflight (must pass before push)
- [ ] `python3 -m ruff check .` clean
- [ ] `mypy heist/ agents.py demo.py` clean (no new `# type: ignore`)
- [ ] `pytest -q` green (existing 216 + new)

## Coverage for this feature
- [ ] US1: a job's challenge scores identical across ≥2 rounds (SC-001)
- [ ] US1: scouted value == locked value; all teams share identical locked scores
- [ ] US2: a cell scouted in round 0 is known in round 1 with zero probes spent (SC-002, SC-004)
- [ ] US2: re-probing a known cell is a no-op (no budget consumed)
- [ ] US2: per-team isolation — team B never sees team A's reveals (SC-005)
- [ ] US2: carried-forward `scouted` events emitted at round start
- [ ] US3: resume preserves locked scores (not re-rolled) + 100% of reveals (SC-003)
- [ ] US3: legacy record with no `slate_scores` initializes once and continues
- [ ] US3: no probe/loot double-count on a resumed round

## Manual / staging
- [ ] quickstart.md US1–US3 walked on a restarted server
- [ ] Replay shows cumulative badges across rounds; hidden depth NOT revealed (FR-013)

## Test quality
- [ ] Tests assert behavior, not implementation details
- [ ] Resume tests exercise a real `to_dict → from_dict` round trip
- [ ] Edge cases covered (no-driver/zero-probe round, re-offered job)
