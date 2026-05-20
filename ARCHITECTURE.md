# Heist Game — Architecture

## Overview

A local web app for watching multiple AI agents independently plan and run the same heist. The player builds a strategy prompt in a wizard, stages 1–3 AIs onto a "game", launches it, then watches each AI bid for a crew, pick a job, and execute scenes in parallel.

```
Browser
   /              → lobby           (list / start games)
   /setup         → setup wizard    (build prompt + add AI)
   /hiring        → hiring phase    (bidding board)
   /job           → job phase       (job slate + AI's pick)
   /heist         → heist phase     (scene cards as they resolve)
   /epilogue      → outcome         (take, escape, epilogue text)
       │
       │  fetch /api/* + EventSource /stream
       ▼
heist/server.py  (stdlib http.server, threaded)
       │
       │  one threading.Thread per AI per game
       ▼
heist/runner.py  → run_heist()
       │
       │  15–20 sequential CLI calls
       ▼
heist/backends.py → CodexHeistAI / GeminiHeistAI
       │
       ▼
   codex exec | gemini  (subprocess)
```

---

## Frontend — Phase Pages

The viewer is split into four standalone URLs. Each page mounts one **tab fragment** into its `#main`, shares the same right rail, and auto-navigates to the next phase when its trigger event fires.

| Page | URL | Tab fragment | Trigger to next page |
|---|---|---|---|
| Hiring | `/hiring?game=N` | `web/tabs/hiring.html` | `job_known` → `/job` |
| Job | `/job?game=N` | `web/tabs/job.html` | first `scene_start` → `/heist` |
| Heist | `/heist?game=N` | `web/tabs/heist.html` | `game_done` → `/epilogue` |
| Epilogue | `/epilogue?game=N` | (none — renders inline) | terminal |

### `heist/web/shell.js` — shared module

Loaded by every phase page via `<script src="/shell.js">`. Exposes:

- `window.Shell` — shared state + helpers (`roster`, `aiList`, `currentAI`, `helpers.{escapeHtml, renderMd, skillVal, primarySkill, portraitUrl, charCardHtml, buildDiffBar, diffCls}`)
- `window.initShell({ gameId, onEvent })` — boot entry point. Fetches `/api/meta` + `/api/games`, populates roster/AI list, renders top bar + AI picker, loads the replay buffer, fans every event to the page's `onEvent` callback
- `window.loadTabFragment(name)` — fetch + execute a `/tabs/<name>` fragment so its `<style>`, `<template>`, and `<script>` activate
- `window.replayStep / replayToggle / replayReset` — bound to topbar replay buttons

**Replay mode is always on.** `initShell` fetches `/api/games/<id>/events` for every game and exposes Step / Play / Reset controls. Live SSE is not wired in the UI; pressing Step advances through the buffer event-by-event. (Hit browser refresh mid-run to pick up newer events.)

### Tab fragments

Each fragment registers a global `window.{Hiring|Job|Heist}Tab` object exposing `{ mount, handleEvent, reset, unmount }`. The page calls `mount(panel, { shell: Shell })` after loading the fragment, then forwards every event via `handleEvent(e)`.

| Fragment | Renders | Events it cares about |
|---|---|---|
| `web/tabs/hiring.html` | Available roster + crew columns + skill coverage bars | `turn_end(bid)`, `crew_known`, `game_done` |
| `web/tabs/job.html` | Comparison grid (team skills card vs location card) + AI reasoning sidebar + hidden depth callout | `turn_end(job_pick)`, `job_known`, `crew_known`, `hidden_depth_rolled`, `game_done` |
| `web/tabs/heist.html` | Job header (chips + reward) + expandable scene cards (chevron, type badge, outcome chip, char blocks, challenge block, narration) + outcome card | `crew_known`, `job_known`, `scene_start`, `scene_done`, `turn_end(scene_N_narrate)`, `game_done` |

#### Adding a new tab fragment

1. Create `heist/web/tabs/<name>.html`. The file is HTML — `<style>` / `<template>` / `<script>` all go inline. Server serves it at `/tabs/<name>` with the right content-type.
2. At the bottom of the fragment's `<script>`, register the tab on `window`:
   ```js
   window.MyTab = {
     mount(panel, { shell }) { /* attach DOM to `panel`, store `shell` ref */ },
     handleEvent(e) { /* called for every replay event */ },
     reset() { /* called on replayReset and back-step rewinds */ },
     unmount() { /* optional — clear timers, listeners */ },
   };
   ```
3. Create or update a phase page (e.g. `heist/mypage.html`) that calls `initShell({ gameId, onEvent: (e) => window.MyTab.handleEvent(e) })` and then `loadTabFragment('<name>')` followed by `window.MyTab.mount(panel, { shell: Shell })`.
4. Add the page's route to `heist/server.py` `_dispatch_get` and a constant like `_MYPAGE_HTML` at the top of the file.
5. If the page is part of the phase navigation chain, wire `_atPhaseEnd('/next-page?game=...')` in `handleEvent` at the boundary trigger, and add it to the `phases` array in `_updatePhasenav` (in `shell.js`).

### Other pages

- `heist/lobby.html` → `/` — list of staged/running/done games, "Start New Game", "Quick Test", per-row replay link
- `heist/web/setup.html` → `/setup?game=N` — 4-step wizard (Risk → Crew → Decisions → Run It) that POSTs `/api/add-ai`
- `heist/epilogue.html` → `/epilogue?game=N` — renders take + escape + aborted + epilogue text from the game's `game_done` event

### Replay model (the UI is always replay-driven)

**There is no live SSE in the UI.** Every phase page boots by fetching `/api/games/<id>/events` (the persisted buffer that grows in real time on the backend) and walking through it locally. To see newer events you refresh the page. This is deliberate: it makes the UI deterministic, debuggable from the lobby's Replay link without distinction from a "live" view, and trivially scrubbable.

**Step / Play / Reset operate on the buffer.** Topbar controls advance `_REPLAY_INDEX` one **visible stage** at a time. "Visible" excludes invisible events (e.g., `_reset` synthetic signals); the count is a property of the whole game, not per-AI — a Step means "advance the whole game by one beat" not "advance the AI I'm watching."

**Phase auto-navigation.** When a phase-boundary event fires, the page navigates to the next URL:

| From | Trigger event | To |
|---|---|---|
| `/hiring` | `job_known` | `/job` |
| `/job` | first `scene_start` | `/heist` |
| `/heist` | `game_done` | `/epilogue` |

In **play mode** (`_REPLAY_TIMER` running), the URL carries `autoplay=1` so the next page resumes playing. In **step mode** the user lands on the next page paused.

**Back across phase boundaries.** Each page can compute `_prevPhaseUrl(stage)` and navigate to the previous phase with `?atStage=N`. The receiving page calls `_jumpToStage(N)` which:

1. Resets all per-AI state (`_aiStreams`, `_hiredMarks`, etc.)
2. Replays the buffer in "review mode" (no UI animations, no auto-nav) up to event index N
3. Hands control back to the user, paused

Net effect: Back is always exactly one stage back, even across phase boundaries — never a fast-forward to "current."

**Phasenav** (`#phasenav` in the topbar): completed phases become `<a>` links so the user can jump back to any phase in review mode without manual Back-stepping.

### Mockups

`heist/mocks/*.html` are static design references served at `/mocks/<name>`.

---

## Backend — `heist/server.py`

Plain `http.server.ThreadingHTTPServer` from the stdlib. No framework. One handler class (`_Handler`) with `do_GET` / `do_POST` dispatching to small methods.

### Routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | lobby.html |
| `/setup` | GET | setup.html |
| `/hiring`, `/job`, `/heist`, `/epilogue` | GET | Phase pages |
| `/shell.js` | GET | Shared JS module (served with `application/javascript`) |
| `/tabs/<name>` | GET | Tab fragment HTML |
| `/mocks/`, `/mocks/<name>` | GET | Static mockups + index |
| `/stream` | GET | Server-Sent Events stream of every game event |
| `/api/meta` | GET | `{ roster, jobs }` |
| `/api/status` | GET | `{ has_history, game_running }` |
| `/api/games` | GET | All games (staged + running + done), heavy `events` field stripped |
| `/api/games/<id>/events` | GET | Full event log for one game (replay buffer) |
| `/api/new-game` | POST | Create a staged game → `{ game_id }` |
| `/api/add-ai` | POST | `{ game_id, prompt, agent }` — attach an AI |
| `/api/launch` | POST | `{ game_id }` — start the game, spawn one thread per AI |
| `/api/quick-game` | POST | Preset: stage + launch 2× codex-mini with the default prompt |

### Game lifecycle

A "game" is a single job attempt that 1–3 AIs play independently against the same roster + job slate.

1. **Stage** — `POST /api/new-game` returns a `game_id`; `POST /api/add-ai` attaches AIs (1–3)
2. **Launch** — `POST /api/launch` spawns one `threading.Thread` per AI, each running `_run_game()`
3. **Run** — each thread calls `run_heist()`. Events emit via `_broadcast()` which:
   - appends to `_event_history` (legacy)
   - appends to the game's `events` list (used for replay)
   - persists the game record to disk via `save_game_record()`
   - fans out to every connected SSE subscriber queue
4. **Done** — when all AIs in a game finish, `_game_running` flips to `False` and the lobby shows the result

Every event includes `ai_idx` so the viewer can split per-AI state. The shell's `Shell.currentAI` switch lets the user watch one AI's perspective at a time.

### Persistence + recovery (`heist/persist.py`)

- `state/games/<id>.json` — full game record (status, AIs, results, full events list)
- `state/games/<id>/ai-<idx>.json` — per-AI runner snapshot (stage, scene_idx, codex session_id, base64-pickled RNG state) so a crashed game can resume mid-scene. Deleted when the AI completes; only present while a run is in-flight.

On startup, `_recover_games()` reloads every game record. For any game whose status is `running`, it scans `state/games/<id>/` for in-flight AI snapshots and spawns resume threads via `resume_heist()`. AIs without snapshots are marked errored.

### `--web-dir` flag

`python -m heist serve --web-dir /path/to/some/worktree/heist` makes the server read HTML / JS files from that directory instead of the one where `heist/server.py` lives. Lets a single server preview any worktree's UI changes without restarting.

---

## Game Engine

### `heist/runner.py` — `run_heist()`

15–20 sequential CLI calls per AI, in order:

1. **Bid** — AI drafts crew from 15-character roster within $2,000 bankroll  
   *emits* `turn_end(bid)`
2. **Fill** (if under 4) — top-up bids until crew has 4  
   *emits* `turn_end(fill_*)`, `crew_known`
3. **Casting summary** — AI explains its crew choices  
   *emits* `turn_end(casting_summary)`
4. **Job pick** — AI selects one of the jobs in the slate (currently 7; see `heist/content.py`'s `JOBS` list) with why-this + why-not  
   *emits* `turn_end(job_pick)`, `job_known`, `hidden_depth_rolled`
5. **Scene loop** — for each scene: assign → resolve → (abort? if failed) → narrate. Decision scenes (hidden-depth bonus) also get a pursue/skip prompt before resolution.  
   *emits* `scene_start`, `turn_end(scene_N_assign)`, `turn_end(scene_N_decision)`, `turn_end(scene_N_abort)`, `scene_done`, `turn_end(scene_N_narrate)`
6. **Escape** — resolved mechanically from heat + driver skill  
   *emits* `scene_start(escape)`, `scene_done`, `turn_end(scene_N_escape_narrate)`
7. **Epilogue** — closing prose  
   *emits* `game_done` (state + extras)

`snapshot_fn` is called at each stage boundary so `resume_heist()` can pick up after a crash.

### `heist/mechanics.py`

Pure functions, no AI calls.

- `effective_skill()` — two crew members in the same skill area act one level higher than the better one (capped at High)
- `resolve_outcome()` — skill level vs. challenge level → `Outcome` (CLEAN / SQUEAK / FAIL / CAUGHT)
- `outcome_is_pass()` — CLEAN and SQUEAK are passes; FAIL and CAUGHT are failures
- `escape_resolves()` — driver skill vs. `(escape_modifier + heat)`

### `heist/state.py`, `heist/content.py`, `heist/scenes.py`

- `state.py` — frozen dataclasses (`Character`, `Job`, `Scene`, `SceneResult`, `HeistState`)
- `content.py` — 15-character roster, 7-job slate (the `JOBS` list, free to evolve), default prompt
- `scenes.py` — builds the scene list for a job, splicing in the hidden-depth element

### `heist/serialize.py`

`character_to_dict`, `job_to_dict`, `state_to_dict` — convert dataclasses to plain dicts so they can ride on SSE events and persistence JSON.

---

## AI Layer

### `heist/ai.py`

`HeistAI` protocol: one method — `ask(prompt: str) -> AgentTurn`. Defines `parse_json_block()` (strips markdown fences, extracts JSON, attempts deterministic repairs) used by `_call_json` for structured responses. Prose-only calls (casting summary, scene narration, epilogue) bypass JSON parsing entirely and use `_call` directly.

### `heist/stub_responses.py`

`build_stub_ai()` — a `HeistAI` that dispatches scripted responses by prompt content. Structured calls return JSON; prose calls (narration, summary, epilogue) return plain text. Used by `--agent stub` for end-to-end tests without burning API calls.

### `heist/backends.py`

`CodexHeistAI(model="gpt-5.4-mini")` and `GeminiHeistAI()`. Each wraps the CLI invokers in `agents.py` and threads `session_id` across calls so one heist runs in one CLI session (maintains conversation context).

### `agents.py`

Thin subprocess wrappers.

- `ask_codex()` — runs `codex exec [-m model] --json --sandbox read-only ...`
- `ask_gemini()` — runs `gemini -o json [-p prompt] [--resume session_id]`

Both return `Turn(text, session_id)`.

---

## Running Locally

```bash
python -m heist serve
```

Open **http://localhost:8000/** in your browser. Use **Quick Test** in the lobby to stage + launch 2× codex-mini with the default prompt; you'll land on `/hiring?game=N` and the browser will auto-navigate through `/job` → `/heist` → `/epilogue` as the run progresses.

For a no-API test from the CLI:

```bash
python -m heist run --agent stub --out report.md
```

To preview a worktree's UI changes against the running server:

```bash
python -m heist serve --web-dir /path/to/worktree/heist
```
