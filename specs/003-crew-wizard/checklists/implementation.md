# Implementation Quality Checklist

**Purpose:** Validate code quality during implementation
**Feature:** [tasks.md](../tasks.md)

No constitution file exists in this repo — using project conventions (CLAUDE.md) + best practices.

## Code Quality (project conventions)

- [ ] Consistent with existing style (`heist/persist.py` helper shape; `heist/server.py` handler/router pattern; `setup.html` CSS tokens + `escapeText`/`escapeAttr`).
- [ ] Crew store reuses `_atomic_write` / `_safe_load` / `_state_dir` — no bespoke file IO.
- [ ] New endpoints validate at the boundary (non-empty `name`/`prompt`; default `agent`); trust internal data otherwise.
- [ ] No new dependencies; stdlib + vanilla JS only (no build step).
- [ ] No hardcoded absolute paths or URLs (use `_state_dir()`, same-origin fetches).

## Two-Lanes Rule (CLAUDE.md)

- [ ] The wizard only **authors** the strategy prompt the AI lane consumes. It adds **no** UI-side game-state computation, and changes **no** engine/mechanics/scoring/scouting-resolution code.
- [ ] Quick-campaign extension only selects which `ais` to launch — it does not alter how the campaign runs.

## Security / Safety

- [ ] All stored, re-displayed crew text is HTML-escaped in `setup.html` and `lobby.html` (FR-014).
- [ ] Corrupt/missing `state/crews.json` degrades to `[]`, never a 500 (FR-013).
- [ ] `DELETE /api/crews/{id}` removes only the target; never destructive across the store.
- [ ] Duplicate display name never overwrites a different crew (distinct server `id`).

## No Regression

- [ ] `/api/new-campaign` payload/behavior unchanged (wizard posts the existing shape).
- [ ] `/api/quick-campaign` with no body / no `crew_ids` is identical to today's 3-team preset.
- [ ] Existing freeform/flat launch path still works (or is intentionally replaced with equal capability).
