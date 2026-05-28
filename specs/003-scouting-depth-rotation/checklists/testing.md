# Testing Quality Checklist

**Purpose**: Validate test coverage and pre-merge gates.
**Feature**: [tasks.md](../tasks.md)

No constitution file in this repo — checklist follows the project's CLAUDE.md pre-merge gate (the `/ship` skill's Steps 3 and 4.5).

## Per-Phase Gates

After each phase (US3 / US2 / US1 / US4 / US5):

- [ ] **Ruff** clean: `python3 -m ruff check .`
- [ ] **mypy** clean: `mypy heist/ agents.py demo.py`
- [ ] **pytest** clean: `pytest -q`
- [ ] **Import sanity**: `python3 -c "import agents, demo, heist, heist.runner, heist.scenes, heist.mechanics, heist.server, heist.persist"`

## Per-User-Story Verification

Each US has at least one test that **fails before** its implementation lands and **passes after** — the spec's Independent Test guarantee.

### US3 (probe budget)

- [ ] `tests/test_scouting.py` asserts `free_probe_budget()` returns 10 for ≥3 distinct crew compositions.

### US2 (pick_order)

- [ ] `tests/test_board.py` covers: ascending probes, bankroll tiebreak, ai_idx final tiebreak, all-zero-probes case, empty input.

### US1 (parallel scouting)

- [ ] `tests/test_orchestration.py` exists and contains: (a) a timing test that uses a slow-mocked `_scout_one` and asserts wall-clock ≤ 1.2 × single-scout time for 3 teams, (b) an error-containment test where one team's scout raises and the others complete.

### US4 (carryover + mix-aware replenish)

- [ ] `tests/test_board.py` tests `replenish_mix_aware` with a synthetic skewed carryover; asserts mix shifts toward balance.
- [ ] `tests/test_campaign.py` runs a 2-round stub campaign and asserts (a) 5 of round 2's 8 jobs are carryover names, (b) `persistent_slate_scores` values for those 5 jobs match round 1.

### US5 (persistent scout intel)

- [ ] `tests/test_scouting.py` asserts `Campaign.per_ai_scout_state[ai].reveals` survives a round transition; `probes_spent_free` resets to 0.
- [ ] `tests/test_campaign.py` runs a 2-round stub campaign; round 1 scouts a non-picked job, round 2 asserts the prior reveal is present in the team's scout prompt and in the slate's `boardByAI` rendering.

## Smoke Test (pre-merge, per `/ship` Step 4.5)

Required because `orchestration.py` is touched in every phase (runner-flow):

- [ ] Boot a server with `HEIST_STATE_DIR=$(mktemp -d) HEIST_TURN_DELAY=0` on a throwaway port; new-game + add-ai (stub) + launch; wait; assert `status=done`.
- [ ] Clean up the temp state dir and kill only the smoke-test server.

## Browser Verification (US5)

- [ ] On staging (8001) after Phase C ships, open the Job tab during a round-2 scout phase of a Quick Test campaign; visually confirm that cells scouted in round 1 still show `(estimate)` or `🔍 N/10` — not `???`.

## End-to-End Playtest (after Phase C)

- [ ] Quick Test on staging, all 3 rounds:
  - [ ] Parallel scout speed is noticeable.
  - [ ] Probe budget shows as 10 in the scout prompt.
  - [ ] Least-probes-first picks first.
  - [ ] ~5 jobs carry over each round.
  - [ ] Persisted reveals are visible across rounds.
  - [ ] At least one team in round 2 or 3 picks a job it scouted in a prior round (SC-007).
