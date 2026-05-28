# Specification Quality Checklist

**Purpose**: Validate that spec.md is complete enough to drive implementation.
**Feature**: [spec.md](../spec.md)

## Content Quality

- [ ] No implementation details (specific libraries, line numbers, or function bodies) leaked into spec.md — those belong in plan.md.
- [ ] Each user story explains user/system value, not how it's coded.
- [ ] Sections are written so a non-coding stakeholder could follow them.
- [ ] All mandatory sections present: User Scenarios & Testing, Edge Cases, Functional Requirements, Success Criteria, Assumptions.

## Requirement Completeness

- [ ] No `[NEEDS CLARIFICATION]` markers remain anywhere in spec.md.
- [ ] Every functional requirement (FR-NNN) is testable — a reviewer could write a unit test or a manual check without inventing details.
- [ ] Every Success Criterion (SC-NNN) is measurable (has a number / threshold / observable signal).
- [ ] All user-story acceptance scenarios are stated in Given/When/Then form.
- [ ] Edge cases section covers: failed scout, all-zero-probes, pool exhaustion, resume mid-stage, backward-compat on saved campaigns.
- [ ] Scope is clearly bounded by the "Locked design" / "Out of scope" notes.

## Independent Testability

- [ ] Each user story has an "Independent Test" line that explains how to verify it without depending on the other stories being complete.
- [ ] US1 (parallel scouts) can be tested with a timing/mocked-delay test — confirmed.
- [ ] US2 (pick_order) is a pure-function test — confirmed.
- [ ] US3 (probe budget) is a single-value assertion — confirmed.
- [ ] US4 (carryover) can be tested in a 2-round stub campaign — confirmed.
- [ ] US5 (persistent intel) can be tested in a 2-round stub campaign — confirmed.

## Prioritization

- [ ] P1 stories form a coherent MVP that ships meaningful behavior end-to-end (US1+US2+US3 unlock the rush-vs-scout strategic axis).
- [ ] P2 stories layer on top of the MVP without breaking it (US4 and US5 add compounding, do not change P1 semantics).
- [ ] No story is marked P1 that the MVP could ship without.
