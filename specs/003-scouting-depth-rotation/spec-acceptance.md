# Acceptance Criteria: Scouting Depth + Board Rotation

## User Stories

| ID | Title | Priority |
|----|-------|----------|
| US-1 | Parallel scouting | P1 |
| US-2 | Pick order by fewest probes used | P1 |
| US-3 | Bigger free probe budget | P1 |
| US-4 | Board carryover with mix-aware replenish | P2 |
| US-5 | Persistent scout intel across rounds | P2 |

## Acceptance Scenarios

### US-1: Parallel scouting
- Given a campaign round with 3 active teams, When the board stage runs, Then the 3 scout turns start within ~100ms of each other and finish concurrently.
- Given one team's scout call raises an exception, When the board stage runs, Then the other teams' scouts still complete and the round proceeds (the failing team is treated as having spent 0 probes).
- Given the conductor is resumed mid-round between scouting and picking, When resume starts, Then prior per-team probe counts and reveals are restored and the round continues from the pick step.

### US-2: Pick order by fewest probes used
- Given Team A spent 2 probes, Team B spent 7, Team C spent 4, When pick order is computed, Then order is A → C → B.
- Given Team A spent 4 probes with $1M banked, Team B spent 4 probes with $500k banked, When pick order is computed, Then B picks before A (banked-loot tiebreak).
- Given two teams tied on probes and bankroll, When pick order is computed, Then the lower ai_idx picks first (final tiebreak).
- Given every team spent 0 probes (all rushed), When pick order is computed, Then order falls through to bankroll then ai_idx (equivalent to today's order for that case).

### US-3: Bigger free probe budget
- Given a standard 4-crew team in a campaign round, When the scout turn is offered, Then the team's free probe budget is at least 10.
- Given the budget is 10, When a team scouts 1 job to full exact reveal (8 probes), Then they still have ≥2 probes left for sampling other jobs.
- Given a team has no driver, When the scout turn is offered, Then the budget is still at least the new floor.

### US-4: Board carryover with mix-aware replenish
- Given an 8-job board where 3 teams pick 3 distinct jobs, When the next round starts, Then 5 unpicked jobs carry over and 3 new jobs are drawn.
- Given all 5 carryover jobs lean confrontation-heavy and low-reward, When the 3 new jobs are drawn, Then the new draws favor non-confrontation profiles and at least one higher-reward tier.
- Given the pool is exhausted (fewer than `BOARD_SIZE − carryover` fresh jobs available), When the next round starts, Then the board is smaller than 8 (consistent with `build_board`'s current behavior) and the system continues normally.
- Given a carried-over job has rolled hidden challenge scores from the prior round, When it persists onto the next round's board, Then its hidden scores stick to the job (so prior reveals stay meaningful).

### US-5: Persistent scout intel across rounds
- Given Team A scouted Job X's electronic cell to EXACT in round 1, When Job X carries over to round 2, Then Team A's scout prompt and Job-tab slate both show the EXACT reveal for that cell in round 2.
- Given Team A scouted Job X's electronic cell to BUCKET in round 1, When Team A scouts the same cell again in round 2, Then the reveal advances to EXACT (a single new probe completes the two-step reveal across rounds).
- Given Job X gets picked by any team mid-round, When the next round starts, Then Job X is no longer on the board (consumed); persisted reveals for Job X may remain in history but are not surfaced as live board intel.
- Given a campaign was running under the OLD model (no persistence) and resumes after this feature ships, When resume loads, Then missing persistent scout structure defaults to empty (no crash) and play continues.

## Success Criteria

- SC-001: After P1 ships, the board stage's elapsed wall-clock time in a 3-team stub campaign is ≤ 1.2× the longest single scout-turn time. [US1]
- SC-002: After P1 ships, in 20 simulated rounds with synthetic probe counts, a team that spent strictly fewer probes than another picks before them in 100% of cases that don't require a tiebreak. [US2]
- SC-003: After P1 ships, the scout-turn prompt reports a free probe budget of at least 10 for any standard 4-crew team. [US3]
- SC-004: After P2 ships, in a 3-round stub campaign with 3 teams, at least 5/8 (≈ 62%) of round N+1's board consists of carryover jobs from round N. [US4]
- SC-005: After P2 ships, when a job is carried over from round N to round N+1 and Team A had any reveal on it in round N, Team A still sees that reveal in round N+1's job_board and scout prompt. [US5]
- SC-006: After P2 ships, in a 3-round playtest the std-dev of challenge-category coverage on the board (count per category across the 8 jobs) is ≤ 1.5. [US4]
- SC-007: After both phases ship, in a Quick Test playtest, at least one team in each round successfully picks a job it had scouted in the prior round. [US4 + US5 together]

## Key Constraints

- **Locked Phase 4 design must hold**: 1–10 hidden scores, score-margin resolution, +1-point collaboration, convex pricing — *Why: the rest of the game's tuning depends on these; touching them ripples everywhere.*
- **`BOARD_SIZE = 8` is locked** — *Why: a known tuning constant balancing variety against decision overload.*
- **The just-shipped escape mechanic (#85) is locked** — *Why: derived 0–6 difficulty vs Driver's 1–10 score is the new normal; do not reintroduce escape_modifier.*
- **The `#84` emit timing for `job_board` must be preserved** (before scouts) — *Why: it's what makes the Job tab show 8 jobs during scouting; regressing it would un-fix that bug.*
- **Two-lanes rule**: every state change is an event from the engine; the UI never reconstructs — *Why: the only way to keep replay/resume truthful and the UI simple.*
- **Backward-compat on saved campaigns**: pre-feature saves must load and continue under the new rules — *Why: live games may resume across the deploy.*
