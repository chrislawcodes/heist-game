# Feature Specification: Persistent Scouting in Campaigns

**Feature branch:** `feat/scout-persistence`
**Created:** 2026-05-26
**Status:** Draft → Planning
**Input:** Make scouting a lasting investment across a campaign. Lock each job's hidden 1-10 challenge scores once at campaign start (no per-round re-roll), and carry each team's scouted-cell reveals forward across all rounds so a location scouted once stays known to that team for the rest of the campaign. The per-round replay must show the team's cumulative scouted cells. Must not break campaign save/resume.

---

## Overview

Today a campaign restarts scouting from zero every round: `runner.run_one_job` calls `roll_slate_scores` to re-roll every job's hidden scores, and builds a fresh blank `ScoutState`. The `Campaign` object carries crew, loot, and round results forward — but nothing about scouting. So a probe a team spends in round 1 teaches it nothing for round 2, and even if the reveal carried over the underlying number would have changed.

This feature makes scouting **persist**, under the user-confirmed "lock scores per campaign" model:

1. **Locked scores** — a job's hidden 1-10 difficulties are rolled **once** at campaign start and reused unchanged for every round. They are **campaign-global**: identical for every team.
2. **Per-team scouting memory** — once a team scouts a `(job, category)` cell, that exact score stays known to **that team** for the rest of the campaign. Each round still grants fresh free probes to learn *more* cells; known cells need no re-probe.

Because the engine owns the event stream (the project's two-lane rule), the carried-forward reveals must be **emitted by the engine** at the start of each round so the existing replay viewer shows them — the browser never reconstructs game state.

The high-risk surface is **campaign save/resume**: campaigns checkpoint and can resume mid-flight (`orchestration.run_campaign_conductor`, `checkpoint_version`, `game_states`, `campaign_to_dict`/`campaign_from_dict`). The new persisted state must serialize and survive a resume without re-rolling scores, losing reveals, or double-counting probes.

This is sequenced MVP-first with a staging review between phases.

---

## User Scenarios & Testing

### User Story 1 — A job's difficulty is fixed for the whole campaign (Priority: P1)

As the **game system**, I roll every job's hidden 1-10 challenge scores once when the campaign begins and reuse those same numbers in every round — so a team's knowledge of a location stays true and scouting is worth doing.

**Why this priority**: Foundation. Persisting a scouted number is meaningless if the number changes underneath it next round. Nothing else in this feature is coherent without locked scores.

**Independent Test**: Run a 2+ round stub campaign; capture each job's challenge scores in round 1 and round 2; they must be identical.

**Acceptance Scenarios**:

1. **Given** a fresh campaign, **When** round 1 and round 2 run, **Then** every job on the slate has the exact same hidden challenge scores in both rounds.
2. **Given** a job that was attempted in round 1, **When** it appears on the slate again in round 2, **Then** its hidden scores are unchanged.
3. **Given** the locked scores were rolled at campaign start, **When** any team scouts a cell, **Then** the revealed value equals the locked value for that cell (no divergence between teams).

---

### User Story 2 — Once a team scouts a location, it stays scouted for that team (Priority: P1)

As a **player (team)**, I keep what I learn: a cell I scouted in an earlier round is still known to me in every later round without spending another probe, and the replay shows everything I currently know — not just what I probed this round.

**Why this priority**: This is the user's actual request and the core value. Scouting becomes a cumulative, lasting investment that counters the heat cascade.

**Independent Test**: In a stub campaign, have a team scout cell X in round 1. In round 2, verify (a) X is already known to that team without a new probe, (b) the round-2 replay shows X's score, and (c) a different team that did *not* scout X does not know it.

**Acceptance Scenarios**:

1. **Given** team A scouted `(Museum, physical)` in round 1, **When** round 2 begins, **Then** team A already knows `(Museum, physical)` and spends no probe to keep it.
2. **Given** team A enters round 2 already knowing 2 cells and is granted 3 fresh probes, **When** it scouts 3 new cells, **Then** at the job-pick it knows 5 cells total.
3. **Given** team A knows `(Museum, physical)` but team B does not, **When** round 2's replays render, **Then** team A's job tab shows that cell and team B's does not.
4. **Given** a team re-issues a probe for a cell it already knows, **When** the probe is applied, **Then** it is a no-op and no free probe is consumed.

---

### User Story 3 — A resumed campaign keeps its locked scores and scouting memory (Priority: P2)

As the **game system**, when a campaign stalls and is resumed, I restore the same locked scores and every team's accumulated scouting memory exactly — without re-rolling, losing intel, or double-counting probes or loot.

**Why this priority**: Resume is an existing, load-bearing capability. The mechanic in US1/US2 can be demonstrated without a mid-campaign crash, but shipping it must not regress resume — so this is a hard correctness requirement that rides just behind the MVP.

**Independent Test**: Start a campaign, run round 1 with some scouting, force a stall after round 1, resume, and confirm round 2 sees the identical locked scores and the team's round-1 reveals intact.

**Acceptance Scenarios**:

1. **Given** a campaign that completed round 1 with scouting, **When** it is resumed, **Then** the locked scores are byte-identical to before and are not re-rolled.
2. **Given** team A had scouted 2 cells before the stall, **When** the campaign resumes, **Then** team A still knows exactly those 2 cells.
3. **Given** a campaign created before this feature existed (no stored locked scores), **When** it is resumed, **Then** locked scores are initialized once and the campaign continues without error.

---

## Edge Cases

- **Job attempted, then re-offered** → locked scores stay the same (campaigns use the full job list every round; locking is per-campaign, not per-attempt).
- **Team with no driver / zero free probes this round** → keeps all previously-known cells; simply learns nothing new this round.
- **Resume between the scout turn and the job pick** → carried-forward reveals are neither lost nor duplicated; probe budget is not refunded or re-spent.
- **Legacy campaign with no stored locked scores** → roll once on first access and persist (back-compat; no crash).
- **Re-probing a known cell** → no-op, no probe spent (existing `apply_probes` guard, now applied across rounds).
- **A team eliminated mid-campaign** → its scouting memory is irrelevant going forward; no special handling required.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST roll each job's hidden 1-10 challenge scores exactly once per campaign and reuse the identical values for every round. (Supports US1)
- **FR-002**: Locked scores MUST be campaign-global — the same for every team in the campaign. (Supports US1)
- **FR-003**: System MUST persist each team's scouting memory (revealed cells and their exact scores) on that team's campaign state across rounds. (Supports US2)
- **FR-004**: At the start of each round, each team MUST already know every cell it scouted in any prior round, with no probe spent to retain it. (Supports US2)
- **FR-005**: Each round MUST still grant a fresh free-probe budget (crew size + best-driver bonus) usable on cells not yet known. (Supports US2)
- **FR-006**: Applying a probe to a cell the team already knows MUST be a no-op that consumes no free probe. (Supports US2)
- **FR-007**: At the start of each round the engine MUST emit the team's carried-forward known cells as events so the replay viewer shows the cumulative set; the browser MUST NOT reconstruct this. (Supports US2)
- **FR-008**: The AI's scout and job-pick prompts MUST reflect already-known cells, so a team does not waste probes re-scouting and can reason over its full accumulated intel. (Supports US2)
- **FR-009**: Locked scores and per-team scouting memory MUST serialize through the campaign's existing save format and survive a mid-campaign resume with no re-roll, no lost reveals, and no double-counting of probes or loot. (Supports US3)
- **FR-010**: A campaign persisted before this feature (no stored locked scores) MUST initialize its locked scores once on first access and resume without error. (Supports US3)
- **FR-011**: System MUST NOT change the score buckets (1-3 Low / 4-7 Medium / 8-10 High), the +1-point collaboration rule, or soften the heat cascade. (Guardrail)
- **FR-012**: Scouting MUST remain locations-only; character scores stay public and unaffected. (Guardrail)
- **FR-013**: Scouting MUST reveal only the exact scores of a job's **published** challenge categories. Hidden challenges and the hidden-depth twist (`_roll_hidden_depth`) MUST stay hidden even for a fully-scouted job, in every round — persistence never lifts that fog. (Guardrail)

### Key Entities

- **Locked slate scores** — `{job_name → {category → 1-10 score}}`, rolled once and stored at the **campaign (game-record) level**, shared by all teams. Replaces the per-round `roll_slate_scores` call inside `run_one_job`.
- **Per-team scouting memory** — the persistent portion of `ScoutState` (`reveals` + `exact_scores`) attached to each team's `Campaign`/team-state and threaded forward each round. The free-probe budget remains per-round.

---

## Success Criteria

- **SC-001**: Across a 3-round campaign, each job's challenge scores are identical in every round (zero variance round-to-round).
- **SC-002**: A cell scouted in round 1 is shown as known in every later round for that team, with zero additional probes spent to retain it.
- **SC-003**: Resuming a campaign mid-way preserves 100% of each team's prior reveals and the identical locked scores; loot and probe counts are unchanged by the resume.
- **SC-004**: A team never spends a free probe to re-learn a cell it already knows.
- **SC-005**: One team's scouting memory never appears for another team.

---

## Assumptions

- **Hidden depth stays per-round AND stays hidden.** The per-run complication/opportunity element (`_roll_hidden_depth`) is a separate "surprise during the run" mechanic and is **out of scope** — it continues to roll fresh each round, and scouting never reveals it. Only the slate's **published** challenge cells get locked-and-scoutable scores; the hidden challenges remain hidden however much a team scouts (see FR-013).
- **Locked scores are stored explicitly**, rolled at campaign start (or lazily on first access for legacy campaigns) and saved — not re-derived from a seed at read time, to avoid drift.
- **Character scores remain public** and unchanged; scouting applies to locations only.
- **Single-job (non-campaign) play is unchanged** — locking and persistence are campaign concepts; the standalone `run_heist` path keeps its current per-run behavior.
