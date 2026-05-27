# Quickstart: Contested Job Board

## Prerequisites

- [ ] Worktree on `feat/phase4-scoring-scouting`, preflight green.
- [ ] `python -m heist run-campaign --agent stub` works (single-AI baseline).

## US1 — Rotating board + global consumption (single-AI)

**Goal**: each round shows ≤8 jobs; attempted jobs never reappear.

**Steps**:
1. `python -m heist run-campaign --agent stub` (seeded).
2. Read the per-round logs / round snapshots.

**Expected**:
- Each round's board ≤ 8 jobs, drawn from `pool − consumed`.
- A job attempted in round N is absent in rounds N+1…10.
- When < 8 unconsumed remain, the board shows all remaining (no crash).

## US2 — Reward climbs with difficulty

**Goal**: take scales with difficulty; floor ≥ $1M; elite jackpots highest.

**Verification**:
```bash
python - <<'PY'
from heist.content import JOBS
from heist.state import ChallengeLevel as CL
rows = []
for j in JOBS:
    nh = sum(1 for v in j.profile.values() if v == CL.HARD)
    rows.append((nh, sum(j.scene_loot.values()), j.name))
print("min take:", min(r[1] for r in rows))
import statistics
for nh in (0,1,2,4):
    band = [r[1] for r in rows if r[0]==nh]
    if band: print(nh, "Hard median:", statistics.median(band))
print("top 2:", sorted(rows, reverse=True)[:2])
PY
```
**Expected**: min take ≥ $1,000,000; band medians ascend; top two are the 4-Hard jobs (≥ $15M).

## US3 — Contention (4 teams, trailing-first)

**Goal**: lowest-banked team picks first; jobs consumed globally.

**Steps**: run the 4-team conductor harness (test or `run-campaign` multi-AI path).

**Expected**:
- Pick order each round = ascending banked loot.
- Two teams wanting the same job → lower-banked gets it; the other falls back to an available board job.
- No job attempted by any team reappears next round.

## US4 — Gating + wilds

**Expected**: round 1 gated slots are low tier (no elite jackpot in gated slots); late rounds unlock high tiers; ≥2 affordable jobs every round; wild slots can surface a surprise. Same seed → same board.

## US5 — Expanded pool

**Expected**: pool ~50 jobs; a 4-team 10-round run never exhausts the board; all content invariants pass.

## US6 — Viewer

**Expected**: replay shows each round's 8-job board and who claimed what; consumed jobs gone; nothing reconstructed client-side.

## US7 — Docs

**Expected**: `heist_game_design.md` + CLAUDE.md match shipped reality (scores, contested board, reward-climb, 21 roster).

## Full verification

```bash
python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q
```
