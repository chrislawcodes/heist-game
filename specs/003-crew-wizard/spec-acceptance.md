# Acceptance Criteria: Strategy-Prompt Wizard, Scouting Step & Premade Crews

## User Stories
| ID | Title | Priority |
|----|-------|----------|
| US-1 | Guided strategy-prompt wizard with a Scouting step | P1 |
| US-2 | Save, list & reuse premade crews | P2 |
| US-3 | Compose Quick Test (and setup) from premade crews | P3 |

## Acceptance Scenarios

### US-1: Guided wizard with Scouting step
- Given the wizard, When a Risk appetite is chosen, Then the prompt's job paragraph matches it.
- Given the Crew step, When a budget posture is chosen, Then the prompt's crew paragraph matches it.
- Given the Scouting step, When a scouting style is chosen, Then the prompt contains a scouting paragraph matching it, phrased so the engine's scouting turn acts on it.
- Given the Decisions step, When bonus + failure handling are set, Then both appear in the prompt.
- Given any step, When the override box is used, Then the override replaces that step's generated paragraph (summary marks "custom").
- Given Run It, When the player edits the prompt directly, Then the edited text launches (no silent regeneration over edits).
- Given a completed wizard, When launched, Then a campaign is created via the existing campaign API with the crew's name/agent/prompt and the viewer opens.

### US-2: Save / list / reuse premade crews
- Given a completed crew, When "Add Crew" is clicked, Then it is saved server-side with a confirmation.
- Given saved crews, When setup loads, Then the player can pick a saved crew to add to the campaign.
- Given a picked saved crew, When the campaign launches, Then it uses the stored name/agent/prompt.
- Given saved crews, When one is deleted, Then it is removed and others are untouched.
- Given a duplicate name, When saving, Then result is unambiguous (new id + warn) — never a silent overwrite.
- Given a server restart, When the list is requested, Then previously saved crews are still present.

### US-3: Quick Test from premade crews
- Given saved crews, When a Quick Test is started, Then the player can run it with selected saved crews.
- Given no saved crews, When a Quick Test is started, Then the hardcoded preset still works unchanged.
- Given N selected saved crews, When launched, Then exactly those N compete with stored name/agent/prompt over the quick-test round count.

## Success Criteria
- SC-001: Build a launch-ready prompt in <~60s via selections only; prompt reflects all dimensions incl. scouting.
- SC-002: Changing only the Scouting step produces a visibly different scouting paragraph.
- SC-003: A crew saved with Add Crew survives a full server restart and launches without rebuilding.
- SC-004: Deleting a saved crew removes exactly that crew, others intact.
- SC-005: A Quick Test can be composed entirely of saved crews; with zero saved crews the original Quick Test launches unchanged.
- SC-006: No regression — existing freeform launch + Quick/Medium Test presets work end-to-end.

## Key Constraints
- Server-side storage at `state/crews.json` — Why: Quick Test launches from a server endpoint, so crews must be reachable server-side, not localStorage.
- Scouting step is prompt-text only — Why: scouting on main is prompt-driven; the engine reads the strategy text, so no engine change is needed (avoids engine risk).
- Corrupt/missing crews file → empty list, never 500 — Why: mirrors forgiving game-record loading; one bad file must not down the server.
- HTML-escape all stored/redisplayed crew text — Why: saved crews introduce stored player text that is re-rendered (XSS safety).
- No regression to `/api/new-campaign` or the Quick/Medium presets — Why: existing flows must keep working; new behavior is additive/opt-in.
- Crew copied by value into a campaign at launch — Why: deleting a crew must not affect a running/finished campaign.
