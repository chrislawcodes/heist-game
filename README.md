# heist-game

Single-player AI heist game. The player writes a strategy prompt; the **Heist AI**
drafts a crew, picks a job from a slate of three, and runs the heist scene by
scene. The system (deterministic Python) owns all mechanics: bid validation,
skill-vs-challenge resolution, hidden depth rolls, scene order, escape, reward.

Design doc: [`heist_game_design.md`](heist_game_design.md).
Build brief: [`build_phase_1_prompt.md`](build_phase_1_prompt.md).

## Status

**Iteration 1 — scaffold + stub AI + full scene loop.** Runnable end-to-end with
a hardcoded stub Heist AI. Real codex/gemini backends and polished content land
in subsequent iterations.

## Run

### CLI mode (writes a markdown file)

```sh
python3 -m heist --agent codex --seed 42 --out /tmp/heist.md
```

Flags:
- `--prompt-file PATH` — strategy prompt file (default: built-in default prompt)
- `--out PATH` — markdown output (default: `heist_report.md`)
- `--seed N` — RNG seed for reproducible hidden-depth rolls
- `--agent stub|codex|gemini` — Heist AI backend

### Browser mode (localhost web UI)

```sh
python3 -m heist serve --port 8000
# open http://localhost:8000
```

Three-screen app, single-user, localhost-only, zero extra dependencies
(uses the stdlib `http.server`). Flow: **Lobby** lets you start a new game
or browse history → **Setup wizard** builds your strategy prompt and picks
the AI → **Live viewer** streams the game with a draft board, crew columns,
and a persistent "thinking rail" showing per-AI private reasoning. Mocks
under `heist/mocks/<name>.html` are auto-served at `/mocks/<name>` for
design iteration.

## Architecture

| Module | Responsibility |
|---|---|
| `heist/state.py` | Dataclasses: `Character`, `Job`, `HiddenDepthElement`, `Scene`, `HeistState`, …; skill/challenge enums |
| `heist/content.py` | The 15-character `ROSTER` and 3-job slate (`MUSEUM`, `ARMORED_CAR`, `SERVER_FARM`); `DEFAULT_PROMPT` |
| `heist/mechanics.py` | Skill resolution, collaboration bonus, cost validation, escape resolution, job viability |
| `heist/scenes.py` | Scene-list generation from job profile + hidden depth roll |
| `heist/ai.py` | `HeistAI` Protocol + `StubHeistAI` + `parse_json_block()` |
| `heist/stub_responses.py` | Iteration 1 hardcoded AI |
| `heist/runner.py` | The heist loop: drafting → job selection → scene loop → escape → reward |
| `heist/output.py` | Markdown emission |
| `heist/__main__.py` | CLI entrypoint (writes a markdown file) |
| `heist/server.py` | FastAPI server for the browser UI; streams scenes via NDJSON |
| `heist/web/index.html` | Single-page browser UI (textarea + streaming output) |
| `agents.py` | Existing codex/gemini wrappers (used by iteration 3 once wired in) |

## Decisions on the design doc's "open items"

The build brief asks me to pick reasonable defaults for several unsettled items.
Here's what I chose:

| Open item | Choice |
|---|---|
| **Scene order** | Scene 1 = setup. Then one scene per Med/Hard challenge in canonical heist order: **social → electronic → physical → confrontation**. Hidden depth elements with `modifies` fold into the matching scene; `adds` produces a new scene; `bonus_with_cost` produces a decision-point scene before the transition. Penultimate = transition. Final = escape. |
| **Failure cascade** | Any challenge whose effective level is HARD is "core". **Fail core → ABORT.** Fail supporting / hidden-depth → heat += 1. Fail bonus pursuit → no bonus, no scaling penalty. Fail escape → reward = 0. |
| **Escape difficulty** | `difficulty = job.escape_modifier + heat`. Best Driver skill (no Driver = treated as Low) `>= difficulty` → success. |
| **Output format** | Markdown: `# Heist Report` → `## Strategy` → `## Casting` (incl. crew list + cost + job choice) → `## Heist` (one `### Scene N — title` per scene with italic personnel/reasoning/outcome meta block then prose) → `## Epilogue` → `## Outcome` (take, abort, escape, bonus, hidden depth, reward roll). |
| **Bid format** | JSON: `{ casting_strategy, bids: [{ character_id, bid, rationale }], reasoning }`. Bids ≥ floor, total ≤ $2000. (Earlier iterations had a `priority` field; removed once Phase 2's bid-resolution rules made it unnecessary — see [Phase 2 in the design doc](heist_game_design.md).) All other AI calls also return JSON; the runner parses defensively (strips chatter, finds first `{`). |
| **Heist AI backend** | Default = the codex/gemini wrappers in `agents.py` (subscription billing, no API spend). Iteration 1 uses a stub; iteration 3 wires up real calls with session resume for conversational continuity across all roles. |

### Known design-doc inconsistencies

The design doc says "Inside Man has no Low option — premium skill" but its
roster table lists Low Inside Man on Eli "Owl" Park (id 3) and Margot Vinter (id
14). The table is preserved as authoritative; the test
`test_low_inside_man_only_on_eli_and_margot` pins the contradiction so it
surfaces if the doc gets reconciled.

## Logs

The backend writes one JSON object per event to `./logs/heist.jsonl` (created on
first write). Override the destination with `HEIST_LOG_PATH=/path/to.jsonl`.
Every line carries `ts` (ISO-8601 UTC), `level`, `source` (caller's module), and
`event`, plus event-specific fields. Server startup prints
`Logging → <abs path>` so you know where to tail.

Useful events:
- `ai_call` / `ai_call_error` — per AI round (label, elapsed_ms, prompt_len, response_len, parsed_ok)
- `game_started` / `game_ended` / `game_crashed` — game lifecycle on the server
- `broadcast` — every SSE payload the server emits (full event under `payload`)
- `http` — access log for everything except `/stream`
- `stream_connected` / `stream_disconnected` — SSE lifecycle
- `subprocess_failed` / `subprocess_timeout` — codex/gemini CLI errors with captured stderr

Recipes:

```sh
# Five slowest AI calls
jq -s 'map(select(.event=="ai_call")) | sort_by(-.elapsed_ms) | .[0:5]' logs/heist.jsonl

# Any crashed games (full traceback)
jq 'select(.event=="game_crashed")' logs/heist.jsonl

# Average AI call time by label
jq -s 'map(select(.event=="ai_call")) | group_by(.label)
       | map({label: .[0].label, avg_ms: ((map(.elapsed_ms) | add) / length), n: length})' \
   logs/heist.jsonl

# Tail the live game stream
tail -f logs/heist.jsonl | jq -c 'select(.event=="broadcast") | .payload.type'
```

## Test policy

Every new feature ships with CI tests in the same commit. See
[`CLAUDE.md`](CLAUDE.md). Currently 38 tests covering mechanics, content
integrity, scene generation, and end-to-end runner.

## Iteration roadmap

1. ✅ Scaffold + stub AI + full scene loop end-to-end
2. Verify all 3 jobs run cleanly with the stub
3. Wire up real codex/gemini via `agents.py`
4. Polish content: 15 personality paragraphs + 3 location descriptions
5. End-to-end runs with default prompt + variations; tune for "done" criteria

## Related

- [`agents.py`](agents.py) — codex/gemini wrappers with session resume
- [`demo.py`](demo.py) — original two-turn smoke test for the wrappers
