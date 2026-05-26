# Feature Specification: Campaign Resume

- **Feature branch**: `feat/campaign-resume`
- **Created**: 2026-05-26
- **Status**: Ready for planning — clarifications resolved 2026-05-26
- **Input**: Revive a campaign that was interrupted mid-run (most commonly because the server process restarted and the daemon conductor thread died) and continue it from where it left off, instead of leaving it stuck `status="running"` forever or having to delete it and restart from round 0.

## Background (grounded in current code)

- A campaign is driven by one daemon thread, `run_campaign_conductor(campaign_id, num_rounds)` (`heist/orchestration.py`). It is a plain `for round_idx in range(num_rounds)` loop that rebuilds all state from scratch starting at the round‑0 auction. It has **no resume-from-round hook** and takes no resume argument. When the process stops, that thread is gone but the persisted record stays `status="running"`.
- `recover_games()` runs at server startup (`heist/server.py`) but only understands **single Phase‑1 games**: it reads `record["ais"]` + per‑AI heist snapshots and re‑spawns `_run_game(resume_snapshot=…)` or restarts a single‑game auction. It has **no `is_campaign` branch** and never re‑spawns the conductor. Campaign records use `ais_cfg` / `game_states` / `num_rounds`, so campaigns are currently mishandled (marked done or mis‑routed).
- A campaign **already persists** per‑round state that can serve as a checkpoint: `game_states[i]` holds each team's `standing_crew`, `banked_loot`, and `round_results`; the record holds `current_round_idx`, `current_stage`, and `progress`. Each round runs four stages: `opening_wire → hiring → heist → reflection`.
- The heist layer already has a working finer‑grained resume model to reuse if needed: `resume_heist()` + per‑AI runner snapshots (`save_runner_snapshot` / `list_pending_snapshots`).

This feature concerns the **multiplayer campaign path only**; single Phase‑1 games are already recovered.

## User Scenarios & Testing

### User Story 1 — A campaign survives a server restart (Priority: P1)

As the operator running the server, when I restart it (which happens routinely on staging and production), any campaign that was mid‑run automatically picks back up and finishes the remaining rounds — so a long campaign is no longer lost to a routine restart.

**Why this priority**: This is the core pain. Server restarts are frequent; today every restart kills in‑flight campaigns and there is no recovery path. Without this the feature has no value.

**Independent Test**: Launch a multi‑round campaign, let it complete round 1, restart the server while round 2 is in flight, and confirm the campaign continues to a normal completion with correct standings — no manual intervention.

**Acceptance Scenarios**:
1. **Given** a campaign that has completed N rounds and is mid‑way through round N+1, **When** the server restarts, **Then** the campaign resumes and runs to completion without restarting from round 0.
2. **Given** a campaign interrupted before any round completed (during the round‑0 setup auction), **When** the server restarts, **Then** it resumes cleanly with no banked loot or partial state carried incorrectly.
3. **Given** a campaign that had already finished (`status="done"`), **When** the server restarts, **Then** resume is a no‑op and the campaign is untouched.

### User Story 2 — Manually revive a stalled campaign without a full restart (Priority: P2)

As the operator, if a campaign is stuck `running` but no longer progressing (the server is up but its conductor thread died or hung), I can trigger a resume for that one campaign from the lobby / war room, without restarting the whole server (which would disturb other live games).

**Why this priority**: Important fallback, but the P1 startup path covers the most common cause (process restart). A campaign can also stall while the server stays up (thread crash / hung call); this handles that without collateral damage to other running games.

**Independent Test**: Take a campaign whose conductor is gone but the server is up, click "Resume" on it, and confirm it continues — while other running games are unaffected.

**Acceptance Scenarios**:
1. **Given** a campaign that is stalled (no progress for longer than the stall threshold) while the server is up, **When** the operator triggers Resume, **Then** the conductor restarts and the campaign continues.
2. **Given** a campaign that is genuinely still progressing, **When** Resume is triggered, **Then** the system refuses / no‑ops rather than spawning a second conductor.

### User Story 3 — Resume is visibly correct in the war room (Priority: P3)

As a viewer watching a campaign, after it resumes I see it continue normally — completed rounds are intact, no round or result is duplicated, banked totals are unchanged — and ideally a subtle indicator that it resumed.

**Why this priority**: Polish/trust. The correctness guarantees are enforced by requirements regardless; this story is about the viewer's confidence and an optional indicator.

**Independent Test**: Compare the war‑room standings/round history before and after a resume; verify completed rounds, takes, banked loot, and crew are byte‑for‑byte unchanged and nothing is duplicated.

**Acceptance Scenarios**:
1. **Given** a campaign resumed after interruption, **When** I open the war room, **Then** every previously‑completed round shows the same job, take, banked total, crew, and caught members as before.
2. **Given** a resumed campaign, **When** it finishes, **Then** the round count and sub‑games match a campaign of that length (no duplicates).

## Edge Cases

- **Interrupted mid‑hiring** (auction partially done): resume must not double‑charge for crew already hired or re‑bid for crew already won. → resume at a boundary that treats the hiring stage as all‑or‑nothing.
- **Interrupted mid‑heist, parallel threads**: heists run one thread per AI, joined before reflection. If the crash hit while some AIs' heists were done and others weren't, resume must not re‑run completed heists or double‑bank their takes.
- **Interrupted between heist and settle** (take computed but not yet banked): resume must not double‑bank, and must not drop the take either.
- **In‑flight sub‑game** (a hire/heist sub‑game record left mid‑flight): decide whether to discard + re‑run that stage or resume the sub‑game itself.
- **No usable checkpoint** (e.g., an old campaign that predates this feature, like the current stalled game 14): if the persisted state is insufficient to resume safely, mark it terminal/"interrupted" rather than leave it "running" — never silently corrupt.
- **Double resume race**: auto‑recover at startup and a manual Resume firing for the same campaign must not produce two conductors.
- **Repeated restarts**: a campaign interrupted, resumed, then interrupted again must still resume (idempotent and repeatable).
- **A team already eliminated** (crew wiped) before the interruption: resume must preserve their done/eliminated status.

## Requirements

### Functional Requirements

- **FR-001**: On server startup, the system MUST detect campaign records (`is_campaign`) with `status="running"` and route them to a campaign‑aware resume path — never mishandle them as single games or silently mark them done. (Supports US1)
- **FR-002**: A resumed campaign MUST continue from a safe checkpoint at or before the point of interruption and complete only the **remaining** rounds — it MUST NOT restart from round 0. (Supports US1)
- **FR-003**: Resume MUST be idempotent with respect to economy and roster: it MUST NOT double‑bank loot already banked, MUST NOT re‑charge for crew already hired, and MUST NOT re‑bid for crew already won in a completed stage. (Supports US1, US3)
- **FR-004**: All already‑completed rounds MUST be preserved exactly across a resume — job, take, banked total, standing crew, caught members, and recorded sub‑game ids unchanged. (Supports US3)
- **FR-005**: If the campaign was interrupted partway through a round, the system MUST resume that round at the **stage boundary**: completed stages of that round (e.g. a finished hiring auction) are kept, and the system redoes only from the stage that was in progress when interrupted (tracked by `current_stage`), without duplicating any already‑completed stage. (Supports US1)
- **FR-006**: A campaign that CANNOT be safely resumed (insufficient or inconsistent checkpoint) MUST be moved to a clear non‑running terminal state (e.g., `interrupted`/`error`) — it MUST NOT be left dangling as `running`. (Supports US1)
- **FR-007**: On resume the engine MUST emit the same kind of events it emits during normal play, so the war room reflects the continued campaign without the UI reconstructing state (two‑lanes rule). (Supports US3)
- **FR-008**: Operators MUST be able to manually trigger resume of a single stalled campaign without restarting the server. Both paths are required: auto‑resume on startup (FR‑001) **and** this manual path. (Supports US2)
- **FR-009**: The system MUST guard against running two conductors for the same campaign concurrently (e.g., a manual Resume on a campaign that is actually still alive must no‑op or be rejected). (Supports US2)
- **FR-010**: The campaign MUST persist enough state at safe checkpoints (per‑round and per‑stage: standing crew, banked loot, round_results, current round, current stage, sub‑game ids) for a resume to reconstruct the in‑memory campaign deterministically. Where the existing persisted `game_states` already capture this, the feature SHOULD reuse it rather than add a parallel store. (Supports US1)
- **FR-011**: Resume MUST be repeatable — a campaign interrupted, resumed, and interrupted again MUST still resume correctly. (Supports US1)

### Key Entities

- **Campaign record** (`state/games/<id>.json`): `status`, `is_campaign`, `num_rounds`, `current_round_idx`, `current_stage`, `progress`, and `game_states[]` (per‑AI `standing_crew`, `banked_loot`, `round_results`, sub‑game ids). The de‑facto checkpoint.
- **Round checkpoint**: the minimal per‑round/per‑stage state required to resume deterministically (may be entirely derivable from the campaign record + game_states).
- **Sub‑games**: per‑round hire and heist sub‑games (separate game ids), heists having their own resume snapshots.

### Success Criteria

- **SC-001**: After a server restart that interrupts a campaign at a round boundary, the campaign resumes and completes with the same final standings it would have reached uninterrupted — in 100% of such restart scenarios.
- **SC-002**: Across a resume, completed‑round banked loot and crew show **zero** discrepancies (no double‑counting, no loss).
- **SC-003**: After any server startup, **no** campaign remains permanently `running` with no conductor — each is either actively resumed or moved to a terminal state, within seconds of startup.
- **SC-004**: An operator can revive a stalled campaign with a single action, without restarting the server or disturbing other running games. (US2)
- **SC-005**: A resumed campaign produces **no** duplicate round and **no** duplicate sub‑game.

## Assumptions

- Scope is the multiplayer **campaign** path (`run_campaign_conductor`); single Phase‑1 games are already recovered by `recover_games()` and are out of scope.
- The persisted `game_states` (with `round_results` appended at each round's settle) are treated as the primary checkpoint, so the cleanest safe resume point is a **round/stage boundary**, reconstructing in‑memory `Campaign` objects from persisted state and restarting the conductor loop at `current_round_idx`.
- **Resolved**: Campaigns already stalled before this feature ships are **always** marked terminal (`interrupted`), never force‑resumed — so today's game 14 becomes `interrupted` and must be deleted + re‑run. Only campaigns that begin running under this feature's checkpointing are resumable.
- "Stalled" detection for manual resume can reuse the existing progress heartbeat staleness (`progress.updated_at` older than the stall threshold).
- No game mechanics, auction model, or UI beyond a resume affordance/indicator change.

## Resolved Decisions (2026-05-26)

- **Resume granularity → Stage boundary.** Keep completed stages of the interrupted round; redo only from the stage that was in progress (`current_stage`). Drives FR‑005.
- **Trigger → Both auto + manual.** Auto‑resume eligible campaigns on server startup (FR‑001) **and** expose a manual Resume action for a campaign that stalls while the server is up (FR‑008).
- **Pre‑existing stalls → Always terminal.** Campaigns stalled before this feature ships are marked `interrupted`, not revived (so game 14 is deleted + re‑run). Only campaigns started under the new checkpointing are resumable. Drives FR‑006.
