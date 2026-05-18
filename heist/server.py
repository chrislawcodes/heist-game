"""Live viewer server — `python -m heist serve [--port N]`.

GET  /              → lobby.html
GET  /setup         → setup.html  (accepts ?game=ID)
GET  /viewer        → viewer.html

POST /api/new-game  → create a staged game, returns {game_id}
POST /api/add-ai    → {game_id, prompt, agent} → stage an AI onto a game
POST /api/launch    → {game_id} → start the game, returns {ok}
POST /api/quick-game → preset: stage + launch 2× codex-mini AIs with the default prompt
GET  /api/games     → all games (staged + running + done)
GET  /api/games/<id>/events → full event history for a game (for replay)
GET  /api/status    → {has_history, game_running}
GET  /api/meta      → roster + jobs
GET  /stream        → SSE event stream
"""
from __future__ import annotations

import contextlib
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
from heist.persist import (
    delete_runner_snapshot,
    list_pending_snapshots,
    load_game_records,
    save_game_record,
    save_runner_snapshot,
)

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
_TABS_DIR    = Path(__file__).parent / "web" / "tabs"


def _broadcast(event: dict) -> None:
    persist_game: dict | None = None
    with _lock:
        _event_history.append(event)
        # Mirror into the relevant game's persistent event log so we can replay
        # it later via /api/games/{id}/events. We don't always know the game_id
        # on the event itself; fall back to the most-recently-running game.
        target_gid = None
        for gid in reversed(list(_games.keys())):
            if _games[gid].get("status") in ("running", "done"):
                target_gid = gid
                break
        if target_gid is not None:
            _games[target_gid].setdefault("events", []).append(event)
            # Snapshot the dict inside the lock; persist outside it so we
            # don't hold the lock during file I/O.
            persist_game = dict(_games[target_gid])
        subs = list(_subscribers)
    log.info("broadcast", payload=event)
    if persist_game is not None:
        try:
            save_game_record(persist_game)
        except Exception as exc:
            log.warn("save_game_record_failed", error=str(exc))
    for q in subs:
        q.put(event)


def _get_game(game_id: int) -> dict | None:
    with _lock:
        return _games.get(game_id)


def _update_game(game_id: int, **fields) -> None:
    persist_game: dict | None = None
    with _lock:
        if game_id in _games:
            _games[game_id].update(fields)
            persist_game = dict(_games[game_id])
    if persist_game is not None:
        try:
            save_game_record(persist_game)
        except Exception as exc:
            log.warn("save_game_record_failed", error=str(exc))


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
        elif p.startswith("/tabs/"):
            self._serve_tab(p[len("/tabs/"):])
        elif p == "/stream":
            self._serve_sse()
        elif p == "/api/meta":
            self._serve_meta()
        elif p == "/api/status":
            self._serve_status()
        elif p == "/api/games":
            self._serve_games()
        elif p.startswith("/api/games/") and p.endswith("/events"):
            self._serve_game_events(p[len("/api/games/"):-len("/events")])
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
            elif p == "/api/quick-game":
                self._handle_quick_game()
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

    def _serve_tab(self, name: str) -> None:
        """Serve a tab fragment from web/tabs/<name>.html. The viewer shell
        fetches these at boot to compose the multi-tab UI."""
        # path-traversal guard: resolved path must stay inside _TABS_DIR
        candidate = (
            (_TABS_DIR / name)
            if name.endswith(".html")
            else (_TABS_DIR / name).with_suffix(".html")
        )
        try:
            resolved = candidate.resolve()
            tabs_root = _TABS_DIR.resolve()
            ok = (
                str(resolved).startswith(str(tabs_root) + "/")
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
            # Strip the heavy events list from the index; clients fetch them
            # explicitly via /api/games/<id>/events when they need to replay.
            games = [{k: v for k, v in g.items() if k != "events"} for g in _games.values()]
        self._json_ok(sorted(games, key=lambda g: g["created_at"]))

    def _serve_game_events(self, gid_str: str) -> None:
        try:
            gid = int(gid_str)
        except ValueError:
            self._json_error(400, "bad game id")
            return
        with _lock:
            game = _games.get(gid)
            if not game:
                self._json_error(404, "game not found")
                return
            events = list(game.get("events", []))
        self._json_ok({"game_id": gid, "events": events})

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
            _games[game_id]["ai_results"] = [None] * len(game["ais"])
            _games[game_id]["ais_remaining"] = len(game["ais"])

        self._json_ok({"ok": True})

        for ai_idx, ai_cfg in enumerate(game["ais"]):
            t = threading.Thread(
                target=_run_game,
                args=(ai_cfg["prompt"], ai_cfg["agent"], None, game_id, ai_idx),
                daemon=True,
            )
            t.start()

    def _handle_quick_game(self):
        """One-click "test production" preset: stage + launch 2 codex-mini AIs
        with the default prompt."""
        global _next_id, _game_running
        from heist.content import DEFAULT_PROMPT
        with _lock:
            if _game_running:
                self._json_error(409, "another game is already running")
                return
            gid = _next_id
            _next_id += 1
            ais = [
                {"prompt": DEFAULT_PROMPT, "agent": "codex-mini"},
                {"prompt": DEFAULT_PROMPT, "agent": "codex-mini"},
            ]
            _games[gid] = {
                "id": gid,
                "created_at": time.time(),
                "status": "running",
                "ais": ais,
                "ai_results": [None] * len(ais),
                "ais_remaining": len(ais),
                "job": None,
                "take": None,
                "aborted": None,
                "escape_success": None,
                "quick_test": True,
            }
            _game_running = True
            _event_history.clear()
        self._json_ok({"game_id": gid, "ok": True})
        for ai_idx, ai_cfg in enumerate(ais):
            t = threading.Thread(
                target=_run_game,
                args=(ai_cfg["prompt"], ai_cfg["agent"], None, gid, ai_idx),
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

def _run_game(
    strategy: str,
    agent: str,
    seed: int | None,
    game_id: int,
    ai_idx: int = 0,
    resume_snapshot: dict | None = None,
) -> None:
    global _game_running
    started_at = time.monotonic()
    log.info(
        "game_started" if resume_snapshot is None else "game_resumed",
        game_id=game_id,
        ai_idx=ai_idx,
        agent=agent,
        prompt_len=len(strategy),
        seed=seed,
    )

    def emit_tagged(evt: dict) -> None:
        _broadcast({**evt, "ai_idx": ai_idx})

    def snapshot_cb(payload: dict) -> None:
        payload = {**payload, "game_id": game_id, "ai_idx": ai_idx, "agent": agent}
        try:
            save_runner_snapshot(game_id, ai_idx, payload)
        except Exception as exc:
            log.warn("save_runner_snapshot_failed",
                     game_id=game_id, ai_idx=ai_idx, error=str(exc))

    def _record_result(result: dict) -> None:
        """Stash this AI's outcome in game["ai_results"][ai_idx]; flip game-level
        status to "done" once every AI has finished."""
        global _game_running
        persist_game: dict | None = None
        with _lock:
            game = _games.get(game_id)
            if not game:
                return
            results = game.setdefault("ai_results", [None] * len(game.get("ais", [])))
            if ai_idx < len(results):
                results[ai_idx] = result
            # Keep top-level summary fields backed by AI 0 (for lobby display).
            if ai_idx == 0 and "error" not in result:
                game.update({
                    "job": result.get("job"),
                    "take": result.get("take"),
                    "aborted": result.get("aborted"),
                    "escape_success": result.get("escape_success"),
                })
            game["ais_remaining"] = max(0, game.get("ais_remaining", 1) - 1)
            if game["ais_remaining"] == 0:
                game["status"] = "done"
                _game_running = False
            persist_game = dict(game)
        if persist_game is not None:
            try:
                save_game_record(persist_game)
            except Exception as exc:
                log.warn("save_game_record_failed",
                         game_id=game_id, error=str(exc))

    try:
        from heist.ai import HeistAI
        from heist.backends import CodexHeistAI, GeminiHeistAI
        from heist.runner import resume_heist, run_heist
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
            err = f"Unknown agent: {agent}"
            emit_tagged({"type": "error", "message": err})
            log.error("game_crashed", game_id=game_id, ai_idx=ai_idx, error=err)
            _record_result({"error": err})
            return

        if resume_snapshot is not None:
            # Re-attach the codex session so the CLI picks up the in-flight
            # conversation. If the session has expired on disk, the next AI
            # call will fail and we mark this AI errored — same path as any
            # other AI failure, no special-case logic needed.
            sid = resume_snapshot.get("session_id")
            if sid and hasattr(ai, "session_id"):
                ai.session_id = sid
            state, extras = resume_heist(
                resume_snapshot, ai, emit=emit_tagged, snapshot_fn=snapshot_cb,
            )
        else:
            # Different seed per AI so parallel runs diverge meaningfully.
            rng_seed = seed if seed is not None else random.randint(0, 1 << 30) + ai_idx
            rng = random.Random(rng_seed)
            state, extras = run_heist(
                strategy, ai, rng=rng, emit=emit_tagged, snapshot_fn=snapshot_cb,
            )

        emit_tagged({
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
            ai_idx=ai_idx,
            take=state.final_take,
            aborted=state.aborted,
            escape_success=state.escape_success,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        _record_result({
            "job": state.job.name,
            "take": state.final_take,
            "aborted": state.aborted,
            "escape_success": state.escape_success,
        })
        # Snapshot served its purpose — clean up so the recovery path doesn't
        # try to re-resume a finished game.
        try:
            delete_runner_snapshot(game_id, ai_idx)
        except Exception as exc:
            log.warn("delete_snapshot_failed",
                     game_id=game_id, ai_idx=ai_idx, error=str(exc))
    except Exception as exc:
        emit_tagged({"type": "error", "message": str(exc)})
        log.error(
            "game_crashed",
            game_id=game_id,
            ai_idx=ai_idx,
            error=str(exc),
            traceback=traceback.format_exc(),
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        _record_result({"error": str(exc)})
        with contextlib.suppress(Exception):
            delete_runner_snapshot(game_id, ai_idx)


# ── server entry point ────────────────────────────────────────────────────────

class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def _recover_games() -> tuple[int, int]:
    """Reload games + snapshots from ``./state/``, spawn resume threads for
    any AI that was mid-run when the server stopped. Returns
    (games_recovered, ai_threads_resuming)."""
    global _next_id, _game_running
    records = load_game_records()
    if not records:
        return (0, 0)

    games_recovered = 0
    ai_resuming = 0
    pending: list[tuple[int, int, dict, dict]] = []  # (gid, ai_idx, snap, ai_cfg)

    with _lock:
        for gid, record in records.items():
            _games[gid] = record
            _next_id = max(_next_id, gid + 1)
            games_recovered += 1

            if record.get("status") != "running":
                continue

            ais = record.get("ais", [])
            results = record.get("ai_results") or [None] * len(ais)
            # Pad in case of a stale file.
            if len(results) < len(ais):
                results = results + [None] * (len(ais) - len(results))

            snapshots = list_pending_snapshots(gid)
            still_remaining = 0
            for ai_idx, ai_cfg in enumerate(ais):
                if results[ai_idx] is not None:
                    continue
                if ai_idx in snapshots:
                    pending.append((gid, ai_idx, snapshots[ai_idx], ai_cfg))
                    still_remaining += 1
                else:
                    # No snapshot — game crashed before this AI made any
                    # observable progress. Mark it errored and move on.
                    results[ai_idx] = {"error": "no snapshot — crashed before first turn"}

            record["ai_results"] = results
            record["ais_remaining"] = still_remaining
            if still_remaining == 0:
                record["status"] = "done"
            else:
                _game_running = True

            ai_resuming += still_remaining

    # Persist any status flips we made above (errored AIs, status→done).
    for gid in records:
        try:
            with _lock:
                snap = dict(_games[gid])
            save_game_record(snap)
        except Exception as exc:
            log.warn("save_game_record_failed", game_id=gid, error=str(exc))

    for gid, ai_idx, snap, ai_cfg in pending:
        log.info("game_recovered", game_id=gid, ai_idx=ai_idx,
                 stage=snap.get("stage"), scene_idx=snap.get("scene_idx"))
        t = threading.Thread(
            target=_run_game,
            args=(ai_cfg.get("prompt", ""), ai_cfg.get("agent", "stub"),
                  None, gid, ai_idx),
            kwargs={"resume_snapshot": snap},
            daemon=True,
        )
        t.start()

    return (games_recovered, ai_resuming)


def serve(port: int = 8000) -> None:
    games_recovered, ai_resuming = _recover_games()
    server = _ThreadingServer(("", port), _Handler)
    print(f"Heist → http://localhost:{port}")
    if games_recovered > 0:
        print(f"Recovered {games_recovered} games "
              f"({ai_resuming} AI threads resuming)")
    print(f"Logging → {log.log_path()}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
