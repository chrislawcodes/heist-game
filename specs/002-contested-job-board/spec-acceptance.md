# Acceptance Criteria: Contested Job Board

## User Stories
| ID | Title | Priority |
|----|-------|----------|
| US-1 | Rotating board with global consumption | P1 (MVP) |
| US-2 | Reward climbs with difficulty | P1 (MVP) |
| US-3 | Teams contend for jobs (trailing-first) | P1 (MVP) |
| US-4 | Progression gating + random wilds | P2 |
| US-5 | Expanded job pool (~50) | P2 |
| US-6 | Board & claims in the viewer | P2 |
| US-7 | Documentation truth-up | P3 |

## Acceptance Scenarios

### US-1
- Given a pool and empty consumed set, When a round begins, Then the board is a deterministic ≤8-job draw from `pool − consumed`.
- Given a job attempted in round 3, When rounds 4–10 begin, Then it never reappears.
- Given < 8 unconsumed remain, When a round begins, Then the board shows all remaining (no crash, no padding with consumed).
- Given the AI picks/scouts, When it sees the slate, Then it is offered only the board (never full pool).

### US-2
- Given the pool grouped by Hard-count, Then band medians ascend: 0 < 1 < 2 < 4 Hards.
- Given any board job, Then its clean take ≥ $1,000,000.
- Given the 4-Hard jobs, Then each take ≥ $15M and they are the two highest.
- Given reward_range vs achievable take, Then the range brackets [squeak/partial .. clean + best bonus] with a reachable top.
- Given the retune, Then every job still pays scene_loot into an active challenge category.

### US-3
- Given 4 teams with distinct banked totals, Then pick order is ascending banked loot (tiebreak ai_idx).
- Given two teams both prefer one job, Then the lower-banked team gets it; the other falls back to an available board job.
- Given a team's preferred jobs were all taken, Then it is assigned an available board job (never idle while jobs remain).
- Given a round completes, Then every attempted job is consumed and unavailable next round.

### US-4
- Given round 1, Then gated slots are low tier (no elite jackpot in gated slots); wilds may surface anything.
- Given a late round with high total banked, Then high/elite jobs are eligible for gated slots.
- Given any round, Then ≥ the configured affordable minimum is present.
- Given the same seed + standings, Then the board is identical (deterministic).

### US-5
- Given the pool, Then ~50 jobs with all 5 categories well represented as gating challenges.
- Given every job, Then it passes all content invariants (unique names, payable loot, floor ≥ $1M, valid tier).
- Given a 4-team 10-round stub campaign, Then it completes without exhausting the board or erroring.

### US-6
- Given a round's events, Then the viewer shows exactly the 8 board jobs (not the full pool).
- Given claim events, Then each claimed job shows its owning team and contested losses are visible.
- Given a replay scrub, Then the board is consistent with the consumed set carried in events.

### US-7
- Given heist_game_design.md, Then core mechanics describe 1–10 scores, score-margin resolution, +1-point collaboration, scouting ladder; Phase 4 marked built; contested board + reward-climb documented.
- Given CLAUDE.md, Then bucket-only skills and 16-char roster are corrected; contested board documented.

## Success Criteria
- SC-001: 4-team 10-round `run-campaign --agent stub` completes — board each round, contention resolved, jobs consumed globally, no traceback.
- SC-002: 0 attempted-job repeats across a full campaign.
- SC-003: band-median take strictly ascending (0<1<2<4 Hards); pool min take ≥ $1M; the two 4-Hard jobs are the top two takes.
- SC-004: every round's board ≤ 8 and ≥ affordable-minimum; trailing team picks first 100% of rounds.
- SC-005: killed-and-resumed campaign restores identical board, pick order, consumed set for the in-flight round.
- SC-006: `ruff` + `mypy heist/ agents.py demo.py` + `pytest -q` green.

## Key Constraints
- **Two-lane rule**: board/pick-order/claims/consumed are emitted as events + persisted; viewer never reconstructs board state — *Why: replay/resume fidelity and the engine/UI contract.*
- **Determinism**: board + contention are functions of (seed, round_idx, standings) — *Why: replay, resume, and reproducible tests.*
- **One AI job-pick call per team per round**: contention re-resolution reuses the system fallback, no extra round-trip — *Why: bounds AI cost and latency in the parallel heist stage.*
- **Conductor owns the shared consumed set**: per-AI campaigns run in parallel threads and can't own shared state — *Why: correctness under concurrency.*
- **Reward floor ≥ $1M, climb with difficulty, elite jackpots $15–18M, 1–2 edges** — *Why: every board job worth contesting; makes the bank-toward-endgame arc work.*
