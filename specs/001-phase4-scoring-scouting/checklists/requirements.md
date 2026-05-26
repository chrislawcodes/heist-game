# Specification Quality Checklist

**Purpose:** Validate spec completeness before implementation
**Feature:** [spec.md](../spec.md)

## Content Quality

- [ ] Numbers/formulas are stated as game-design requirements (scores, pricing curve), not tech choices
- [ ] Focused on player/system value, not implementation
- [ ] All mandatory sections completed (stories, edge cases, FRs, SCs, key entities, assumptions)

## Requirement Completeness

- [ ] No `[NEEDS CLARIFICATION]` markers remain (Hacker-gap question resolved → add a 2nd medium hacker)
- [ ] Requirements testable and unambiguous (FR-001..FR-019)
- [ ] Success criteria measurable (SC-001..SC-008)
- [ ] All acceptance scenarios defined per story
- [ ] Edge cases identified (no driver, probe past EXACT, low bankroll, "High" that's an 8 vs "Hard" that's a 10, legacy saves)
- [ ] Scope bounded (no notoriety/rolling slate; within-round scouting; reward decoupling sequenced P3)

## Phase-4-specific

- [ ] Locked character scores + floor costs present and internally consistent (bucket(score) == published bucket)
- [ ] Margin thresholds, escape rescaling, and backward-compat each have a resolved decision (research.md)
- [ ] Two reconciliation points captured: graded outcomes on score margin; escape on derived bucket
- [ ] Scouting reveal ladder fully specified (free = crew + driver bonus; bucket→exact; $100k overflow; locations-only)
