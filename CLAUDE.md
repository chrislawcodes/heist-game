# Heist Game — Project Context

## What This Is

A single-player (Phase 1) → multiplayer (Phase 2+) AI heist game. The player writes a strategy prompt; an AI ("Heist AI") handles all decisions — bidding for crew, picking the job, running the heist scene by scene. The player watches.

## Key Documents

| Doc | What's in it |
|-----|-------------|
| [`heist_game_design.md`](heist_game_design.md) | Full game design: all mechanics, roster, jobs, hidden depth, phase roadmap. **Read this before touching game logic.** |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Codebase structure: server, runner, backends, AI layer, how it all connects. **Read this before touching code.** |

## Locked Design Decisions — Do Not Change Without Explicit Instruction

- Skill levels: Low / Medium / High only
- Collaboration rule: two same-skill crew act one level higher, capped at High
- Hard challenges require High skill (Medium + Medium collaboration counts)
- Challenge resolution is graded: clean / squeak (pass, +1 heat) / fail / caught (skill 2+ levels short → a crew member is caught). Take = per-scene loot secured during the run, kept only if at least one crew member escapes
- Bankroll: $2,000,000
- Roster: 16 characters, locked
- Job slate is not locked — add/remove freely in `heist/content.py` (`JOBS` list). Current slate: Museum Gala, Armored Car, Corporate Server Farm, Penthouse Caper, Cargo Yard, Diplomatic Reception, Casino Vault
- System owns all deterministic mechanics; Heist AI owns all creative/interpretive decisions

## Current Phase

**Phase 1** — single player, single job. See `heist_game_design.md` § "Phase 1" for full spec.

## Production vs Staging Servers

Two long-running servers, mapped to two git branches:

| Port | Branch  | Source on disk                                | Purpose |
|------|---------|-----------------------------------------------|---------|
| 8000 | `main`  | `/Users/chrislaw/heist-game`                  | Production — what's shipped. Updates on `git pull`. |
| 8001 | `staging` | `.claude/worktrees/staging/`                | Staging — `main` + every in-flight feature merged together. |

### Hard rule

**The main repo directory (`/Users/chrislaw/heist-game`) stays on `main`
forever.** Never `git checkout -b feat/whatever` there. All feature work
happens in worktrees under `.claude/worktrees/<name>/`.

### Production (port 8000)

```bash
cd /Users/chrislaw/heist-game
python -m heist serve            # leave running

# When a PR merges, refresh:
git pull                         # server reads HTML fresh on every request
```

### Feature work

```bash
# Start a new feature
cd /Users/chrislaw/heist-game
git worktree add .claude/worktrees/<name> -b feat/<name>

# Then cd into the worktree to edit
cd .claude/worktrees/<name>
# ...edit, commit, push, PR
```

### Staging (port 8001)

The `staging` branch is **disposable** — never PR from it. It's regenerated
on demand from `main` + each branch listed in `.claude/staging-branches.txt`.

```bash
# Start the staging server (once)
# Run from the staging WORKTREE (not the main repo) so staging's server.py is used.
# Using --web-dir from the main repo only swaps HTML; Python endpoints come from
# whichever directory you run from. Once all in-flight branches ship to main, you
# can go back to running from the main repo with --web-dir.
cd /Users/chrislaw/heist-game/.claude/worktrees/staging
python -m heist serve --port 8001

# Refresh staging whenever you want 8001 to reflect your latest feature work
cd /Users/chrislaw/heist-game
.claude/scripts/refresh-staging.sh
```

`refresh-staging.sh` resets the staging worktree to `origin/main`, then merges
every branch in `.claude/staging-branches.txt`. Stops on the first conflict so
you can resolve it in the staging worktree without polluting any feature
branch. When a feature ships to `main`, delete its line from
`.claude/staging-branches.txt`.

### Game state is shared

All servers (production, staging, any `--web-dir` previews) read/write
`state/games/` from the same place. A game launched on 8001 shows up in 8000's
lobby and vice versa.

## UI Mockups

Mockups live in `heist/mocks/`. Served at:

```
http://127.0.0.1:8000/mocks/                    # index
http://127.0.0.1:8000/mocks/<filename>.html     # specific mock
```

Drop a new HTML file in that folder and reload — no server restart needed. Mocks can call any `/api/*` endpoint since they're served from the same origin.

## Workflow

Default workflow for any Claude (or Codex) agent working in this repo.

### Staging Rule

**After every commit, always push to staging.** Commit → push branch → run `.claude/scripts/refresh-staging.sh`. No exceptions. The user reviews changes on staging at http://127.0.0.1:8001/ before shipping.

### Direct Path

```
Decide → optional spec → dispatch → verify → commit → push → refresh staging → /ship
```

- **Implementer for any medium/large coding task: Codex CLI** (`codex exec -m gpt-5.4-mini -s workspace-write`), run inside a worktree. This applies to **both backend and frontend** code — there is no "UI is operator-only" rule. After every Codex run, `git status` in the worktree (Codex doesn't always commit) and review its diff before shipping. (Codex CLI is *also* used as a *player* inside the game — separate role, both fine.)
- **Specs** for Codex dispatches must be self-contained (Codex has no memory of the conversation). Write the spec to a file (`specs/<name>.md` or `/tmp/codex-spec.txt`) and pass it via `$(cat …)`.
- **Inline edits** by the orchestrator for small changes (≤ ~30 lines, no design risk).
- **Merge always via `/ship`**, never `gh pr merge` directly. `/ship` runs preflight, watches CI, fixes the squash-drift trap (see below), and squash-merges.

### Preflight (run before every push)

```bash
python3 -m ruff check . && \
mypy heist/ agents.py demo.py && \
pytest -q
```

`/ship` runs this in Step 3. Run it locally first to skip CI roundtrips.

### The two lanes (game architecture)

The game is built on two lanes, and keeping them clean is the core design rule. **This is about how the game works, not about who writes the code.**

- **AI lane (the engine).** The engine generates **all** events. Every outcome and state change — a bid, the crew, a scene outcome, heat, a caught member, the take — is emitted as a discrete event. Nothing about display pacing or presentation lives in the compute path.
- **UI lane (the browser).** The UI does nothing but pick up those events and show them to the user. It never computes game state, and it never reconstructs context the events didn't provide.

**Implication for fixes:** if the UI is missing something (a name, the crew, an outcome), the fix is almost always to *emit it from the AI lane* — not to reconstruct it in the UI. A complete, self-sufficient event stream is the contract between the two lanes.

(Who *writes* the code is a separate matter — see "Implementer" above: Codex handles both backend and frontend.)

### Files that conflict often in parallel work

- `heist/server.py` — UI routes and backend hooks both land here
- `heist/runner.py` — stages refactor often
- `heist/web/shell.js` — both UI iteration and replay-model changes land here
- `README.md` / `ARCHITECTURE.md` — appended sections from multiple work streams; usually auto-merges

If a Codex task will touch one of these, don't run a second task that also edits it until the first merges.

### Squash-drift trap

After `/ship` squash-merges a PR, the branch's local commits live on as un-squashed equivalents. Re-pushing the same branch makes GitHub see `DIRTY/CONFLICTING` against main even though the content is identical. Recovery (codified in `/ship` Step 2):

```bash
git reset --hard origin/main
git cherry-pick <new-commit-sha>
git push --force-with-lease
```

### Feature Factory — available, opt-in

The shared Feature Factory skills (`/feature-spec` → `/feature-plan` → `/feature-tasks` → `/feature-implement`) live in `~/.claude/skills/` and are available in this repo. They are **not** the default here — for a project this size, **Direct Path covers everything**. Reach for the Feature Factory flow only when a change is big enough that Direct Path feels unsafe: data migrations, AI prompt audits across all call types, multi-day refactors. For those, prefer the structured spec → plan → tasks → implement flow over an ad-hoc "stop and discuss."

The flow writes artifacts under `specs/NNN-feature-name/`. The Codex-is-the-implementer rule (see Direct Path above) applies to **Direct Path only** — when you run the Feature Factory flow, `feature-implement` writes the code directly, no Codex dispatch. The Staging Rule still applies, and merges still go through `/ship`.

### What is still NOT here

No adversarial AI reviews by default. If a change feels big enough that even the Feature Factory flow is unsafe, stop and discuss before dispatching.

### Cross-references

- **Global spec-writing rules**: `~/.claude/rules/spec-writing.md`
- **Global agent-invocation rules**: `~/.claude/rules/agent-invocation.md`
- **Cross-session memory**: `~/.claude/projects/-Users-chrislaw-heist-game/memory/MEMORY.md`
