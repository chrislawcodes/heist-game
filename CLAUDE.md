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
- Roster: 15 characters, locked
- Phase 1 jobs: Museum Gala, Armored Car, Corporate Server Farm
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

Mockups live in `heist/web/mockups/`. The server mounts the whole `heist/web/` directory at `/web/`, so any file there is immediately viewable at:

```
http://127.0.0.1:8000/web/mockups/<filename>.html
```

Drop a new HTML file in that folder and reload — no server restart needed. Mockups can call the live `/api/heist` endpoint directly since they're served from the same origin.
