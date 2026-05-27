# Feature Specification: Contested Job Board

**Feature branch:** `feat/phase4-scoring-scouting` (built on top of the Phase 4 scoring/scouting work)
**Created:** 2026-05-26
**Status:** Draft → Planning
**Input:** Make the campaign job slate a rotating, fought-over board: a subset of a larger pool is shown each round, jobs are consumed globally once attempted, teams contend for them (trailing team picks first), the board composition is gated by campaign progress plus random wilds, and reward climbs with difficulty so the elite endgame jobs are the biggest scores.

---

## Background & Problem

Today the campaign shows **all jobs** (`available_jobs = list(JOBS)` in `heist/runner.py`) **every round**, identical each round, with no rotation and no inter-team competition. Two problems:

1. **No board dynamics.** 15 jobs crammed on screen every round, the same list forever. There is no scarcity, no "fresh jobs come up," and no competition between teams for the good jobs.
2. **Reward is disconnected from difficulty.** The hardest 4-Hard endgame jobs (Billionaire's Compound, The Mint) pay *less* (~$2.1M take) than mid-tier jobs (Casino $7M, Server Farm $6M). This inverts the intended campaign arc and breaks the "bank loot across rounds to afford the endgame" premise — there is no reason to build toward the hardest jobs.

This feature makes the slate a **contested board** and re-shapes reward to **climb with difficulty**.

## Locked Decisions (settled — do not re-open)

- **Shared, fought-over board.** Jobs are consumed **globally**: once any team attempts a job, it leaves the board for everyone, permanently.
- **Sized for up to 4 teams** → pool grows from 15 to **~50 jobs**, weighted toward easy/medium tiers.
- **8 jobs shown per round.**
- **Contention = trailing team picks first.** Pick order each round is ascending banked loot (the team furthest behind chooses first; anti-snowball).
- **Global progression gating + random wilds.** Early-campaign boards skew cheap-to-mid; higher tiers/jackpots unlock as the campaign progresses; some "wild" slots add surprises. Always include enough affordable jobs that no team is starved.
- **Reward climbs with difficulty.** Floor ~$1M (no sub-$1M scraps on the board); elite 4-Hard jobs are the $15–18M jackpots; deliberate slack leaves 1–2 "edge" jobs (a bargain, a trap).
- **Campaign length stays 10 rounds.**

## Constitution / Governance Check (CLAUDE.md)

- **Two-lane rule (PASS by design):** the engine emits **all** board state — the round's slate, pick order, each team's claim, contention losses, and the running consumed set — as events, and persists them in the round snapshot. The viewer only renders; it never recomputes which jobs are on the board or who won a contested job. Encoded in FR-016…FR-019.
- **System owns deterministic mechanics (PASS):** board composition, gating, pick-order, and contention resolution are deterministic given the seed + standings; the AI only *chooses* which board job to pursue. Encoded in FR-009…FR-013.
- **Locked-decision drift:** CLAUDE.md's "Locked Design Decisions" and `heist_game_design.md` core mechanics still describe the pre-Phase-4 bucket model and a 16-character roster; this feature's doc pass corrects them (US7).

---

## User Scenarios & Testing

### User Story 1 — Rotating board with global consumption (Priority: P1) 🎯 MVP

As a player watching a campaign, I need each round to present a *subset* of the job pool that changes over time, with jobs disappearing once any team has attempted them, so the campaign feels like a living board of opportunities rather than a static list.

**Why this priority:** This is the foundational mechanic. Without per-round board selection and global no-repeat, nothing else (contention, gating) has anything to operate on.

**Independent Test:** Run `run-campaign --agent stub` (even with one team). Each round shows ≤8 jobs drawn from the pool; a job attempted in round N never appears again in rounds N+1…10; the board refills from the unconsumed pool.

**Acceptance Scenarios:**

1. **Given** a pool of N jobs and an empty consumed set, **When** a round begins, **Then** the board is a deterministic (seeded) selection of up to 8 jobs drawn only from jobs not yet attempted.
2. **Given** a team attempts "The Cargo Yard" in round 3, **When** rounds 4–10 begin, **Then** "The Cargo Yard" never appears on the board again.
3. **Given** the unconsumed pool has fewer than 8 jobs left, **When** a round begins, **Then** the board shows all remaining unconsumed jobs (no crash, no padding with consumed jobs).
4. **Given** the AI is asked to pick/scout, **When** it sees the slate, **Then** it is offered only the current board's 8 jobs — never the full pool.

---

### User Story 2 — Reward climbs with difficulty (Priority: P1) 🎯 MVP

As a player, I need a job's payout to scale with how hard it is, so that the elite endgame jobs are the biggest scores and banking loot across rounds to afford them is worthwhile.

**Why this priority:** A contested board is meaningless if the hardest jobs pay the least. This re-shaping is what makes the board worth fighting over and the campaign arc coherent. Small, self-contained (re-tune existing content), so it ships in the MVP.

**Independent Test:** Sort all jobs by difficulty (number of Hard challenges, then tier). The clean take is monotonic-ish ascending across difficulty bands; the minimum take across the pool is ≥ $1M; the 4-Hard elite jobs are the top scores ($15–18M); 1–2 jobs deliberately deviate (one bargain above trend, one trap below).

**Acceptance Scenarios:**

1. **Given** the job pool, **When** takes are grouped by Hard-count, **Then** band medians ascend: 0-Hard < 1-Hard < 2-Hard < 4-Hard.
2. **Given** any job on the board, **When** its clean take is read, **Then** it is ≥ $1,000,000.
3. **Given** Billionaire's Compound and The Mint (4 Hards), **When** their takes are read, **Then** each is ≥ $15M and they are the two highest in the pool.
4. **Given** the published `reward_range`, **When** compared to the achievable take, **Then** the range brackets roughly [squeak/partial take … clean take + best hidden-depth bonus] and the range top is reachable.
5. **Given** the re-tune, **When** the test suite runs, **Then** every job still satisfies "scene_loot pays into an active challenge category" (no $0-payout jobs).

---

### User Story 3 — Teams contend for jobs (trailing-team-first) (Priority: P1) 🎯 MVP

As a competing team, I need a fair, deterministic rule for who wins a job two teams both want, so the board is genuinely fought over and a runaway leader can't also hoard the best jobs.

**Why this priority:** This is the headline "fought-over" value. It's P1 because the board's competitive identity depends on it; with multiple AI teams it is exercised every round.

**Independent Test:** Run `run-campaign --agent stub` with 4 teams. Each round, teams choose in ascending-banked-loot order; if two want the same job, the lower-banked team gets it and the other must choose again from what remains; each job is claimed by at most one team that round; claimed jobs join the consumed set.

**Acceptance Scenarios:**

1. **Given** 4 teams with distinct banked totals, **When** a round resolves, **Then** the pick order is ascending banked loot (lowest first), with a deterministic tiebreak (e.g. ai_idx).
2. **Given** two teams both prefer "The Casino Vault", **When** picks resolve, **Then** the lower-banked team is assigned it and the higher-banked team is re-prompted/falls back to its next choice among still-available board jobs.
3. **Given** a team's every preferred job was taken by earlier pickers, **When** its turn comes, **Then** it is assigned an available board job (its next viable choice) rather than nothing — every team that can run a job does.
4. **Given** a round completes, **When** the consumed set is inspected, **Then** every job a team attempted that round is now consumed and unavailable next round.

---

### User Story 4 — Progression gating + random wilds (Priority: P2)

As a player, I want the board to start with modest jobs and unlock bigger scores as the campaign goes on, with the occasional surprise, so there's a build-up arc and the jackpots feel earned but not perfectly predictable.

**Why this priority:** Improves pacing and the endgame payoff, but the board functions (US1–US3) without it — early boards would just be random draws.

**Independent Test:** Across many seeded campaigns, early-round boards skew to lower tiers, late-round boards include high tiers/jackpots; a minority of slots ("wilds") are drawn without the gate so a reach job or off-tier surprise can appear; every board still contains at least a couple of jobs the trailing team could afford.

**Acceptance Scenarios:**

1. **Given** round 1, **When** the board is built, **Then** the gated slots are drawn from the lower tiers (no elite jackpot in the gated slots), while wild slots may surface anything.
2. **Given** a late round with high total banked loot, **When** the board is built, **Then** high-tier/elite jobs are eligible for the gated slots.
3. **Given** any round, **When** the board is built, **Then** at least a configured minimum of "affordable" jobs (relative to the trailing team / a global floor) is present so no team is starved.
4. **Given** the same seed and standings, **When** a board is built twice, **Then** it is identical (deterministic).

---

### User Story 5 — Expanded job pool (~50) (Priority: P2)

As the game, I need a pool large enough that a 4-team, 10-round campaign (up to ~40 jobs consumed) never runs dry and the board stays varied, so contention and rotation keep working to the end.

**Why this priority:** Required for 4-team longevity, but US1–US4 are demonstrable on the existing 15 for short/few-team runs; content can land second.

**Independent Test:** Pool ≥ ~50 jobs; distribution weighted to easy/medium; all new jobs have complete content (flavor, profile, scene_loot, hidden_depth, reward_amounts, tier, art row) and pass all content invariants; a 4-team/10-round stub campaign completes without exhausting the board.

**Acceptance Scenarios:**

1. **Given** the pool, **When** counted, **Then** it has ~50 jobs with each of the 5 challenge categories well represented as a gating challenge.
2. **Given** every job, **When** validated, **Then** it satisfies all existing content tests (unique names, payable scene_loot, reward floor ≥ $1M, tier in {easy,medium,hard,elite}).
3. **Given** a 4-team 10-round stub campaign, **When** it runs, **Then** every round produces a full or near-full board and the campaign completes without error.

---

### User Story 6 — Board & claims in the viewer (Priority: P2)

As a viewer, I need to see the current board, which team grabbed which job (and who got out-bid), and that consumed jobs are gone, so the contested board reads clearly on replay.

**Why this priority:** The data exists (events) without UI; the browser view is important polish but not required for the engine to be correct.

**Independent Test:** In a campaign replay, each round renders its 8-job board; claims show the winning team per job; a team that lost a contested job shows its fallback; consumed jobs do not reappear. No board state is reconstructed client-side — it all comes from events.

**Acceptance Scenarios:**

1. **Given** a round's events, **When** the viewer renders, **Then** it shows exactly the 8 board jobs from the event stream (not the full pool).
2. **Given** claim events, **When** the viewer renders, **Then** each claimed job shows the owning team, and contested losses are visible.
3. **Given** a replay scrub across rounds, **When** moving forward, **Then** the board shrinks/refreshes consistently with the consumed set carried in the events.

---

### User Story 7 — Documentation truth-up (Priority: P3)

As a future contributor, I need the design doc and CLAUDE.md to match shipped reality, so the source-of-truth docs don't mislead.

**Why this priority:** Important hygiene; no runtime impact.

**Independent Test:** `heist_game_design.md` describes the 1–10 score model, the contested board, and reward-climb; CLAUDE.md "Locked Design Decisions" lists scores (not buckets), a 21-character roster, the correct phase, and the contested-board slate rule.

**Acceptance Scenarios:**

1. **Given** `heist_game_design.md`, **When** read, **Then** core mechanics describe hidden 1–10 scores with public buckets, score-margin resolution, +1-point collaboration, the scouting reveal ladder, and Phase 4 is marked built.
2. **Given** CLAUDE.md, **When** read, **Then** "Skill levels: Low/Medium/High only" and "Roster: 16 characters, locked" are corrected, and the contested job board + reward-climb model are documented.

---

## Edge Cases

- **Board runs low:** fewer than 8 unconsumed jobs remain → show all remaining; if fewer than the team count remain, teams without a job that round are handled gracefully (skip with an event, no crash).
- **All teams tied on banked loot** (e.g. round 1, all at starting bankroll) → deterministic tiebreak by ai_idx; pick order stable.
- **Two teams pick the same job, lower-banked wins** → higher-banked team re-resolves to its next available preference; if the AI named only the taken job, fall back to the cheapest/affordable available board job (system fills, as today's incomplete-pick fallback does).
- **A team can't afford anything on the board** → it can still attempt the cheapest available job (it may fail), or the system surfaces a "sat out" event; never a crash.
- **Resume mid-round:** the board, pick order, and consumed set are in the round snapshot, so a resumed campaign restores the exact board and contention state.
- **Single-team campaign:** contention is a no-op; the board still rotates and consumes (US1 behavior).
- **Determinism:** the same seed + standings must reproduce the same board and the same contention outcome (for replay/resume fidelity and tests).

---

## Requirements (Functional)

**Board state & rotation (US1)**
- **FR-001:** The campaign MUST maintain a global **consumed-jobs** set (job names attempted by any team), persisted across rounds.
- **FR-002:** Each round, the system MUST build a **board** of up to 8 jobs drawn only from the pool minus consumed jobs.
- **FR-003:** Board selection MUST be deterministic given the campaign seed, round index, and standings.
- **FR-004:** The AI MUST be offered only the current board for scouting and job selection (never the full pool).
- **FR-005:** When fewer than 8 unconsumed jobs remain, the board MUST contain all remaining unconsumed jobs without error.

**Reward climb (US2)**
- **FR-006:** Every job's clean take MUST be ≥ $1,000,000.
- **FR-007:** Job take MUST trend upward with difficulty (Hard-count primary, tier secondary); 4-Hard elite jobs MUST be the highest takes (≥ $15M each).
- **FR-007a:** The pool MUST include 1–2 deliberate "edge" jobs that deviate from the difficulty→reward trend (≥1 bargain above trend, ≥1 trap below).
- **FR-008:** Each job's `reward_range` MUST bracket the achievable take (≈ [0.55× … clean take + best hidden-depth bonus]) with a reachable top, and `scene_loot` MUST still pay into an active challenge category.

**Contention (US3)**
- **FR-009:** Each round, the system MUST compute a **pick order** = teams sorted by ascending banked loot, deterministic tiebreak by ai_idx.
- **FR-010:** Teams MUST claim board jobs in pick order; a job claimed by an earlier picker is unavailable to later pickers that round.
- **FR-011:** When a team's chosen job was already claimed, the system MUST resolve it to the team's next available board choice (AI re-prompt or system fallback to an affordable available job).
- **FR-012:** Each board job MUST be claimable by at most one team per round; all attempted jobs MUST join the consumed set after the round.
- **FR-013:** Every team that has a viable available job MUST be assigned one each round (no idle team while jobs remain).

**Gating & wilds (US4)**
- **FR-014:** Board composition MUST gate higher tiers/jackpots by campaign progression (round index and/or total banked loot), keeping elite jackpots out of early gated slots.
- **FR-015:** A configurable subset of board slots MUST be "wild" (drawn without the gate) for surprises, and each board MUST guarantee a minimum number of affordable jobs so no team is starved.

**Events, serialize & persistence (US1/US3/US6 — two-lane rule)**
- **FR-016:** The system MUST emit board/claim events: the round's board (the 8 jobs), the pick order, each team's claim, contested losses, and the updated consumed set.
- **FR-017:** The round snapshot MUST persist the board, pick order, claims, and consumed set so replay and mid-round resume restore exact state.
- **FR-018:** `serialize` MUST round-trip board/claim/consumed data; the viewer MUST render board state only from events (no client-side reconstruction).
- **FR-019:** `server` MUST broadcast the new events on the stream and append them to the persisted events buffer (no new route).

**Content scale (US5)**
- **FR-020:** The job pool MUST grow to ~50 jobs, weighted toward easy/medium, each with complete content and an art row, all passing content invariants.

**Documentation (US7)**
- **FR-021:** `heist_game_design.md` MUST be corrected to the 1–10 score model and document the contested board + reward-climb; Phase 4 marked built.
- **FR-022:** CLAUDE.md "Locked Design Decisions" MUST be corrected (scores not buckets, 21-char roster, phase, contested-board slate rule).

---

## Success Criteria

- **SC-001:** A 4-team, 10-round `run-campaign --agent stub` run completes with no traceback, a board each round, contention resolved, and jobs consumed globally.
- **SC-002:** No attempted job ever reappears on the board in a later round (0 repeats across a full campaign).
- **SC-003:** Sorted by Hard-count, band-median take is strictly ascending (0 < 1 < 2 < 4 Hards), pool minimum take ≥ $1M, and the two 4-Hard jobs are the top two takes.
- **SC-004:** Each round's board shows ≤ 8 jobs and ≥ the configured affordable minimum; the trailing (lowest-banked) team picks first 100% of rounds.
- **SC-005:** A killed-and-resumed campaign restores the identical board, pick order, and consumed set for the in-flight round.
- **SC-006:** Full preflight stays green: `ruff`, `mypy heist/ agents.py demo.py`, `pytest -q`.

---

## Key Entities

- **Job pool** (`heist/locations`): ~50 `Job`s (name, flavor, profile, tier, `scene_loot`, `reward_range`, `reward_amounts`, `hidden_depth`, art).
- **Board / slate:** per-round selection of ≤8 job names drawn from `pool − consumed`, plus gating/wild metadata.
- **Consumed set:** campaign-level set of attempted job names (persisted).
- **Pick order:** per-round ordering of teams (ascending banked loot, tiebreak ai_idx).
- **Claim:** mapping team (ai_idx) → claimed job for the round; plus contested-loss records.
- **Campaign state:** gains `consumed_jobs` and per-round board/claims snapshot fields.

## Assumptions

- "Banked loot" for pick order is each team's running banked total at the start of the round (the same value standings already track).
- "Affordable" for the starvation guard is a coarse heuristic from a job's difficulty/tier vs. the trailing team's bankroll (the reward proxy), not an exact crew-cost solve.
- The existing incomplete-pick fallback (system fills an unaffordable/empty pick) is reused for contention re-resolution rather than running a second AI round-trip per collision (keeps it to one job-pick call per team per round).
- Board size 8 and team cap 4 are constants (tunable); pool ~50 supports 4×10 consumption with buffer.
- New jobs reuse the existing portrait/art pipeline conventions (`heist/locations/locations_art.csv`).
