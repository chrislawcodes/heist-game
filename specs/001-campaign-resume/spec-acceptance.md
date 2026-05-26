# Acceptance Criteria: Campaign Resume

## User Stories
| ID | Title | Priority |
|----|-------|----------|
| US-1 | A campaign survives a server restart | P1 |
| US-2 | Manually revive a stalled campaign without a full restart | P2 |
| US-3 | Resume is visibly correct in the war room | P3 |

## Acceptance Scenarios

### US-1: A campaign survives a server restart
- Given a campaign that completed N rounds and is mid‑way through round N+1, When the server restarts, Then the campaign resumes and runs to completion without restarting from round 0.
- Given a campaign interrupted before any round completed (round‑0 setup auction), When the server restarts, Then it resumes cleanly with no partial state carried incorrectly.
- Given a campaign already `done`, When the server restarts, Then resume is a no‑op.

### US-2: Manually revive a stalled campaign
- Given a campaign stalled (no progress past the stall threshold) while the server is up, When the operator triggers Resume, Then the conductor restarts and the campaign continues.
- Given a campaign genuinely still progressing, When Resume is triggered, Then the system refuses / no‑ops rather than spawning a second conductor.

### US-3: Resume is visibly correct
- Given a campaign resumed after interruption, When I open the war room, Then every previously‑completed round shows the same job, take, banked total, crew, and caught members as before.
- Given a resumed campaign, When it finishes, Then the round count and sub‑games match a campaign of that length (no duplicates).

## Success Criteria
- SC-001: After a restart that interrupts a campaign at a round boundary, it resumes and completes with the same final standings it would have reached uninterrupted — 100% of such scenarios.
- SC-002: Across a resume, completed‑round banked loot and crew show zero discrepancies (no double‑count, no loss).
- SC-003: After any startup, no campaign remains permanently `running` with no conductor — each is resumed or moved terminal, within seconds.
- SC-004: An operator can revive a stalled campaign with a single action, without restarting the server or disturbing other running games.
- SC-005: A resumed campaign produces no duplicate round and no duplicate sub‑game.

## Key Constraints
- Stage‑boundary resume — *Why: economy side‑effects (hiring deducts banked loot; settle banks the take) live in specific stages; re‑entering a completed stage double‑counts.*
- `settle_round` runs exactly once per round — *Why: it banks the take and removes caught crew; a duplicate would double‑bank and double‑remove.*
- Both auto (startup) + manual (endpoint) triggers — *Why: process restart is the common cause, but a campaign can also stall while the server stays up.*
- Pre‑existing stalls (no `checkpoint_version`) → `interrupted`, never force‑resumed — *Why: their persisted state isn't guaranteed sufficient; safer to require deletion + re‑run.*
- Double‑conductor guard (`active_campaigns`) — *Why: two conductors on one campaign would duplicate rounds and corrupt economy.*
- Two‑lanes — *Why: resume must re‑emit normal events so the UI continues to display without reconstructing state.*
