# Quickstart: Scouting Depth + Board Rotation

Manual testing guide. Each section maps to a user story from spec.md.

## Prerequisites

- [ ] Worktree on `feat/scouting-depth-rotation` at `/Users/chrislaw/heist-game/.claude/worktrees/scouting-depth-rotation/`.
- [ ] Preflight passes: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`.
- [ ] Staging server on **port 8001** restarted from this worktree (or a fresh isolated server on a throwaway port with `HEIST_STATE_DIR=$(mktemp -d) HEIST_TURN_DELAY=0`).

---

## Testing US-1: Parallel scouting

**Goal**: Confirm all teams' scout turns run concurrently, not serially, and a single team's failure doesn't block the others.

**Steps**:
1. Launch a **stub** campaign via `/api/new-campaign` with 3 stub AIs and `num_rounds=1`.
2. Watch the server log (or instrument `_run_scout_turn` to log `start_ts` / `end_ts` per AI).
3. Confirm the three scout turns' time windows overlap; the board-stage wall-clock should be ≤ ~1.2× the longest single scout.

**Expected**:
- All three scout `turn_start` events fire within ~100ms of each other.
- Total board-stage elapsed time ≈ max(individual scout times), not their sum.
- The campaign reaches `status=done` end-to-end.

**Verification**:
```bash
PORT=$((8800 + RANDOM % 100))
TMPSTATE=$(mktemp -d)
HEIST_STATE_DIR="$TMPSTATE" HEIST_TURN_DELAY=0 \
  python3 -m heist serve --port $PORT > /tmp/heist-quickstart.log 2>&1 &
sleep 2
curl -s -X POST http://localhost:$PORT/api/new-campaign \
  -H 'Content-Type: application/json' \
  -d '{"num_rounds":1,"ais":[
    {"name":"A","prompt":"x","agent":"stub"},
    {"name":"B","prompt":"x","agent":"stub"},
    {"name":"C","prompt":"x","agent":"stub"}]}'
# wait for done, then inspect sub-game event timestamps
```

---

## Testing US-2: Pick order by fewest probes used

**Goal**: Verify pick order = ascending probes, with bankroll tiebreak.

**Steps**:
1. Unit-test `board.pick_order` against synthetic tuples:
   - `[(0, 2, 1_000_000), (1, 7, 500_000), (2, 4, 750_000)]` → `[0, 2, 1]`.
   - `[(0, 4, 1_000_000), (1, 4, 500_000)]` → `[1, 0]` (bankroll tiebreak).
   - `[(0, 4, 500_000), (1, 4, 500_000)]` → `[0, 1]` (ai_idx tiebreak).
2. Launch a stub 3-team 1-round campaign; inspect the per-team `scout` event's parsed `probes` count and the order of `job_claimed` events.

**Expected**:
- The team with the **fewest probes** in `scout` `turn_end` is the first to receive `job_claimed`.

**Verification**:
```bash
# After a stub campaign completes:
python3 -c "
import json, glob
subs = [g for g in glob.glob('state/games/*.json')
        if (d:=json.load(open(g))).get('parent_campaign_id') == <cid>]
# print probes_count vs job_claimed order; assert ascending
"
```

---

## Testing US-3: Bigger free probe budget

**Goal**: Confirm the free probe budget is at least 10 per team per round.

**Steps**:
1. In a stub campaign's first round, inspect the per-team `scout` `turn_start` prompt.
2. Confirm the prompt text reports a budget of `10` (the new flat value), regardless of crew size or driver bonus.

**Expected**:
- Scout prompt: "You have 10 free scouting probe(s) this round" (or wording reflecting the new budget formula).

**Verification**:
```bash
python3 -c "
import json
d = json.load(open('state/games/<sub_game_id>.json'))
scout = next(e for e in d['events']
             if e['type']=='turn_start' and e.get('label')=='scout')
assert '10 free scouting probe' in scout['prompt'].lower() or 'probe(s)' in scout['prompt']
"
```

---

## Testing US-4: Board carryover with mix-aware replenish

**Goal**: Confirm unpicked jobs persist into the next round, and new draws diversify the mix.

**Steps**:
1. Stub a **2-round, 3-team** campaign.
2. In round 1, pick any 3 jobs (stub picks the first viable one each).
3. Compare round 2's board to round 1's:
   - 5 of the 8 round-1 unpicked jobs MUST appear in round 2.
   - The 3 new draws should NOT all share the same dominant challenge category as the majority of the carryover.

**Expected**:
- Round 2 emits a `job_board` event whose `board` includes ≥ 5 job names also present in round 1's `job_board`.
- `Campaign.persistent_slate_scores` contains entries for all 5 carryover jobs, and their values match round 1's rolled scores.

**Verification**:
```bash
python3 -c "
import json
camp = json.load(open('state/games/<cid>.json'))
# round 1 and round 2 sub-games, per team
# check overlap of board names; check persistent_slate_scores stability
"
```

---

## Testing US-5: Persistent scout intel across rounds

**Goal**: Confirm a team's reveals on a carried-over job persist into the next round.

**Steps**:
1. Stub a 2-round campaign with 3 teams.
2. In round 1, ensure at least one team scouts a job that is **not picked** by anyone (use `HEIST_TURN_DELAY=0` and a stub agent that scouts a fixed pool — adjust stub to scout 1 cell on a low-reward job, ensuring no one picks it).
3. In round 2, inspect that team's `scout` `turn_start` prompt: the previously scouted cell should show `(estimate)` or `(scouted: N/10)`, not `???`.
4. Also inspect the Job tab's render (`/api/games/<round2_sub_id>/events`) — the slate card for that job should show the prior reveal.

**Expected**:
- Round 2 scout prompt shows the prior round's reveals on carried-over jobs.
- A second probe on a cell that was already BUCKET in round 1 advances it to EXACT in round 2.

**Verification**:
```bash
python3 -c "
import json
# Compare per_ai_scout_state in the campaign record between rounds
camp = json.load(open('state/games/<cid>.json'))
pre = camp['campaign_state']['per_ai_scout_state'].get('<ai_idx>', {})
# in round 2, reveals should be a superset of round-1 reveals on carried-over jobs
"
```

---

## Cross-phase smoke (all stories together)

After Phase C ships, run a **full 3-round Quick Test** on staging (`http://127.0.0.1:8001/`):

1. Click ▶ Quick Test.
2. Open the Job tab on round 1 — confirm 8 fresh cards, escape rows showing `N/6`.
3. After round 1's pick → round 2 board: confirm ~5 cards look familiar (carryover); 3 are new.
4. Open the Job tab on round 2's scout — your prior reveals are still visible on the carried-over cards.
5. At least one team should have picked a job it scouted in a prior round by round 3 (validates SC-007).

---

## Troubleshooting

**Issue**: `feature/job-board-fix` (#84) emit timing seems broken — board shows ~50 jobs during scouting again.
**Fix**: Confirm the conductor emits `job_board` **before** spawning the parallel scouts (not after). The board-build/emit step must come first in the new flow.

**Issue**: Round 2 starts with an empty board on a resumed campaign.
**Fix**: Check that `campaign_from_dict` defaults `carryover_board` and `persistent_slate_scores` to empty (not raising) when keys are missing; check that `Campaign.consumed_jobs` includes the prior round's picks before computing the next round's board.

**Issue**: A team's prior reveals disappear in round 2.
**Fix**: `Campaign.per_ai_scout_state` must be the same object that `_run_scout_turn` mutates; ensure the conductor reuses the persisted ScoutState rather than constructing a fresh one each round. Reset only `probes_spent_free` and `free_probes` per round.

**Issue**: pytest fails with `AttributeError: 'Campaign' object has no attribute 'carryover_board'` when loading a pre-feature save.
**Fix**: `campaign_from_dict` must default the new field; do not raise on missing.
