"""Live viewer server — `python -m heist serve [--port N]`.

GET  /              → lobby.html
GET  /setup         → setup.html  (accepts ?game=ID)
GET  /viewer        → viewer.html

POST /api/new-game  → create a staged game, returns {game_id}
POST /api/add-ai    → {game_id, prompt, agent} → stage an AI onto a game
POST /api/launch    → {game_id} → start the game, returns {ok}
GET  /api/games     → all games (staged + running + done)
GET  /api/status    → {has_history, game_running}
GET  /api/meta      → roster + jobs
GET  /stream        → SSE event stream
"""
from __future__ import annotations

import http.server
import json
import queue
import random
import socketserver
import threading
import time
import traceback
from pathlib import Path

from heist.logs import log

# ── shared state ──────────────────────────────────────────────────────────────

_lock = threading.Lock()
_event_history: list[dict] = []
_subscribers: set[queue.Queue] = set()
_game_running = False

# All games: staged, running, done, error
# {id, created_at, status, ais:[{prompt,agent}], job, take, aborted, escape_success}
_games: dict[int, dict] = {}
_next_id = 1

_LOBBY_HTML  = Path(__file__).parent / "lobby.html"
_SETUP_HTML  = Path(__file__).parent / "web" / "setup.html"
_VIEWER_HTML = Path(__file__).parent / "viewer.html"
_MOCKS_DIR   = Path(__file__).parent / "mocks"


def _broadcast(event: dict) -> None:
    with _lock:
        _event_history.append(event)
        subs = list(_subscribers)
    log.info("broadcast", payload=event)
    for q in subs:
        q.put(event)


def _get_game(game_id: int) -> dict | None:
    with _lock:
        return _games.get(game_id)


def _update_game(game_id: int, **fields) -> None:
    with _lock:
        if game_id in _games:
            _games[game_id].update(fields)


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _Handler(http.server.BaseHTTPRequestHandler):

    def _http_log(self, method: str, t0: float) -> None:
        """Emit a structured access-log line. Skip /stream (long-lived SSE)."""
        path = self.path.split("?")[0]
        if path == "/stream":
            return
        status = getattr(self, "_status_code", None)
        log.info(
            "http",
            method=method,
            path=path,
            status=status,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    def send_response(self, code, message=None):
        # Capture the status code so the access log can report it.
        self._status_code = code
        super().send_response(code, message)

    def do_GET(self):
        t0 = time.monotonic()
        p = self.path.split("?")[0]
        try:
            self._dispatch_get(p)
        finally:
            self._http_log("GET", t0)

    def _dispatch_get(self, p: str) -> None:
        if p == "/":
            self._serve_file(_LOBBY_HTML)
        elif p == "/setup":
            self._serve_file(_SETUP_HTML)
        elif p == "/viewer":
            self._serve_file(_VIEWER_HTML)
        elif p == "/mocks" or p == "/mocks/":
            self._serve_mocks_index()
        elif p.startswith("/mocks/"):
            self._serve_mock(p[len("/mocks/"):])
        elif p == "/stream":
            self._serve_sse()
        elif p == "/api/meta":
            self._serve_meta()
        elif p == "/api/status":
            self._serve_status()
        elif p == "/api/games":
            self._serve_games()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        t0 = time.monotonic()
        p = self.path.split("?")[0]
        try:
            if p == "/api/new-game":
                self._handle_new_game()
            elif p == "/api/add-ai":
                self._handle_add_ai()
            elif p == "/api/launch":
                self._handle_launch()
            else:
                self.send_response(404)
                self.end_headers()
        finally:
            self._http_log("POST", t0)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── file serving ──

    def _serve_file(self, path: Path):
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_mock(self, name: str) -> None:
        # path-traversal guard: resolved path must stay inside _MOCKS_DIR
        candidate = (
            (_MOCKS_DIR / name)
            if name.endswith(".html")
            else (_MOCKS_DIR / name).with_suffix(".html")
        )
        try:
            resolved = candidate.resolve()
            mocks_root = _MOCKS_DIR.resolve()
            ok = (
                str(resolved).startswith(str(mocks_root) + "/")
                and resolved.is_file()
            )
        except OSError:
            ok = False
        if not ok:
            self.send_response(404)
            self.end_headers()
            return
        self._serve_file(resolved)

    def _serve_mocks_index(self) -> None:
        files = sorted(_MOCKS_DIR.glob("*.html")) if _MOCKS_DIR.is_dir() else []
        items = "".join(
            f'<li><a href="/mocks/{f.name}">{f.stem}</a></li>' for f in files
        ) or '<li class="empty">No mocks in heist/mocks/ yet.</li>'
        css = (
            "body{background:#0c0c0e;color:#e0dfe8;"
            "font-family:-apple-system,sans-serif;padding:48px;margin:0}"
            "h1{font-size:11px;letter-spacing:3px;color:#e8a030;"
            "text-transform:uppercase;margin:0 0 24px}"
            "ul{list-style:none;padding:0;margin:0;max-width:480px}"
            "li{padding:10px 14px;border:1px solid #26262c;border-radius:6px;"
            "margin-bottom:8px;background:#131316}"
            "li:hover{border-color:#3a3a44}"
            "li.empty{color:#72717a;font-style:italic;border-style:dashed}"
            "a{color:#e0dfe8;text-decoration:none;font-size:14px;"
            "font-weight:600;display:block}"
            "a::before{content:'▸ ';color:#e8a030;margin-right:4px}"
        )
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Mocks</title><style>" + css + "</style></head>"
            "<body><h1>Mocks</h1><ul>" + items + "</ul></body></html>"
        )
        data = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── API endpoints ──

    def _serve_meta(self):
        from heist.content import JOBS, ROSTER
        from heist.serialize import character_to_dict, job_to_dict
        self._json_ok({
            "roster": [character_to_dict(c) for c in ROSTER],
            "jobs": [job_to_dict(j) for j in JOBS],
        })

    def _serve_status(self):
        with _lock:
            self._json_ok({
                "has_history": len(_event_history) > 0,
                "game_running": _game_running,
            })

    def _serve_games(self):
        with _lock:
            games = list(_games.values())
        self._json_ok(sorted(games, key=lambda g: g["created_at"]))

    def _handle_new_game(self):
        global _next_id
        with _lock:
            gid = _next_id
            _next_id += 1
            _games[gid] = {
                "id": gid,
                "created_at": time.time(),
                "status": "staging",
                "ais": [],
                "job": None,
                "take": None,
                "aborted": None,
                "escape_success": None,
            }
        self._json_ok({"game_id": gid})

    def _handle_add_ai(self):
        body = self._read_json()
        game_id = body.get("game_id")
        prompt  = body.get("prompt", "")
        agent   = body.get("agent", "stub")
        game = _get_game(game_id)
        if not game:
            self._json_error(404, "game not found")
            return
        if game["status"] != "staging":
            self._json_error(409, "game is not in staging")
            return
        _update_game(game_id, ais=game["ais"] + [{"prompt": prompt, "agent": agent}])
        self._json_ok({"ok": True})

    def _handle_launch(self):
        global _game_running
        body = self._read_json()
        game_id = body.get("game_id")
        game = _get_game(game_id)
        if not game:
            self._json_error(404, "game not found")
            return
        if game["status"] != "staging":
            self._json_error(409, "game already launched or not staged")
            return
        if not game["ais"]:
            self._json_error(400, "no AIs configured")
            return
        with _lock:
            if _game_running:
                self._json_error(409, "another game is already running")
                return
            _game_running = True
            _event_history.clear()
            _games[game_id]["status"] = "running"

        self._json_ok({"ok": True})

        ai_cfg = game["ais"][0]  # Phase 1: single AI
        t = threading.Thread(
            target=_run_game,
            args=(ai_cfg["prompt"], ai_cfg["agent"], None, game_id),
            daemon=True,
        )
        t.start()

    # ── SSE ──

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        sub_q: queue.Queue = queue.Queue()
        with _lock:
            history = list(_event_history)
            _subscribers.add(sub_q)
        log.info("stream_connected", history_len=len(history))
        connected_at = time.monotonic()

        try:
            for evt in history:
                try:
                    self._send_event(evt)
                except (BrokenPipeError, ConnectionResetError):
                    return

            while True:
                try:
                    evt = sub_q.get(timeout=20)
                    if evt is None:
                        break
                    self._send_event(evt)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _lock:
                _subscribers.discard(sub_q)
            log.info(
                "stream_disconnected",
                duration_ms=int((time.monotonic() - connected_at) * 1000),
            )

    def _send_event(self, evt: dict) -> None:
        self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode())
        self.wfile.flush()

    # ── helpers ──

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _json_ok(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_error(self, code: int, message: str) -> None:
        data = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Default stderr access log is replaced by structured logs via _http_log.
        pass


# ── game runner thread ────────────────────────────────────────────────────────

def _run_game(strategy: str, agent: str, seed: int | None, game_id: int) -> None:
    global _game_running
    started_at = time.monotonic()
    log.info(
        "game_started",
        game_id=game_id,
        agent=agent,
        prompt_len=len(strategy),
        seed=seed,
    )
    try:
        from heist.ai import HeistAI
        from heist.backends import CodexHeistAI, GeminiHeistAI
        from heist.runner import run_heist
        from heist.serialize import state_to_dict
        from heist.stub_responses import build_stub_ai

        ai: HeistAI
        if agent == "stub":
            ai = build_stub_ai()
        elif agent == "codex":
            ai = CodexHeistAI(model="gpt-5.4")
        elif agent == "codex-mini":
            ai = CodexHeistAI(model="gpt-5.4-mini")
        elif agent == "gemini":
            ai = GeminiHeistAI()
        else:
            _broadcast({"type": "error", "message": f"Unknown agent: {agent}"})
            _update_game(game_id, status="error")
            log.error("game_crashed", game_id=game_id, error=f"Unknown agent: {agent}")
            return

        rng = random.Random(seed)
        state, extras = run_heist(strategy, ai, rng=rng, emit=_broadcast)

        _update_game(
            game_id,
            status="done",
            job=state.job.name,
            take=state.final_take,
            aborted=state.aborted,
            escape_success=state.escape_success,
        )
        _broadcast({
            "type": "game_done",
            "state": state_to_dict(state),
            "extras": {
                "casting_summary": extras.get("casting_summary", ""),
                "epilogue": extras.get("epilogue", ""),
                "strategy": extras.get("strategy", ""),
            },
        })
        log.info(
            "game_ended",
            game_id=game_id,
            take=state.final_take,
            aborted=state.aborted,
            escape_success=state.escape_success,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
    except Exception as exc:
        _update_game(game_id, status="error")
        _broadcast({"type": "error", "message": str(exc)})
        log.error(
            "game_crashed",
            game_id=game_id,
            error=str(exc),
            traceback=traceback.format_exc(),
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
    finally:
        _game_running = False


# ── server entry point ────────────────────────────────────────────────────────

class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def serve(port: int = 8000) -> None:
    server = _ThreadingServer(("", port), _Handler)
    print(f"Heist → http://localhost:{port}")
    print(f"Logging → {log.log_path()}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
