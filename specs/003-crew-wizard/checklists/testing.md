# Testing Quality Checklist

**Purpose:** Validate test coverage and quality
**Feature:** [tasks.md](../tasks.md)

No constitution — using the project's preflight + best practices.

## Preflight (run before every push — CLAUDE.md)

- [ ] `python3 -m ruff check .` clean
- [ ] `mypy heist/ agents.py demo.py` clean (no `# type: ignore` added for crew code)
- [ ] `pytest -q` green

## Test Coverage (this feature)

- [ ] Crew persist round-trip: save → load returns the same crews (T013).
- [ ] Delete removes only the target; others intact (T013, SC-004).
- [ ] Missing file → `[]`; corrupt/non-list file → `[]`, no exception (T013, FR-013).
- [ ] Duplicate names persist under distinct ids (T013, FR-011).
- [ ] `POST /api/crews`: happy path returns id+created_at; empty name/prompt → 400 (T014).
- [ ] `GET /api/crews` lists saved; `DELETE /api/crews/{id}` removes target, 404 on unknown (T014).
- [ ] `/api/quick-campaign` with `crew_ids` builds matching `ais` in order; unknown id / count>6 → 400 (T017).
- [ ] `/api/quick-campaign` with empty/no body → unchanged 3-team preset (T017, SC-006).

## Manual / Browser (quickstart.md, on staging 8001)

- [ ] US1: scouting paragraph changes when only the Scouting step changes (SC-002); manual prompt edits preserved (FR-003).
- [ ] US2: saved crew survives a server **restart** (Python loads once — restart staging) (SC-003).
- [ ] US3: a Quick Test composed entirely of saved crews runs those crews; default Quick Test unchanged (SC-005/006).

## Test Hygiene

- [ ] Tests use a temp `HEIST_STATE_DIR` (no writes to the real `state/`).
- [ ] New tests follow the existing harness pattern in `tests/`.
- [ ] Edge cases covered (empty store, corrupt store, dup names, over-limit selection).
