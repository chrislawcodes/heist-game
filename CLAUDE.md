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
- Bankroll: $2,000
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
cd /Users/chrislaw/heist-game
python -m heist serve --port 8001 --web-dir .claude/worktrees/staging/heist

# Refresh staging whenever you want 8001 to reflect your latest feature work
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

- **Implementer** for substantial work: Sonnet subagent via the Agent tool with `isolation: "worktree"`. The subagent commits in its own worktree on a separate branch; the orchestrator merges that branch back. **Not** Codex CLI as an implementer — codex-mini is a *player* inside the game, not an agent that writes code here.
- **Specs** for non-trivial dispatches live inline in the Agent tool's `prompt` parameter. They must be self-contained: the subagent has no memory of the conversation.
- **Inline edits** by the orchestrator for small changes (≤ ~30 lines, no design risk).
- **Merge always via `/ship`**, never `gh pr merge` directly. `/ship` runs preflight, watches CI, fixes the squash-drift trap (see below), and squash-merges.

### Preflight (run before every push)

```bash
python3 -m ruff check . && \
mypy heist/ agents.py demo.py && \
pytest -q
```

`/ship` runs this in Step 3. Run it locally first to skip CI roundtrips.

### Lanes

| Lane | Files | Who |
|---|---|---|
| **UI** | `heist/hiring.html`, `heist/job.html`, `heist/heist.html`, `heist/epilogue.html`, `heist/lobby.html`, `heist/web/setup.html`, `heist/web/shell.js`, `heist/web/tabs/*.html`, `heist/mocks/*` | Operator + orchestrator. **Don't dispatch a subagent to UI files** — iteration is conversation-driven; a backgrounded agent will collide with live edits. |
| **Backend** | `heist/server.py`, `heist/runner.py`, `heist/persist.py`, `heist/serialize.py`, `heist/scenes.py`, `heist/mechanics.py`, `agents.py`, tests | Subagent territory. Dispatch with a comprehensive spec. |
| **Design / docs** | `heist_game_design.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `README.md` | Operator. Subagents may append sections (e.g. logging recipes, persistence layout); fine to merge. |

### Files that conflict often in parallel work

- `heist/server.py` — UI routes and backend hooks both land here
- `heist/runner.py` — stages refactor often
- `heist/web/shell.js` — both UI iteration and replay-model changes land here
- `README.md` / `ARCHITECTURE.md` — appended sections from multiple work streams; usually auto-merges

If a subagent will touch one of these, hold operator-side edits to that file until the merge.

### Squash-drift trap

After `/ship` squash-merges a PR, the branch's local commits live on as un-squashed equivalents. Re-pushing the same branch makes GitHub see `DIRTY/CONFLICTING` against main even though the content is identical. Recovery (codified in `/ship` Step 2):

```bash
git reset --hard origin/main
git cherry-pick <new-commit-sha>
git push --force-with-lease
```

### What is NOT here

No Feature Factory, no structured spec/plan/implement runner, no adversarial AI reviews by default. The project is at a scale where Direct Path covers everything. If a change feels big enough that Direct Path is unsafe (data migrations, AI prompt audits across all call types, multi-day refactors), stop and discuss before dispatching.

### Cross-references

- **Global spec-writing rules**: `~/.claude/rules/spec-writing.md`
- **Global agent-invocation rules**: `~/.claude/rules/agent-invocation.md`
- **Cross-session memory**: `~/.claude/projects/-Users-chrislaw-heist-game/memory/MEMORY.md`
