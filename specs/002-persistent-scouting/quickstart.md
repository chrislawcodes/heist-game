# Quickstart: Persistent Scouting

Manual verification on a throwaway server (keeps real lobbies clean). The stub AI scouts the physical defense of the first 1-2 jobs each round, so persistence is observable without spending real AI calls.

## Prerequisites

- [ ] On branch `feat/scout-persistence`, worktree `.claude/worktrees/scout-persistence`
- [ ] Preflight green: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`
- [ ] A server running this worktree's code on a free port (e.g. 8002), or use staging (8001) after restart

## Test US1 — scores are locked for the campaign

**Goal**: a job's hidden scores are identical in every round (SC-001).

**Steps**:
1. Start a 2-round stub campaign: `POST /api/new-campaign` with `{"num_rounds":2,"ais":[{"name":"T","prompt":"...","agent":"stub"}]}`.
2. From the journey, read round 0's and round 1's heist sub-game ids.
3. In each, read the `challenge_scores` on the picked job and any `scouted` events.

**Expected**: every job's challenge scores match between round 0 and round 1 (zero variance).

## Test US2 — scouting stays scouted

**Goal**: a cell scouted in round 0 is known in round 1 with no new probe (SC-002, SC-004), and the replay shows it.

**Steps**:
1. In the round-0 heist sub-game, note the `scouted` cells (stub scouts e.g. Museum/physical, Armored Car/physical).
2. Open the round-1 heist sub-game's event stream.
3. Open `/job?campaign=<id>&ai=0&round=1` and step to the job pick.

**Expected**:
- Round 1's stream emits carried-forward `scouted` events for round 0's cells at the top.
- The round-1 job tab shows those cells' `🔍 N/10` badges (cumulative), plus any new ones.
- No free probe is spent to retain the old cells.

## Test US2 — per-team isolation

**Goal**: one team's intel never shows for another (SC-005).

**Steps**: run a 2-team stub campaign; compare `/job?...&ai=0&round=1` vs `...&ai=1&round=1`.

**Expected**: each team's cumulative badges reflect only its own scouting.

## Test US3 — resume keeps locked scores + memory

**Goal**: SC-003.

**Steps**:
1. Run a campaign through round 0 with scouting; stop the server mid-round-1 (simulate stall).
2. Restart the server; resume the campaign (`POST /api/campaign/<id>/resume`).
3. Re-read round 1.

**Expected**: identical locked scores (not re-rolled), all round-0 reveals intact, no loot/probe double-count.

## Troubleshooting

- **Round 1 scores differ from round 0** → locked scores not being reused; check `run_one_job` reads `campaign.slate_scores` instead of calling `roll_slate_scores`.
- **Round 1 shows no prior badges** → carried-forward `scouted` events not emitted; check the round-start re-emission in `run_one_job`.
- **Resume re-rolls scores** → game-record `slate_scores` not re-injected into rebuilt Campaigns in the conductor's resume path.
- **Engine (Python) changes not visible on staging** → restart the 8001 server (HTML/JS is fresh per request; Python loads once).
