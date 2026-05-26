# Acceptance Criteria: Phase 4 — Hidden Location Info & Scouting

## User Stories
| ID | Title | Priority |
|----|-------|----------|
| US-1 | True-score resolution, pricing, collaboration | P1 |
| US-2 | Scout a location to learn its defenses | P2 |
| US-3 | Experience the fog in the viewer | P2 |
| US-4 | Tiered job ladder + mispriced "edge" jobs | P3 |
| US-5 | A second Medium Hacker for electronic resilience | P3 |

## Acceptance Scenarios

### US-1: True-score resolution, pricing, collaboration
- Given a member with Safecracker score 9, When priced, Then floor cost = $100k seat + $600k = $700k.
- Given two Inside Man members at 7 and 6, When effective Inside Man computes, Then it returns 8 (best+1, cap 10).
- Given effective score 8 vs hidden challenge 9, When resolved, Then it fails and heat rises per the margin table.
- Given effective score 10 vs challenge 8, When resolved, Then clean pass.
- Given an existing stub campaign, When run under the new engine, Then 3 rounds complete with no crash and the same event types emit.

### US-2: Scout a location
- Given a 4-member crew with a Medium best-driver (+2), When scouting opens, Then 6 free probes.
- Given an unscouted location, When one probe targets (location, electronic), Then electronic bucket revealed, others fogged.
- Given electronic bucket already revealed, When a 2nd probe targets it, Then exact 1-10 electronic score revealed.
- Given all free probes spent, When one more probe requested, Then $100k charged (granted if affordable; refused if not).
- Given a job scouted to exact on its gating challenge, When the AI crews/runs it, Then it can field a comfortable margin against the known score.

### US-3: Fog in the viewer
- Given an unscouted location, When rendered, Then defenses fogged and reward range public.
- Given a bucket `scouted` event, When processed, Then that category updates fogged→bucket.
- Given an exact `scouted` event, When processed, Then that category shows the 1-10 value.

### US-4: Tiered ladder + edges
- Given a Tier-1 job, When scores roll, Then no challenge exceeds Medium (any Hard = exactly 8).
- Given a Tier-3 job, When scores roll, Then gating Hards roll in {9,10}.
- Given the reward model, When a job rolls, Then prize and defenses are correlated with slack.
- Given an edge job scouted to exact, When the AI evaluates, Then it can commit a cheaper crew to a high prize behind soft defenses.

### US-5: Second Medium Hacker
- Given the updated roster, When loaded, Then 17 characters with ≥2 Medium-band hackers.
- Given the new hacker (7) paired with Sasha (6) on electronic, When effective computes, Then 8.

## Success Criteria
- SC-001: Full stub campaign (3 rounds) + stub single job complete error-free; all 17 priced by the curve.
- SC-002: Every floor cost equals `seat + Σ premium(score)` to the dollar.
- SC-003: Across 100 resolutions, outcome is exactly determined by `effective_score` vs `challenge_score` (no randomness in the contest); graded outcome matches the margin mapping every time.
- SC-004: Two same-skill members always give effective `min(best+1, 10)`.
- SC-005: Free probe count = `crew size + driver bonus` for every driver tier; 1st/2nd probe = bucket/exact.
- SC-006: A scouted-to-exact crew clears the gating challenge first-attempt at least as reliably as a fully-margined blind crew, at lower crew cost.
- SC-007: ≥1 pool job presents a high reward range over below-trend defenses; scouting reveals it as an edge.
- SC-008: The viewer never shows an unscouted exact defense score or exact reward.

## Key Constraints
- **Two-lane architecture**: engine emits all events; UI only renders — *Why: the contract that keeps display logic out of the compute path; a missing UI value is fixed by emitting it, not reconstructing it.*
- **Heat cascade stays steep**: do not soften the margin/heat bands — *Why: project memory; the steep cascade is intentional and scouting is its counterweight.*
- **Character scores public, location scores fogged**: scouting applies to locations only — *Why: locked design; pricing on public character scores leaks nothing, and the fog/intelligence game lives entirely on the location side.*
- **`ScoutState` is the single fog authority**: prompts AND serialize read it — *Why: two sources of "what's known" drift and leak the fog in one lane.*
- **`Job` stays a frozen constant**: rolled scores live per-round on state — *Why: jobs are shared/reused every round; per-round mutation is unsafe and breaks parallel-AI determinism.*
- **Existing flows keep working**: `run_heist`/`run_campaign` end-to-end under new engine — *Why: FR-007; Phase 4 supersedes mechanics without removing the play modes.*
