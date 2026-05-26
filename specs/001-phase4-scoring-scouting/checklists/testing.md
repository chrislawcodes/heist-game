# Testing Quality Checklist

**Purpose:** Validate test coverage and quality
**Feature:** [tasks.md](../tasks.md)

(No constitution — project preflight from `CLAUDE.md`.)

## Preflight (run before every push — CLAUDE.md)

- [ ] `python3 -m ruff check .` clean
- [ ] `mypy heist/ agents.py demo.py` clean
- [ ] `pytest -q` green

## Coverage of new mechanics

- [ ] `score_floor_cost` — every roster member matches the spec table to the dollar (SC-002)
- [ ] `effective_skill_score` — 1 member = their score; ≥2 = min(best+1, 10) (SC-004)
- [ ] `score_to_bucket` — boundary values 3/4, 7/8, 0
- [ ] `resolve_by_margin` — one case per band (clean/squeak/fail/caught) incl. boundaries 2, 1, 0, −3, −4
- [ ] `roll_challenge_scores` — stays within tier fog bands across many rolls (T1 Hard=8, T3 Hard∈{9,10})
- [ ] Determinism — 100 resolutions fixed by score comparison, no randomness in the contest (SC-003)

## Scouting

- [ ] Free-probe budget = crew + driver bonus for each driver tier (none/+1/+2/+3) (SC-005)
- [ ] 1st probe → bucket, 2nd → exact; probe past exact is a no-op and not charged
- [ ] Over-budget probe charges $100k; unaffordable probe is refused without side effects
- [ ] Serialize hides unscouted exact scores; reward range stays public (SC-008)

## Integration

- [ ] Stub single heist runs end-to-end on the new engine
- [ ] Stub 3-round campaign runs end-to-end, emits `scouted` events, settles rounds
- [ ] Legacy game record loads and replays without error

## Content

- [ ] 17 characters; ≥2 Medium-band hackers; new char curve-correct cost (US5)
- [ ] ≥1 edge job (high reward range over below-trend defenses) exists in the pool (SC-007)

## Quality

- [ ] New tests are deterministic (seed RNG where rolls are involved)
- [ ] Edge cases from spec.md covered (no driver, low bankroll, tie margin, legacy save)
- [ ] No test asserts on the old bucket comparison or `expected_floor_cost`
