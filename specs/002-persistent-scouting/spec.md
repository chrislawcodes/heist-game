# Feature Specification: Scouting v2 — Two-Stage Hidden-Bucket Reveal (persistent + redesigned cards)

**Feature branch:** `feat/scout-persistence`
**Created:** 2026-05-26 (revised 2026-05-26 for the two-stage hidden-bucket model)
**Status:** Draft → Planning
**Input:** Make scouting the way a crew actually learns a location. A challenge's difficulty starts **fully hidden** — the crew doesn't even know the rough bucket. The **first** scout of a cell reveals its **bucket** (Low/Med/Hard); a **second** scout reveals the **exact 1-10**. Knowledge **persists** across a campaign (per team), and each job's true scores are **locked** for the whole campaign. The job cards show only what the crew actually knows: empty bars when unscouted, filled bars once the bucket is known, the exact number to the right once it's known — with the row briefly highlighted when scouted this turn. No magnifying glass.

---

## Overview

This revises the earlier "persistent scouting" spec. The persistence and locked-score parts stand; the **reveal model changes**.

**Before:** every job publicly advertised its per-cell bucket (Low/Med/Hard). Scouting jumped straight to the exact 1-10. Cards drew the public bucket as filled bars for every cell.

**Now (two-stage, hidden bucket):**
- A cell begins **HIDDEN** — the crew knows nothing about its difficulty (not even the bucket). It only knows the job's reward and that four challenge categories exist.
- **Probe #1** on a cell → **BUCKET**: the crew learns the rough Low/Med/Hard.
- **Probe #2** on the same cell → **EXACT**: the crew learns the precise 1-10 under that bucket.
- A probe advances exactly one level; fully knowing a cell costs two probes (possibly spread across rounds).

This makes scouting genuinely load-bearing: the AI now picks jobs nearly blind unless it scouts, and persistence means knowledge accumulates over a campaign (blind early, well-cased late). The engine already has the ladder — `RevealLevel` is `HIDDEN → BUCKET → EXACT` and `ScoutState.reveal()` advances one step; today's `apply_probes` jumps to EXACT and the slate is shown publicly, which is what this changes.

Locked design preserved: score buckets 1-3 Low / 4-7 Med / 8-10 High; +1-point collaboration; the steep heat cascade is untouched (this makes scouting its counterweight). Scouting remains locations-only; character scores stay public. Reward ranges stay public. Hidden-depth twists stay hidden regardless of scouting.

---

## User Scenarios & Testing

### User Story 1 — A job's difficulty is fixed for the whole campaign (Priority: P1) — BUILT

As the **game system**, I roll each job's hidden 1-10 challenge scores once at campaign start and reuse them every round.

**Status:** implemented (locked `Campaign.slate_scores`, conductor rolls once + shares, CLI reuses; tests green).

**Acceptance:** a job's scores are identical across rounds; a scouted value equals the locked value; all teams share identical locked scores.

---

### User Story 2 — Two-stage hidden reveal (Priority: P1) 🎯 MVP

As a **player (team)**, a cell starts fully hidden; my first scout of it tells me the bucket, my second tells me the exact number — so difficulty is something I *earn*, not something I'm handed.

**Why this priority**: This is the core mechanic change. Everything else (cards, the AI's job choice) depends on it.

**Independent Test**: In a stub campaign, probe a cell once → it's at BUCKET (bucket known, no exact). Probe it again → EXACT (number known). The AI's job-slate text shows nothing about an un-probed cell's difficulty.

**Acceptance Scenarios**:

1. **Given** an un-scouted cell, **When** the crew probes it once, **Then** its reveal level becomes BUCKET — the bucket is known, the exact number is not.
2. **Given** a cell already at BUCKET, **When** the crew probes it again, **Then** it becomes EXACT and the exact 1-10 is known.
3. **Given** a cell at EXACT, **When** probed again, **Then** it's a no-op and no probe is spent.
4. **Given** an un-probed cell, **When** the AI is shown the job slate to pick a job, **Then** that cell's difficulty (bucket and number) is **not** disclosed — only that the category exists.
5. **Given** the revealed bucket of a cell, **Then** it equals the published bucket of the cell's locked score (a "Hard" reveal corresponds to an 8-10 locked score).

---

### User Story 3 — Scouting persists across rounds at its level (Priority: P1) 🎯 MVP

As a **player (team)**, what I've learned stays learned: a cell I took to BUCKET last round is still at BUCKET this round (and a fresh probe can push it to EXACT); a cell at EXACT stays EXACT. Each round grants fresh probes for new progress. The replay shows my full accumulated knowledge.

**Why this priority**: Persistence is what makes the two-stage cost worth paying over a campaign.

**Independent Test**: Take a cell to BUCKET in round 0; in round 1 it's still BUCKET with no probe spent, and one probe there advances it to EXACT. A second team that didn't scout it still sees it HIDDEN.

**Acceptance Scenarios**:

1. **Given** team A took `(Museum, physical)` to BUCKET in round 0, **When** round 1 begins, **Then** A still knows that bucket with no probe spent, and the round-1 replay shows it.
2. **Given** A's cell is at BUCKET entering round 1, **When** A probes it once more, **Then** it advances to EXACT (carry + advance compose correctly).
3. **Given** A knows a cell but team B does not, **When** round-1 replays render, **Then** A's card shows it and B's shows it hidden.
4. **Given** a probe re-issued for an EXACT cell, **Then** it is a no-op consuming no probe.

---

### User Story 4 — Job cards show only what the crew knows (Priority: P1) 🎯 MVP

As the **player watching**, each job card's four challenge rows reflect my knowledge: empty bars when hidden, bars filled to the bucket once known, the exact number to the right once known — with a brief highlight on rows I scouted this turn. No magnifying glass.

**Why this priority**: This is the visible payoff and what the user asked for; the engine work is invisible without it.

**Independent Test**: In a replay, an un-scouted row shows empty bars and no number; after a bucket reveal it shows filled bars; after an exact reveal it shows bars + the number to the right; a row revealed this turn is highlighted.

**Acceptance Scenarios**:

1. **Given** a hidden cell, **When** the card renders, **Then** the row shows empty bars and no number.
2. **Given** a bucket-known cell, **When** the card renders, **Then** the bars fill to the bucket level (None 0 / Low 1 / Med 2 / Hard 3) with no number.
3. **Given** an exact-known cell, **When** the card renders, **Then** the bars fill to the bucket **and** the exact 1-10 shows to the right of the bars.
4. **Given** a cell revealed during this round, **When** the card renders, **Then** its row carries a subtle highlight (outline or low-opacity tint); carried-over reveals from prior rounds are not highlighted.
5. **Given** any cell, **When** the card renders, **Then** there is no magnifying-glass icon anywhere.

---

### User Story 5 — Resume keeps locked scores + reveal levels (Priority: P2)

As the **game system**, a resumed campaign restores the locked scores and each team's per-cell reveal **levels** (HIDDEN/BUCKET/EXACT) and exact scores, with no re-roll, loss, or double-count.

**Independent Test**: take cells to BUCKET and EXACT in round 0, stall, resume — round 1 shows the identical levels and locked scores.

**Acceptance Scenarios**:

1. **Given** a campaign with mixed BUCKET/EXACT reveals before a stall, **When** resumed, **Then** every cell's level and exact score is restored exactly and scores are not re-rolled.
2. **Given** a legacy campaign with no stored locked scores, **When** resumed, **Then** scores initialize once and it continues without error.

---

## Edge Cases

- **None-difficulty cell** → scouting it once reveals bucket NONE (0 bars); a second probe reveals exact 0. The crew can't tell a None cell from a deadly one until they scout (full fog).
- **Out of probes mid-cell** → a cell at BUCKET stays BUCKET; it's finished to EXACT in a later round (persistence makes this fine).
- **Re-probe an EXACT cell** → no-op, no probe spent.
- **Resume between scout turn and job pick** → reveal levels neither lost nor advanced twice; budget not refunded/re-spent.
- **Legacy campaign** (pre-feature) → no stored locked scores → rolled once on first access; no crash.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST roll each job's hidden 1-10 scores once per campaign and reuse them every round (campaign-global). *(US1 — built)*
- **FR-002**: A challenge cell MUST begin HIDDEN — neither bucket nor exact known to any team until scouted. *(US2)*
- **FR-003**: A probe on a cell MUST advance its reveal level by exactly one step (HIDDEN→BUCKET→EXACT) and spend exactly one free probe; a probe on an EXACT cell MUST be a no-op spending nothing. *(US2)*
- **FR-004**: A BUCKET reveal MUST disclose only the bucket (derived from the locked score); the exact 1-10 MUST remain undisclosed until a second probe takes the cell to EXACT. *(US2)*
- **FR-005**: The AI's job-slate prompt MUST disclose a cell's bucket only at BUCKET+ and the exact only at EXACT; HIDDEN cells MUST disclose neither. *(US2)*
- **FR-006**: Each team's per-cell reveal levels and exact scores MUST persist across rounds; a fresh per-round free-probe budget is granted; carried knowledge is never re-paid. *(US3)*
- **FR-007**: At the start of each round the engine MUST emit the team's carried-forward reveals (at their level) so the replay shows cumulative knowledge; the browser MUST NOT reconstruct it. *(US3)*
- **FR-008**: Job cards MUST render each challenge row from the team's reveal state only — empty bars at HIDDEN, bucket-filled bars at BUCKET, bucket-filled bars + exact number to the right at EXACT — NOT from the job's public profile. *(US4)*
- **FR-009**: A row whose reveal advanced **this round** MUST carry a subtle highlight; carried-over reveals MUST NOT. There MUST be no magnifying-glass icon. *(US4)*
- **FR-010**: Locked scores + per-cell reveal levels + exact scores MUST serialize and survive a mid-campaign resume with no re-roll, loss, or double-count; legacy campaigns initialize locked scores once. *(US5)*
- **FR-011**: System MUST NOT change score buckets, +1 collaboration, or soften the heat cascade. Reward ranges stay public. Scouting stays locations-only. Hidden-depth stays hidden. *(Guardrail)*

### Key Entities

- **Locked slate scores** — `{job → {category → 1-10}}`, campaign-global, rolled once. *(built)*
- **Per-team scout reveals** — `ScoutState.reveals: {job → {category → RevealLevel}}` (HIDDEN/BUCKET/EXACT) + `exact_scores: {job → {category → 1-10}}` (only at EXACT). Persists across rounds.

---

## Success Criteria

- **SC-001**: A job's challenge scores are identical every round (zero variance). *(built)*
- **SC-002**: One probe takes a HIDDEN cell to BUCKET (bucket known, exact unknown); a second takes it to EXACT.
- **SC-003**: An un-probed cell's difficulty never appears in the AI's job-slate prompt or on its card.
- **SC-004**: A cell's reveal level is retained in every later round for that team with zero extra probes to retain it.
- **SC-005**: Resume preserves 100% of each team's reveal levels + exact scores and identical locked scores; no probe/loot double-count.
- **SC-006**: Cards show empty/bucket/exact correctly; this-turn reveals are highlighted; no magnifying glass anywhere.

---

## Assumptions

- The four challenge categories (electronic/physical/confrontation/social) are always shown as rows; only their difficulty is fogged. Reward range stays public.
- The revealed bucket is derived from the locked score (`score_to_bucket`), so it always agrees with the eventual exact.
- Hidden depth stays per-round and never revealed by scouting (FR-011).
- Single-job (non-campaign) play: the two-stage reveal applies within the run; locking/persistence are campaign concepts.
