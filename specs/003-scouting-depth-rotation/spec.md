# Feature 003 — Scouting Depth + Board Rotation

- **Branch**: `feat/scouting-depth-rotation`
- **Created**: 2026-05-27
- **Status**: Draft (ready for plan)
- **Constitution check**: SKIPPED (no constitution/governance file in repo)

## Input

A coherent redesign that gives scouting real strategic depth and lets investments compound across rounds. Five tightly-related changes intended to ship together as one cohesive design shift:

1. Run all teams' scout turns in **parallel** (today they run serially per team inside `_pick_for`).
2. Change pick order from "trailing-team-first (lowest banked)" to **"fewest probes used"**, with banked-loot as a tiebreak and ai_idx as the final tiebreak. Teams that "rush in blind" get rewarded with first pick; teams that scout deep go later.
3. Raise the **free probe budget** from `crew size + driver bucket bonus (~6)` to `crew size + best driver's 1–10 score`. A typical 4-crew with a High driver lands at ~13; a 4-crew with no driver gets 4. Rewards investment in both crew size and driver skill while keeping budget visibly tied to crew composition — and pairs with the new pick-order rule (use them, pick last).
4. **Board carryover**: each round, carry forward the `(8 − N)` unpicked jobs and draw `N` new ones (N = teams that picked). The replenishment is **mix-aware** — bias new draws to fill gaps in challenge-category and reward-tier distribution, on top of `build_board`'s existing gating.
5. **Persistent scout intel**: each team's `reveals` and `exact_scores` persist across rounds on the Campaign. A team's prior scouting on a carried-over job stays revealed; light scouting across rounds accumulates.

**Locked design (not changed by this feature):**
- Phase 4's hidden 1–10 scores, score-margin resolution, +1-point collaboration, convex pricing.
- 21-character roster.
- `BOARD_SIZE = 8`.
- The just-shipped escape mechanic (derived 0–6 difficulty vs Driver's 1–10 score).

**User preference:** MVP-first with a staging review between phases. P1 (US1/2/3) unlocks the new strategic axis; P2 (US4/5) adds the compounding layer.

---

## User Scenarios & Testing

### User Story 1 — Parallel scouting (Priority: P1)

*As a campaign conductor, when a round's board stage begins, I need every active team's scout turn to fire concurrently so the round's wall-clock time is bounded by the slowest single scout, not the sum of all scouts.*

**Why this priority**: P1, because it's a prerequisite for the new pick-order rule (we can't sort teams by probes spent until every team has finished scouting). It also restores reasonable round latency once the probe budget grows.

**Independent test**: Launch a stub 3-team campaign with `HEIST_TURN_DELAY=0`. Time the board stage start → board stage end. Confirm elapsed ≤ ~1.2× a single team's scout turn (not ~3×).

**Acceptance Scenarios:**

1. **Given** a campaign round with 3 active teams, **When** the board stage runs, **Then** the 3 scout turns start within ~100ms of each other and finish concurrently.
2. **Given** one team's scout call raises an exception, **When** the board stage runs, **Then** the other teams' scouts still complete and the round proceeds (the failing team is treated as having spent 0 probes).
3. **Given** the conductor is resumed mid-round between scouting and picking, **When** resume starts, **Then** prior per-team probe counts and reveals are restored and the round continues from the pick step.

---

### User Story 2 — Pick order by fewest probes used (Priority: P1)

*As a competing AI team, I need pick order to favor teams that scouted least so that "rush in blind" is a real strategic choice with a real reward (first pick), and "scout deep" is a real trade-off (last pick).*

**Why this priority**: P1, because this is the change that turns scouting into a strategic axis. Without it, more probes is strictly free upside and the depth dial doesn't matter.

**Independent test**: Unit-test `pick_order(...)` against synthetic standings carrying `(ai_idx, probes_spent, banked_loot)`. Verify ascending order on probes_spent, then ascending on banked_loot for ties, then ascending on ai_idx.

**Acceptance Scenarios:**

1. **Given** Team A spent 2 probes, Team B spent 7, Team C spent 4, **When** pick order is computed, **Then** order is A → C → B.
2. **Given** Team A spent 4 probes with $1M banked, Team B spent 4 probes with $500k banked, **When** pick order is computed, **Then** B picks before A (banked-loot tiebreak).
3. **Given** two teams tied on probes and bankroll, **When** pick order is computed, **Then** the lower ai_idx picks first (final tiebreak).
4. **Given** every team spent 0 probes (all rushed), **When** pick order is computed, **Then** order falls through to bankroll then ai_idx (equivalent to today's order for that case).

---

### User Story 3 — Bigger free probe budget (Priority: P1)

*As a competing AI team, I need enough free probes (~10) that "deep scout one job + sample a few others" is achievable in a single round, so the choice between depth, breadth, and rushing is meaningful rather than forced.*

**Why this priority**: P1, because at the current budget (~6 against 32 cells) probes are too scarce for the new pick-order rule to expose interesting strategies — every team would still want to use them all.

**Independent test**: Unit-test the new probe budget function returns the target value (target: 10) for a standard 4-crew. End-to-end: in a stub campaign, inspect the scout-turn prompt and verify it reports the new budget.

**Acceptance Scenarios:**

1. **Given** a standard 4-crew team in a campaign round, **When** the scout turn is offered, **Then** the team's free probe budget is at least 10.
2. **Given** the budget is 10, **When** a team scouts 1 job to full exact reveal (4 cells × 2 probes = 8 probes), **Then** they still have ≥2 probes left for sampling other jobs.
3. **Given** a team has no driver, **When** the scout turn is offered, **Then** the budget is still at least the new floor (plan to confirm whether driver bonus stacks on top or is folded in).

---

### User Story 4 — Board carryover with mix-aware replenish (Priority: P2)

*As a competing AI team, when a round ends with jobs I scouted but didn't pick, I need those jobs to stay on next round's board (mostly) so my scouting wasn't wasted, with N new jobs drawn to fill the slots vacated by picks — and the new jobs should diversify the board's mix.*

**Why this priority**: P2, because the strategic axis from P1 still works without it (rush vs scout, single-round). But this is where scouting investments compound and the board feels continuous rather than re-rolled. Required for the redesign's full intent.

**Independent test**: Simulate two rounds with a seeded RNG, force a known set of carryover jobs, assert (a) `(BOARD_SIZE − N)` carried jobs appear on round 2's board, (b) `N` newly drawn jobs appear, (c) the new draws shift the category/reward distribution toward balance compared to a naive random draw.

**Acceptance Scenarios:**

1. **Given** an 8-job board where 3 teams pick 3 distinct jobs, **When** the next round starts, **Then** 5 unpicked jobs carry over and 3 new jobs are drawn.
2. **Given** all 5 carryover jobs lean confrontation-heavy and low-reward, **When** the 3 new jobs are drawn, **Then** the new draws favor non-confrontation profiles and at least one higher-reward tier.
3. **Given** the pool is exhausted (fewer than `BOARD_SIZE − carryover` fresh jobs available), **When** the next round starts, **Then** the board is smaller than 8 (consistent with `build_board`'s current behavior) and the system continues normally.
4. **Given** a carried-over job has rolled hidden challenge scores from the prior round, **When** it persists onto the next round's board, **Then** its hidden scores stick to the job (so prior reveals stay meaningful).

---

### User Story 5 — Persistent scout intel across rounds (Priority: P2)

*As a competing AI team, when I scouted a job last round (whether I picked it or not), I need my reveals to persist into this round so my scouting compounds and I can scout broadly over time instead of dumping the whole budget in one round.*

**Why this priority**: P2, because it pairs with US4 — without carryover the persistence has little to attach to, and without persistence the carryover only gives the AI a job name to re-recognize, not actual intel. Together they make scouting a long-game choice.

**Independent test**: Run two rounds against a stub agent. In round 1, scout Job X (which the team does not pick). In round 2, with Job X carried over, verify the team's `reveals` and `exact_scores` for Job X are still present and visible in the next scout turn's prompt and in the Job tab's slate render.

**Acceptance Scenarios:**

1. **Given** Team A scouted Job X's electronic cell to EXACT in round 1, **When** Job X carries over to round 2, **Then** Team A's scout prompt and Job-tab slate both show the EXACT reveal for that cell in round 2.
2. **Given** Team A scouted Job X's electronic cell to BUCKET in round 1, **When** Team A scouts the same cell again in round 2, **Then** the reveal advances to EXACT (i.e., a single new probe completes the two-step reveal across rounds).
3. **Given** Job X gets picked by any team mid-round, **When** the next round starts, **Then** Job X is no longer on the board (consumed); persisted reveals for Job X may remain in history but are not surfaced as live board intel.
4. **Given** a campaign was running under the OLD model (no persistence) and resumes after this feature ships, **When** resume loads, **Then** missing persistent scout structure defaults to empty (no crash) and play continues.

---

## Edge Cases

- **One team's scout call fails / times out** → that team's probe count is treated as 0; they're sorted to the top of the pick order (a "rusher"); their reveals remain whatever they had. The other teams' scouts proceed unaffected (FR-001, FR-002).
- **All teams use 0 probes** → pick order falls through to bankroll-ascending then ai_idx (FR-002).
- **All teams use the maximum probes** → pick order falls through to bankroll-ascending then ai_idx (same tiebreak chain).
- **Carryover would leave the board < BOARD_SIZE** because the pool is exhausted → board is the size of `carryover + available_replenish` (consistent with current `build_board`); no padding.
- **A team has its standing crew shrink mid-campaign** (caught members) → probe budget is independent of crew size after this feature (decouples from `crew_size + driver_bonus`); the team still gets the budgeted probes.
- **A campaign is resumed mid-board-stage** (between scouts and picks, or mid-scouts) → persisted per-team scout state and pick-order inputs round-trip so resume is idempotent. If only some teams have scouted, the conductor re-runs the missing scouts.
- **An old (pre-feature) campaign resumes after deploy** → missing `per_ai_scout_state` / `carryover` fields default to empty; play continues with the new rules from that round forward.
- **A persisted carried-over job's rolled hidden challenge scores conflict with a fresh roll on the same name** → the carried scores stick to the carried job (FR-005), not re-rolled, so prior reveals stay meaningful.

---

## Functional Requirements

- **FR-001**: System MUST run scout turns for all active teams concurrently within the board stage (not serially). Supports US1.
- **FR-002**: System MUST determine pick order each round by ascending count of free probes used, with banked-loot ascending as the first tiebreak and ai_idx ascending as the final tiebreak. Supports US2.
- **FR-003**: System MUST set each team's free probe budget per round to `len(crew) + best driver's 1–10 score` (0 if no driver). This varies per team — bigger crews and stronger drivers get more probes; the budget rewards crew investment. Supports US3.
- **FR-004**: System MUST carry forward all unpicked jobs from the prior round's board (i.e., `(BOARD_SIZE − N)` jobs where N is the number of teams that successfully claimed a job) into the current round's board. Supports US4.
- **FR-005**: System MUST replenish the board with `N` newly drawn jobs each round (or fewer if the pool is exhausted). The selection of new draws MUST bias toward filling gaps in the carryover's distribution along (a) challenge category emphasis and (b) reward tier, while still respecting `build_board`'s existing gating (campaign progress + wilds). Supports US4.
- **FR-006**: System MUST preserve the rolled hidden challenge scores for any carried-over job (no re-roll), so that persistent reveals remain truthful. Supports US4/US5.
- **FR-007**: System MUST persist per-team scout state (`reveals`, `exact_scores`, and any related metadata needed to render and resolve reveals) across rounds on the Campaign. A team's prior reveals on a carried-over job MUST be visible to that team in the next round's scout prompt and Job tab. Supports US5.
- **FR-008**: System MUST emit a `job_board` event per team at the beginning of each round's board stage (before scouting) that carries the composed round board (carryover + replenish) — preserving the timing fix shipped in #84. Supports all stories.
- **FR-009**: System MUST update the AI rulebook (`prompts.py _TRADECRAFT`) to describe (a) the new larger probe budget, (b) the least-probes-first pick order with bankroll tiebreak, (c) board carryover, and (d) persistent scouting intel, so the AI reasons under the new rules.
- **FR-010**: System MUST NOT modify the locked Phase 4 design (1–10 hidden scores, score-margin resolution, +1-point collaboration, convex pricing), the 21-character roster, `BOARD_SIZE=8`, or the just-shipped escape mechanic.
- **FR-011**: System MUST surface the new state in serialization so the Job tab and replays correctly render (a) which jobs are carryover vs new, (b) each team's persisted reveals on carried-over jobs.

---

## Success Criteria

- **SC-001**: After P1 ships, the board stage's elapsed wall-clock time in a 3-team stub campaign is ≤ 1.2× the longest single scout-turn time (validating parallelism). [US1]
- **SC-002**: After P1 ships, in 20 simulated rounds with synthetic probe counts, a team that spent strictly fewer probes than another picks before them in 100% of cases that don't require a tiebreak. [US2]
- **SC-003**: After P1 ships, the scout-turn prompt reports a free probe budget equal to `len(crew) + best driver's 1–10 score` for the team (e.g. a 4-crew with a High driver sees ~13 probes; a 4-crew with no driver sees 4). [US3]
- **SC-004**: After P2 ships, in a 3-round stub campaign with 3 teams, at least `(BOARD_SIZE − N) / BOARD_SIZE = 5/8 ≈ 62%` of round N+1's board consists of carryover jobs from round N (the rest are new draws). [US4]
- **SC-005**: After P2 ships, when a job is carried over from round N to round N+1 and Team A had any reveal on it in round N, Team A still sees that reveal in round N+1's job_board and scout prompt. [US5]
- **SC-006**: After P2 ships, in a 3-round playtest the variance of challenge-category coverage on the board (measured as the std-dev of category-count across the 8 jobs) is ≤ 1.5 — confirming the mix-aware replenish keeps the board diverse rather than drifting to one category. [US4]
- **SC-007**: After both phases ship, in a Quick Test playtest, at least one team in each round successfully picks a job it had scouted in the prior round (confirming compounding works end-to-end).

---

## Key Entities

- **ScoutState (per team)** — extended to be the persisted, per-campaign, per-team scouting record. Carries `reveals` (job_name → category → RevealLevel), `exact_scores` (job_name → category → 1–10 score), the latest `rationale`, `probes_spent_free` for the current round, and `free_probes` budget. Persistence is across rounds; only the round-specific counters reset between rounds.
- **Campaign** — gains a `per_ai_scout_state: dict[int, ScoutState]` aggregating each team's persisted scouting, and either (a) keeps the carryover jobs' rolled hidden challenge scores in a campaign-level `persistent_slate_scores: dict[str, dict[str, int]]`, or (b) attaches the rolled scores directly to a carried Job snapshot. Exact carrier finalized in plan.
- **Round Board** — the composed list of ≤8 job names for the round, derived from `prior_round_unpicked + replenish_new`. The board for round 0 is a clean `build_board` draw (no prior round).
- **Job** — unchanged. The escape model from #85 and the locked Phase 4 fields are untouched.

---

## Assumptions

- **Probe budget target = 10.** Final number confirmed in the plan after sampling realistic scout patterns. The formula will likely drop the `crew_size + driver_bonus` derivation in favor of a flat budget; driver bonus may still apply on top.
- **Mix-balancing heuristic.** When drawing N new jobs, compute the carryover's distribution along (a) which challenge category is the most-demanding cell for each job (electronic-heavy / physical-heavy / etc.) and (b) reward tier band. Weight the random draw toward under-represented bins. Exact weighting finalized in plan.
- **Parallelism = threads, not processes.** Scout turns are I/O-bound (LLM calls), so `concurrent.futures.ThreadPoolExecutor` or equivalent is sufficient. GIL is not a constraint for I/O concurrency.
- **Persistence storage.** Per-team `ScoutState` lives on the Campaign in memory, serialized into the campaign's saved record. Sub-game (round) records continue to emit `job_board` and `scouted` events for replay; the campaign-level state is the source of truth for "what does team A know across rounds."
- **Carried-over jobs keep their hidden scores.** The roll happens once when a job first enters the board; subsequent rounds inherit those scores until the job is consumed. This is required for prior reveals to remain truthful (US5).
- **Backward compatibility on resume.** Old (pre-feature) saved campaigns lack the new persistent structures; loaders default them to empty. Play resumes under the new rules from the next round; previously-emitted events in the old format remain renderable.
