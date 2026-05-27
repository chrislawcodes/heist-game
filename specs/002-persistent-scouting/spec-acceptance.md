# Acceptance Criteria: Persistent Scouting

## User Stories
| ID | Title | Priority |
|----|-------|----------|
| US-1 | A job's difficulty is fixed for the whole campaign | P1 |
| US-2 | Once a team scouts a location, it stays scouted for that team | P1 |
| US-3 | A resumed campaign keeps its locked scores and scouting memory | P2 |

## Acceptance Scenarios

### US-1: Locked scores
- Given a fresh campaign, When round 1 and round 2 run, Then every job has the same hidden challenge scores in both rounds.
- Given a job attempted in round 1, When it appears again in round 2, Then its hidden scores are unchanged.
- Given locked scores rolled at start, When any team scouts a cell, Then the revealed value equals the locked value (no divergence between teams).

### US-2: Persistent scouting
- Given team A scouted (Museum, physical) in round 1, When round 2 begins, Then team A already knows it and spends no probe to keep it.
- Given team A enters round 2 knowing 2 cells and gets 3 fresh probes, When it scouts 3 new cells, Then it knows 5 cells at job-pick.
- Given team A knows a cell but team B does not, When round 2 replays render, Then A's job tab shows it and B's does not.
- Given a probe re-issued for a known cell, When applied, Then it is a no-op and consumes no free probe.

### US-3: Resume
- Given a campaign that completed round 1 with scouting, When resumed, Then locked scores are byte-identical (not re-rolled).
- Given team A scouted 2 cells before a stall, When resumed, Then A still knows exactly those 2 cells.
- Given a legacy campaign with no stored locked scores, When resumed, Then scores are initialized once and it continues without error.

## Success Criteria
- SC-001: Across a 3-round campaign, each job's challenge scores are identical every round (zero variance).
- SC-002: A cell scouted in round 1 is shown as known in every later round, zero extra probes spent.
- SC-003: Resume preserves 100% of each team's reveals and identical locked scores; no loot/probe double-count.
- SC-004: A team never spends a free probe to re-learn a known cell.
- SC-005: One team's scouting memory never appears for another team.

## Key Constraints
- Locked scores are campaign-global — *Why: a job's true difficulty is one fact about the world, identical for all teams.*
- free_probes resets per round; only reveals/exact_scores carry forward — *Why: scouting more each round is the intended progression (FR-005).*
- Engine re-emits carried-forward reveals; UI never reconstructs — *Why: two-lane rule; per-round replay only sees its own sub-game's events.*
- Must not re-roll/lose/double-count on resume — *Why: resume is an existing load-bearing capability.*
- Hidden challenges/hidden-depth stay hidden even when fully scouted — *Why: explicit design rule (FR-013); scouting only sharpens published cells.*
- Buckets / +1 collaboration / steep heat cascade untouched — *Why: locked design; persistent scouting is the cascade's counterweight, not a softening of it.*
