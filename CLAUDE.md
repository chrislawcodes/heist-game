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

## Server — One Canonical Instance

**Do not start a server from a worktree.** One server runs from `main` on port 8000.
Worktrees exist to edit code, not to run servers.

```bash
# Start once from main, leave running
python -m heist serve

# Preview a worktree's frontend changes against the running server
python -m heist serve --web-dir .claude/worktrees/WORKTREE_NAME/heist

# Test backend (Python) changes from a worktree on a separate port
python -m heist serve --port 8001 --web-dir .claude/worktrees/WORKTREE_NAME/heist
```

`--web-dir` points at the `heist/` subdirectory of any worktree. Game state in
`state/games/` is shared across all instances regardless of `--web-dir`.

## UI Mockups

Mockups live in `heist/web/mockups/`. The server mounts the whole `heist/web/` directory at `/web/`, so any file there is immediately viewable at:

```
http://127.0.0.1:8000/web/mockups/<filename>.html
```

Drop a new HTML file in that folder and reload — no server restart needed. Mockups can call the live `/api/heist` endpoint directly since they're served from the same origin.
