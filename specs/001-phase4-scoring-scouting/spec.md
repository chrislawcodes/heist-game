# Feature Specification: Phase 4 — Hidden Location Info & Scouting (Score-Based Resolution)

**Feature branch:** `feat/phase4-scoring-scouting`
**Created:** 2026-05-26
**Status:** Draft → Planning
**Input:** Phase 4 of the heist game. Replace the Phase 1-3 bucketed skill/challenge model with hidden 1-10 scores under public Low/Med/High buckets, true-score resolution, score-based crew pricing, +1-point collaboration, a tiered job ladder, a decoupled reward model, and a scouting system that lets the player buy down location uncertainty. Scoring and scouting ship as one package.

---

## Overview

Today the whole slate is laid bare and all mechanics resolve on three coarse buckets (Low/Medium/High vs None/Low/Medium/Hard). Phase 4 moves the engine to a hidden **1-10 score** for every skill and challenge, keeps only the **bucket** as a public label, and gives the player **scouting** to learn the truth before committing. A published "High" becomes an *estimate, not a contract*.

This supersedes the Phase 1-3 graded bucket comparison ("Hard requires High") — resolution now reads true scores. Character scores are **public** (scouting applies to **locations only, never people**). Location defenses are **fogged** until scouted.

This is a large, migration-heavy change that touches the data model, mechanics, content (all jobs + all characters), the AI prompts, serialization, the campaign loop, and the viewer. It is sequenced so the **scoring engine (P1)** lands first without breaking existing play, then **scouting (P2)**, then **content/economy polish (P3)**.

---

## User Scenarios & Testing

### User Story 1 — True-score resolution, pricing, and collaboration (Priority: P1)

As the **game system**, I resolve every challenge by comparing the crew's true effective skill *score* to the challenge's true *score*, price crew off their scores, and grant collaboration as a flat +1 point — so that a published bucket is an estimate, not a guarantee, and the whole economy rests on the 1-10 spine.

**Why this priority:** This is the deterministic foundation Phase 4 is built on. Scouting, tiers, and the reward model all read these scores. Nothing else in Phase 4 can be built or tested until resolution and pricing run on scores. It must replace the bucket model *without breaking* existing single-job and campaign play.

**Independent Test:** Run a stub heist and a stub campaign end-to-end. Verify (a) every character's `skill_scores` is populated and matches the locked table; (b) each crew member's floor cost equals the pricing curve; (c) a challenge resolves by `effective_score >= challenge_score`; (d) two crew in the same skill produce `best_score + 1` (capped 10); (e) graded outcomes (clean/squeak/fail/caught) and heat still emit, keyed off the score margin; (f) the escape still resolves on the rescaled driver score.

**Acceptance Scenarios:**

1. **Given** a crew member with Safecracker score 9, **When** the system prices them, **Then** their floor cost is `$100k seat + $600k premium = $700k`.
2. **Given** a crew with two Inside Man members at scores 7 and 6, **When** the system computes effective Inside Man, **Then** it returns 8 (best 7, +1, capped 10).
3. **Given** an effective skill score of 8 against a hidden challenge score of 9, **When** the system resolves, **Then** the attempt fails (8 < 9) and heat rises per the graded mapping.
4. **Given** an effective skill score of 10 against a challenge score of 8, **When** the system resolves, **Then** the attempt is a clean pass.
5. **Given** an existing stub campaign, **When** it runs under the new engine, **Then** it completes 3 rounds with no crash and emits the same event types the viewer already consumes.

---

### User Story 2 — Scout a location to learn its defenses (Priority: P2)

As a **player (via my strategy prompt and the Heist AI)**, I want my crew to scout locations before committing — learning each defense's bucket, and paying down further to the exact number — so that I can right-size my crew instead of gambling on what a "Hard" really hides.

**Why this priority:** Scouting is the intelligence game that makes hidden scores *fair* (the locked "adversity must feel fair" principle). Without it, fogged defenses are arbitrary punishment. It is the second half of the one package, and depends on US1's scores existing.

**Independent Test:** In a campaign round's scouting phase, confirm: a free probe on `(location, category)` reveals that category's **bucket**; a second probe on the same target reveals the **exact 1-10 score**; free-probe count equals `crew size + best-driver bonus (+1/+2/+3 for Low/Med/High driver)`; probes beyond the free allotment cost **$100k** each; revealed intel is available to the Heist AI when it picks and runs the job that round.

**Acceptance Scenarios:**

1. **Given** a 4-member crew whose best driver is a Medium (bonus +2), **When** the scouting phase opens, **Then** the crew has `4 + 2 = 6` free probes that round.
2. **Given** an unscouted location, **When** one free probe targets `(location, electronic)`, **Then** the electronic **bucket** is revealed and the other categories stay fogged.
3. **Given** a location whose electronic bucket is already revealed, **When** a second probe targets `(location, electronic)`, **Then** the exact 1-10 electronic score is revealed.
4. **Given** a crew that has spent all free probes, **When** it requests one more probe, **Then** the system charges $100k and (if affordable) grants the probe; if unaffordable, the probe is refused.
5. **Given** a location scouted to exact on its gating challenge, **When** the Heist AI assembles and runs the job, **Then** it can choose crew with a comfortable margin against the now-known score.

---

### User Story 3 — Experience the fog in the viewer (Priority: P2)

As a **spectator**, I want the viewer to show what's known versus fogged — public flavor and reward range, hidden defense buckets, and intel as it's revealed by scouting — so that the tension of committing under uncertainty is visible and legible.

**Why this priority:** Phase 4's drama is the fog; if the UI still shows everything, the mechanic is invisible to the watcher. Depends on US1/US2 emitting the fogged/revealed state on the event stream.

**Independent Test:** Open a campaign replay. Before scouting, a location shows flavor + reward range but its defense categories read as unknown. After a scouting probe event, the scouted category shows its bucket (then exact, after a second probe). No defense exact number appears that wasn't scouted.

**Acceptance Scenarios:**

1. **Given** an unscouted location on the slate, **When** the viewer renders it, **Then** defense categories display as fogged and the reward **range** displays as public.
2. **Given** a `scouted` event revealing a bucket, **When** the viewer processes it, **Then** that category updates from fogged to its bucket label.
3. **Given** a `scouted` event revealing an exact score, **When** the viewer processes it, **Then** that category shows the precise 1-10 value.

---

### User Story 4 — Tiered job ladder and mispriced "edge" jobs (Priority: P3)

As a **player building a crew over a campaign**, I want jobs that span an easy-to-hard ladder and whose reward is *correlated with but not locked to* their difficulty — so that early rounds are doable with a starter crew, late rounds demand a built crew, and a good scout can uncover an underdefended treasure.

**Why this priority:** Enhancement and content. The engine and scouting work without it, but it delivers the build-over-time arc and the "find the steal" payoff. Larger content lift; sequenced last.

**Independent Test:** With an expanded pool, confirm: each job carries a `tier` (1/2/3); Tier-1 jobs demand 0 High specialists, Tier-2 demand 1, Tier-3 demand 2-3; a Hard's hidden score is drawn from the tier's fog band (T1→{8}, T2→{8,9}, T3→{9,10}); each of the five skills gates a fair share across the pool; and at least one job rolls a high reward range over below-trend defenses (a scoutable edge).

**Acceptance Scenarios:**

1. **Given** a Tier-1 job, **When** its hidden challenge scores roll, **Then** no challenge exceeds the Medium band (and any Hard is exactly 8).
2. **Given** a Tier-3 job, **When** its scores roll, **Then** its gating Hard challenges roll in {9,10}.
3. **Given** the reward model, **When** a job's prize and defenses roll, **Then** they are positively correlated but with slack, so some high-reward jobs are below-trend defended.
4. **Given** an edge job scouted to exact, **When** the Heist AI evaluates it, **Then** it can recognize a high prize behind soft defenses and commit a cheaper crew.

---

### User Story 5 — A second Medium Hacker for electronic resilience (Priority: P3)

As a **player**, I want a second Medium-tier Hacker on the roster so that electronic-Hard jobs are not strictly "own Marcus or fail," giving electronic a collaboration fallback like the other skills and adding auction/campaign resilience.

**Why this priority:** Targeted content fix for the one skill with no two-medium path to Hard. Improves resilience and auction depth but isn't required for the engine; grows the roster from 16 to 17.

**Independent Test:** The roster contains 17 characters; the new hacker has a Hacker score of 6 or 7, a full authored personality, a floor cost matching the pricing curve, and a portrait; two medium hackers can collaborate to an effective 7-8.

**Acceptance Scenarios:**

1. **Given** the updated roster, **When** it loads, **Then** there are 17 characters and at least two with a Medium-band Hacker score.
2. **Given** the new hacker (score 7) paired with Sasha (score 6) on electronic, **When** effective skill computes, **Then** it returns 8 — a collaboration path to a Hard-8.

---

## Edge Cases

- **No driver on the crew** → scouting still grants `crew size` free probes (driver bonus is +0); the escape treats a missing driver as the existing "Low" floor, rescaled to scores.
- **Probe on an already-exact target** → no further reveal; the probe is rejected or no-ops without charging (must not silently waste a paid probe).
- **Bankroll too low for a paid probe** → request refused; the round proceeds on whatever intel is free.
- **A "High" that is really an 8 vs a "Hard" that is really a 10** → the published buckets both read plausibly attemptable, but the attempt fails on true scores; this must feel fair *because* scouting was available.
- **Collaboration cap** → two 10s (or any pair summing past 10) cap at 10, never exceed.
- **Tie on scores** (`effective == challenge`) → defined as a pass, but the *graded* outcome is the heat-costing "squeak," preserving the knife-edge.
- **Existing saved games / in-flight snapshots** created under the bucket model → must not crash the loader; either migrate or fail gracefully (see Assumptions).
- **A job re-appearing in a later round** (full-JOBS-every-round model) → its hidden scores roll fresh for that round; scouting intel is per-round, not carried (see Assumptions).
- **Reward range published but exact fogged** → the viewer never shows an exact prize that wasn't scouted; the Heist AI plans against the range unless it scouted the amount.

---

## Requirements

### Functional Requirements — Scoring engine (US1)

- **FR-001:** Every character MUST carry a public 1-10 `skill_scores` entry for each skill they possess, matching the locked table in *Key Entities*. Buckets are derived: 1-3 Low, 4-7 Medium, 8-10 High.
- **FR-002:** The system MUST compute a crew's effective skill in a category as the highest member score in that category, **plus 1 if two or more members have the skill**, capped at 10 (replaces the old "+1 bucket level" rule).
- **FR-003:** The system MUST resolve a challenge as a pass when `effective_score >= challenge_score`, reading true scores (replaces the bucket comparison).
- **FR-004:** The system MUST preserve graded outcomes (clean / squeak / fail / caught) and their heat/capture consequences, keyed off the **score margin** (`effective_score − challenge_score`). Exact margin thresholds are a planning-phase decision; the heat cascade MUST remain steep (it is intentionally so — see Assumptions).
- **FR-005:** The system MUST compute floor cost as `$100,000 seat + Σ premium(score)` where `premium` is: 1-3 → $0, 4 → $25k, 5 → $50k, 6 → $100k, 7 → $175k, 8 → $325k, 9 → $600k, 10 → $1,100k. The legacy `base_cost`/`expected_floor_cost` (points-based + High premium) MUST be replaced. Resulting costs MUST match *Key Entities*.
- **FR-006:** The escape MUST resolve on the rescaled 1-10 driver score against an escape difficulty expressed on the same scale (incorporating escape modifier + heat). The rescaling MUST preserve the existing knife-edge (a blown escape is the campaign's attrition source). Exact rescaling is a planning-phase decision.
- **FR-007:** Existing single-job (`run_heist`) and campaign (`run_campaign`) flows MUST continue to run end-to-end under the new engine and emit the event types the viewer already consumes.

### Functional Requirements — Hidden challenge scores (US1/US4)

- **FR-008:** Every job MUST carry hidden 1-10 `challenge_scores` for each active challenge category, rolled at the start of the round in which the job is offered.
- **FR-009:** A challenge's hidden score MUST be drawn from a band determined by its bucket and the job's tier: Tier-1 Hard → {8}, Tier-2 Hard → {8,9}, Tier-3 Hard → {9,10}; Medium and Low bands defined analogously in planning.
- **FR-010:** Only the **bucket** of a challenge is ever derivable for free; the exact score is revealed only by scouting (US2) — and is never knowable for *characters* in reverse (character scores are public; location scores are fogged).

### Functional Requirements — Scouting (US2)

- **FR-011:** Before committing to a job each round, the system MUST grant the crew a free probe allotment equal to `crew size + best-driver bonus`, where the bonus is +1 (Low driver), +2 (Medium), +3 (High), using the best single driver's bucket.
- **FR-012:** A probe MUST target a `(location, challenge-category)` pair. The first probe on a target reveals that category's **bucket**; a second probe on the same target reveals the **exact 1-10 score**. Both are free if within the allotment.
- **FR-013:** Probes beyond the free allotment MUST cost **$100,000** each, deducted from bankroll; a probe that cannot be paid for MUST be refused without side effects.
- **FR-014:** Revealed intel MUST be available to the Heist AI when it selects, crews, and runs the job that round, and MUST be emitted on the event stream as `scouted` events for the viewer.
- **FR-015:** The reward **range** MUST remain public (the aiming reticle); the **exact** reward amount MAY be revealed by scouting (a reward-dimension probe) but is otherwise fogged.

### Functional Requirements — Reward model (US4)

- **FR-016:** A job's prize and its defenses MUST be generated as positively correlated but *not identical* (correlation with slack), so that under- and over-defended jobs exist relative to their prize. Baseline per-cleared-challenge loot follows `Reward(C) ≈ 2930 × 2^C` ($100k@5, $200k@6, $375k@7, $750k@8, $1.5M@9, $3M@10).
- **FR-017:** Each job MUST carry a `tier` (1/2/3) reflecting how many High specialists it demands (0 / 1 / 2-3). The job pool SHOULD expand toward ~12-15 jobs, with each of the five skills gating a fair share across the pool.

### Functional Requirements — Content & roster (US5)

- **FR-018:** The roster MUST add one new Medium Hacker (Hacker score 6-7) with a fully authored personality (backstory, voice, motivation, quirk, crew dynamic, weakness, look, signature line) and a portrait, growing the roster to 17. Its floor cost MUST follow the pricing curve.

### Functional Requirements — Docs

- **FR-019:** `heist_game_design.md` MUST be updated to reflect: bucket boundaries (1-3 Low / 4-7 Med / 8-10 High), collaboration = +1 point, score-based resolution superseding the bucket model, scouting applies to **locations only**, the tier ladder, and the decoupled reward model.

---

## Success Criteria

- **SC-001:** A full stub campaign (3 rounds) and a full stub single-job run complete without error under the new engine, with all 17 characters priced by the curve.
- **SC-002:** For every character, the displayed floor cost equals `seat + Σ premium(score)` to the dollar.
- **SC-003:** Across 100 simulated resolutions, outcomes are exactly determined by `effective_score` vs `challenge_score` (no randomness in the contest itself), and the graded outcome matches the margin mapping every time.
- **SC-004:** Two same-skill crew members always produce effective `min(best+1, 10)`.
- **SC-005:** In a scouting phase, the free probe count equals `crew size + driver bonus` for every driver tier, and the first/second probe on a target yields bucket/exact respectively.
- **SC-006:** A player who scouts a job's gating challenge to exact can field a crew that clears it on the first attempt at least as reliably as a fully-margined blind crew, at lower crew cost — demonstrating scouting's value.
- **SC-007:** At least one job in the pool presents a high reward range over below-trend defenses, and scouting reveals it as an edge.
- **SC-008:** The viewer never displays a location's exact defense score or exact reward that was not scouted.

---

## Key Entities

### Locked character skill scores (public)

| Character | Skills (score) | Floor cost |
|-----------|----------------|-----------:|
| Marcus "Prodigy" | Hacker 10, Driver 2 | $1,200k |
| Lin "Closer" | Inside 9, Safe 2 | $700k |
| Rook | Safe 9 | $700k |
| Slim | Driver 9 | $700k |
| Vance "The Wall" | Muscle 8 | $425k |
| Pearl | Inside 7, Muscle 2 | $275k |
| Sasha | Hacker 6 | $200k |
| Carla | Muscle 6, Driver 3 | $200k |
| Theo | Inside 6 | $200k |
| Jo | Safe 6, Hacker 3 | $200k |
| Val | Muscle 6, Inside 3 | $200k |
| Margot | Driver 6, Inside 2 | $200k |
| Nestor | Safe 5, Hacker 2 | $150k |
| Dex | Driver 4, Muscle 2 | $125k |
| Eli "Owl" | Hacker 2, Inside 3 | $100k |
| Big Mike | Muscle 2, Driver 3, Inside 2 | $100k |
| *(new) Medium Hacker* | Hacker 6-7 (+ optional Low rider) | per curve |

### Pricing curve

`floor_cost = $100,000 + Σ premium(score)`; `premium`: {1-3: $0, 4: $25k, 5: $50k, 6: $100k, 7: $175k, 8: $325k, 9: $600k, 10: $1,100k}.

### Reward curve (baseline, per cleared challenge)

`Reward(C) ≈ 2930 × 2^C` → $100k@5, $200k@6, $375k@7, $750k@8, $1.5M@9, $3M@10. Job total ≈ Σ over its challenges, then perturbed by the correlation-with-slack model (FR-016).

### Data model touch points (already seeded)

- `Character.skill_scores: dict[str,int]` — exists, currently empty → **populate (public)**.
- `Job.challenge_scores: dict[str,int]` — exists, currently empty → **populate per-round (hidden)**.
- `Job.tier: str` — exists → use for tier band + fog band.
- New: per-location/per-round **scout state** (which `(location, category)` are revealed, and to bucket vs exact), and a per-round **free-probe budget** derived from crew + driver.

---

## Assumptions

1. **No notoriety / rolling slate in scope.** Commit #68 removed notoriety, the rolling slate, and attempted-job tracking; campaigns use the full `JOBS` list every round. Phase 4 keeps that model. Tiers are a job attribute and a fog-band driver — *not* notoriety-gated. (Notoriety-gated tiers remain a future Phase 3e item.)
2. **Scouting is a within-round phase, no cross-round persistence.** Because scores roll per round in the full-JOBS model, the crew scouts the current round's slate and attacks the same round; intel is not carried between rounds. This drops the "lock per slate-appearance / persist" machinery from the earlier design discussion.
3. **Graded outcomes survive on score margin.** Clean/squeak/fail/caught + heat are preserved (not collapsed to binary), keyed off `effective_score − challenge_score`. Default margin thresholds (to be confirmed in planning): margin ≥ 2 → clean; margin 0-1 → squeak (+1 heat); margin −1 to −2 → fail (+1 heat); margin ≤ −3 → caught (+1 heat, lose a member). The heat cascade stays intentionally steep (project memory: do not soften it).
4. **Escape moves to scores with the knife-edge intact.** Driver score (1-10) vs an escape difficulty rescaled to the 1-10 world (from escape modifier + heat). Exact rescaling defined in planning; a blown escape must still credibly catch a crew member.
5. **Reward decoupling (FR-016) is sequenced last (P3).** The engine may ship first with reward still derived from challenge scores; the correlation-with-slack refinement layers on after, since it is a generative tuning change rather than a resolution change.
6. **Backward compatibility for saved games:** existing `state/games/*` records were written under the bucket model. The loader must not crash on them; acceptable approaches (decided in planning): one-time migration to populate scores from buckets, or tolerant loading that treats legacy records as read-only history.
7. **Hidden-depth complication as a third scout dimension is out of scope** for this feature (noted as a future enhancement).
8. **Implementer:** per project workflow, medium/large coding is dispatched to Codex from a worktree; `feature-implement` writes code directly only when running the Feature Factory flow. This spec is agnostic to that choice.

---

## Constitution Check

No constitution file found (`CONSTITUTION.md`, `docs/constitution.md`, `.specify/memory/constitution.md` all absent). Validation **SKIPPED**. Project conventions in `CLAUDE.md` (two-lane AI/UI architecture, staging rule, `/ship` merges) are honored at plan/implement time, not as spec gates.
