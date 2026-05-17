# heist-game

Game prototype that drives `codex` and `gemini` CLIs as NPC voices, using their
non-interactive modes with session resumption for per-NPC conversational continuity.

## Why subprocess + `--resume`

- Subscription billing on the CLIs (no per-token API spend)
- Both CLIs save sessions to disk and replay them on resume, so we get
  conversation memory across turns without re-sending the full transcript
- No PTY, no terminal emulator, no ACP — just `subprocess` and JSON parsing

## Files

- [`agents.py`](agents.py) — `ask_codex()` and `ask_gemini()`, both returning `Turn(text, session_id)`
- [`demo.py`](demo.py) — two-turn heist scene demonstrating state mutation + session resume

## Run

```sh
python3 demo.py
```

Requires `codex` and `gemini` on `PATH` and a signed-in session for each.

## Known gotchas

- `codex exec` blocks on stdin unless invoked with stdin closed (we pass `subprocess.DEVNULL`)
- `codex exec resume` doesn't accept `--sandbox` or `--output-schema` — those apply to the first turn only
- Gemini stdout can be prefixed with warning lines before the JSON object; we strip to the first `{`
- The model remembers narrative state via the transcript, but the game owns authoritative state — always pass a `<state>` block; never trust the model to remember HP / inventory / alarm status

## Next

When per-turn latency (~5–9s) becomes painful, switch to ACP via the
[`agent-client-protocol`](https://pypi.org/project/agent-client-protocol/) Python SDK
to keep one agent process warm for the whole game.
