"""Live viewer server — `python -m heist serve [--port N]`.

GET  /              → lobby.html
GET  /setup         → setup.html  (accepts ?game=ID)
GET  /hiring        → hiring.html  (phase 1 — ?game=ID)
GET  /job           → job.html     (phase 2 — ?game=ID)
GET  /heist         → heist.html   (phase 3 — ?game=ID)
GET  /epilogue      → epilogue.html (phase 4 — ?game=ID)
GET  /shell.js      → web/shell.js  (shared JS module)
GET  /portraits/<id> → heist/characters/c<id>_*.jpeg (or .jpg) — serves portrait by character id

POST /api/new-game  → create a staged game, returns {game_id}
POST /api/add-ai    → {game_id, prompt, agent} → stage an AI onto a game
POST /api/launch    → {game_id} → start the game, returns {ok}
POST /api/quick-game → preset: stage + launch 2× codex-mini AIs with the default prompt
GET  /api/games     → all games (staged + running + done)
GET  /api/games/<id>/events → full event history for a game (for replay)
DELETE /api/games/<id> → remove a non-running game (record + snapshots)
GET  /api/status    → {has_history, game_running}
GET  /api/meta      → roster + jobs
GET  /stream        → SSE event stream
"""
from __future__ import annotations

import http.server
import json
import queue
import socketserver
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from heist import gamestate, orchestration
from heist.logs import log
from heist.persist import (
    delete_game_record,
    delete_runner_snapshot,
    list_pending_snapshots,
    save_game_record,
)

_LOBBY_HTML    = Path(__file__).parent / "lobby.html"
_SETUP_HTML    = Path(__file__).parent / "web" / "setup.html"
_HIRING_HTML   = Path(__file__).parent / "hiring.html"
_JOB_HTML      = Path(__file__).parent / "job.html"
_HEIST_HTML    = Path(__file__).parent / "heist.html"
_EPILOGUE_HTML = Path(__file__).parent / "epilogue.html"
_CAMPAIGN_HTML = Path(__file__).parent / "campaign.html"
_SHELL_JS      = Path(__file__).parent / "web" / "shell.js"
_MOCKS_DIR       = Path(__file__).parent / "mocks"
_TABS_DIR        = Path(__file__).parent / "web" / "tabs"
_PORTRAITS_DIR   = Path(__file__).parent / "characters"


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
        elif p == "/hiring":
            self._serve_file(_HIRING_HTML)
        elif p == "/job":
            self._serve_file(_JOB_HTML)
        elif p == "/heist":
            self._serve_file(_HEIST_HTML)
        elif p == "/epilogue":
            self._serve_file(_EPILOGUE_HTML)
        elif p == "/campaign" or p.startswith("/campaign/"):
            self._serve_file(_CAMPAIGN_HTML)
        elif p == "/shell.js":
            self._serve_js(_SHELL_JS)
        elif p == "/mocks" or p == "/mocks/":
            self._serve_mocks_index()
        elif p.startswith("/mocks/"):
            self._serve_mock(p[len("/mocks/"):])
        elif p.startswith("/portraits/"):
            self._serve_portrait(p[len("/portraits/"):])
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
        elif p == "/api/campaigns":
            self._serve_campaigns()
        elif p.startswith("/api/campaign/") and p.endswith("/state"):
            self._serve_campaign_state(p[len("/api/campaign/"):-len("/state")])
        elif p.startswith("/api/campaign-journey/"):
            self._serve_campaign_journey(p[len("/api/campaign-journey/"):])
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
            elif p == "/api/new-campaign":
                self._handle_new_campaign()
            elif p == "/api/add-ai":
                self._handle_add_ai()
            elif p == "/api/launch":
                self._handle_launch()
            elif p == "/api/quick-game":
                self._handle_quick_game()
            elif p == "/api/quick-campaign":
                self._handle_quick_campaign()
            elif p == "/api/medium-campaign":
                self._handle_medium_campaign()
            elif p.startswith("/api/campaign/") and p.endswith("/resume"):
                self._handle_resume_campaign(
                    p[len("/api/campaign/"):-len("/resume")]
                )
            else:
                self.send_response(404)
                self.end_headers()
        finally:
            self._http_log("POST", t0)

    def do_DELETE(self):
        t0 = time.monotonic()
        p = self.path.split("?")[0]
        try:
            # /api/games/<id>
            if p.startswith("/api/games/") and "/" not in p[len("/api/games/"):]:
                qs = self.path.split("?", 1)[1] if "?" in self.path else ""
                force = "force=1" in qs
                self._handle_delete_game(p[len("/api/games/"):], force=force)
            else:
                self.send_response(404)
                self.end_headers()
        finally:
            self._http_log("DELETE", t0)

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

    def _serve_js(self, path: Path):
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
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

    def _serve_portrait(self, char_id_str: str) -> None:
        """Serve a character portrait by id.

        URL: /portraits/9  →  heist/characters/c09_pearl.jpeg (or .jpg)
        Falls back to 404 if the file doesn't exist yet — the frontend
        onerror handler hides the <img> and shows the initials fallback.
        """
        try:
            char_id = int(char_id_str)
        except ValueError:
            self.send_response(404)
            self.end_headers()
            return
        prefix = f"c{char_id:02d}_"
        portrait: Path | None = None
        for ext in (".jpeg", ".jpg"):
            matches = list(_PORTRAITS_DIR.glob(f"{prefix}*{ext}"))
            if matches:
                portrait = matches[0]
                break
        if portrait is None or not portrait.is_file():
            self.send_response(404)
            self.end_headers()
            return
        content = portrait.read_bytes()
        mime = "image/jpeg"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

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
        with gamestate.lock:
            self._json_ok({
                "has_history": len(gamestate.event_history) > 0,
                "game_running": gamestate.runtime.game_running,
            })

    def _serve_games(self):
        with gamestate.lock:
            # Strip the heavy events list from the index; clients fetch them
            # explicitly via /api/games/<id>/events when they need to replay.
            games = [
                {k: v for k, v in g.items() if k != "events"}
                for g in gamestate.games.values()
            ]
        self._json_ok(sorted(games, key=lambda g: g["created_at"]))

    def _serve_campaigns(self):
        with gamestate.lock:
            records = [
                dict(game)
                for game in gamestate.games.values()
                if game.get("is_campaign") is True and not game.get("is_campaign_sub")
            ]

        payload: list[dict] = []
        for game in records:
            game_states = game.get("game_states") or []
            current_round = max(
                (len(gs.get("round_results", []) or []) for gs in game_states),
                default=0,
            )
            ais: list[dict] = []
            for idx, gs in enumerate(game_states):
                ais.append({
                    "ai_idx": int(gs.get("ai_idx", idx)),
                    "ai_name": gs.get("ai_name", f"AI {idx + 1}"),
                    "banked": int(gs.get("banked_loot", gs.get("banked", 0))),
                    "status": gs.get("status", "waiting"),
                })
            payload.append({
                "id": int(game["id"]),
                "status": game.get("status", "running"),
                "name": game.get("name") or None,
                "num_rounds": int(game.get("num_rounds", 5)),
                "created_at": float(game.get("created_at", 0.0)),
                "current_round": current_round,
                "current_round_idx": int(game.get("current_round_idx", 0)),
                "current_stage": game.get("current_stage"),
                "progress": game.get("progress"),
                "ais": ais,
            })
        payload.sort(key=lambda row: row["created_at"], reverse=True)
        self._json_ok(payload)

    def _serve_campaign_state(self, gid_str: str) -> None:
        try:
            gid = int(gid_str)
        except ValueError:
            self._json_error(404, "not found")
            return
        with gamestate.lock:
            game = gamestate.games.get(gid)
            if not game:
                self._json_error(404, "not found")
                return
            game = dict(game)

        from heist.content import ROSTER
        from heist.serialize import campaign_from_dict, campaign_state_to_dict

        campaign_payload = game.get("campaign_state")
        game_states = (
            game.get("game_states")
            or game.get("ais_states")
            or game.get("campaign_game_states")
        )
        if campaign_payload is None and isinstance(game.get("campaign"), dict):
            campaign_payload = game["campaign"]
        if (
            campaign_payload is None
            and {"rounds_total", "bankroll", "banked_loot"} <= set(game.keys())
        ):
            campaign_payload = game
        if not isinstance(campaign_payload, dict):
            self._json_error(404, "not found")
            return
        if {"round", "total_rounds", "standings", "wire"} <= set(campaign_payload.keys()):
            if campaign_payload.get("progress") is None:
                campaign_payload = {
                    **campaign_payload,
                    "progress": game.get("progress"),
                }
            self._json_ok(campaign_payload)
            return
        if game_states is None:
            self._json_error(404, "not found")
            return

        campaign = campaign_from_dict(campaign_payload)
        game_current_stage = game.get("current_stage", "done")
        game_current_round_idx = int(game.get("current_round_idx", 0))
        payload = campaign_state_to_dict(
            campaign, game_states, ROSTER,
            current_stage=game_current_stage,
            current_round_idx=game_current_round_idx,
            progress=game.get("progress"),
        )
        self._json_ok(payload)

    def _serve_campaign_journey(self, gid_str: str) -> None:
        try:
            gid = int(gid_str)
        except ValueError:
            self._json_error(404, "not found")
            return

        with gamestate.lock:
            game = gamestate.games.get(gid)
            if not game or game.get("is_campaign") is not True:
                self._json_error(404, "not found")
                return
            game = dict(game)

        game_states = list(game.get("game_states") or [])
        num_rounds = int(game.get("num_rounds", len(game_states)))
        current_round_idx = int(game.get("current_round_idx", 0))

        def _outcome_for(round_results: list, round_idx: int) -> dict:
            if round_idx < len(round_results):
                entry = round_results[round_idx]
                if isinstance(entry, dict):
                    take = int(entry.get("take", 0))
                    escape_success = entry.get("escape_success")
                    aborted = bool(entry.get("aborted", False))
                else:
                    take = int(getattr(entry, "take", 0))
                    escape_success = getattr(entry, "escape_success", None)
                    aborted = bool(getattr(entry, "aborted", False))
                return {
                    "take": take,
                    "escape_success": escape_success,
                    "aborted": aborted,
                }
            return {"take": 0, "escape_success": None, "aborted": False}

        teams: list[dict] = []
        for idx, gs in enumerate(game_states):
            round_game_ids = list(gs.get("round_game_ids", []) or [])
            hiring_game_ids = list(gs.get("hiring_game_ids", []) or [])
            round_results = list(gs.get("round_results", []) or [])
            rounds: list[dict] = []
            for round_idx in range(num_rounds):
                rounds.append({
                    "round_idx": round_idx,
                    "hire_sub_game_id": (
                        hiring_game_ids[round_idx]
                        if round_idx < len(hiring_game_ids)
                        else None
                    ),
                    "heist_sub_game_id": (
                        round_game_ids[round_idx]
                        if round_idx < len(round_game_ids)
                        else None
                    ),
                    "outcome": _outcome_for(round_results, round_idx),
                })
            teams.append({
                "ai_idx": int(gs.get("ai_idx", idx)),
                "team_name": gs.get("ai_name", f"AI {idx + 1}"),
                "banked": int(gs.get("banked_loot", gs.get("banked", 0))),
                "rounds": rounds,
            })

        teams.sort(key=lambda row: row["ai_idx"])
        self._json_ok({
            "campaign_id": gid,
            "num_rounds": num_rounds,
            "current_round_idx": current_round_idx,
            "teams": teams,
        })

    def _serve_game_events(self, gid_str: str) -> None:
        try:
            gid = int(gid_str)
        except ValueError:
            self._json_error(400, "bad game id")
            return
        with gamestate.lock:
            game = gamestate.games.get(gid)
            if not game:
                self._json_error(404, "game not found")
                return
            events = list(game.get("events", []))
        self._json_ok({"game_id": gid, "events": events})

    def _handle_new_game(self):
        with gamestate.lock:
            gid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            gamestate.games[gid] = {
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

    def _handle_new_campaign(self):
        try:
            body = self._read_json()
        except Exception:
            self._json_error(400, "invalid campaign payload")
            return

        def bad(msg: str) -> None:
            self._json_error(400, msg)

        num_rounds = body.get("num_rounds", 5)
        if (
            not isinstance(num_rounds, int)
            or isinstance(num_rounds, bool)
            or num_rounds < 1
            or num_rounds > 20
        ):
            bad("num_rounds must be an int between 1 and 20")
            return

        ais = body.get("ais", [])
        if not isinstance(ais, list) or not (1 <= len(ais) <= 6):
            bad("ais must be a non-empty list with 1 to 6 entries")
            return

        normalized_ais: list[dict] = []
        for i, ai_cfg in enumerate(ais):
            if not isinstance(ai_cfg, dict):
                bad(f"ai {i + 1} must be an object")
                return
            prompt = ai_cfg.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                bad(f"ai {i + 1} prompt must be a non-empty string")
                return
            name = ai_cfg.get("name", f"AI {i + 1}")
            if not isinstance(name, str) or not name.strip():
                name = f"AI {i + 1}"
            agent = ai_cfg.get("agent", "stub")
            if not isinstance(agent, str) or not agent.strip():
                agent = "stub"
            normalized_ais.append({
                "name": name,
                "prompt": prompt,
                "agent": agent,
            })

        with gamestate.lock:
            gid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            game = {
                "id": gid,
                "created_at": time.time(),
                "status": "running",
                "is_campaign": True,
                "num_rounds": num_rounds,
                "ais_remaining": len(normalized_ais),
                "ais_cfg": normalized_ais,
                "current_stage": "starting",
                "current_round_idx": 0,
                "campaign_state": {
                    "rounds_total": num_rounds,
                    "banked_loot": 0,
                    "bankroll": 0,
                    "standing_crew": [],
                    "round_results": [],
                    "between_round_log": [],
                },
                "game_states": [
                    {
                        "ai_idx": i,
                        "ai_name": ai["name"],
                        "ai_game_id": None,
                        "status": "waiting",
                        "banked_loot": 0,
                        "standing_crew": [],
                        "round_results": [],
                    }
                    for i, ai in enumerate(normalized_ais)
                ],
            }
            gamestate.games[gid] = game

        save_game_record(dict(game))

        t = threading.Thread(
            target=orchestration.run_campaign_conductor,
            args=(gid, num_rounds),
            daemon=True,
        )
        t.start()

        self._json_ok({"campaign_id": gid})

    def _handle_add_ai(self):
        body = self._read_json()
        game_id = body.get("game_id")
        prompt  = body.get("prompt", "")
        agent   = body.get("agent", "stub")
        game = gamestate.get_game(game_id)
        if not game:
            self._json_error(404, "game not found")
            return
        if game["status"] != "staging":
            self._json_error(409, "game is not in staging")
            return
        gamestate.update_game(game_id, ais=game["ais"] + [{"prompt": prompt, "agent": agent}])
        self._json_ok({"ok": True})

    def _handle_launch(self):
        body = self._read_json()
        game_id = body.get("game_id")
        game = gamestate.get_game(game_id)
        if not game:
            self._json_error(404, "game not found")
            return
        if game["status"] != "staging":
            self._json_error(409, "game already launched or not staged")
            return
        if not game["ais"]:
            self._json_error(400, "no AIs configured")
            return
        with gamestate.lock:
            if gamestate.runtime.game_running:
                self._json_error(409, "another game is already running")
                return
            gamestate.runtime.game_running = True
            gamestate.event_history.clear()
            gamestate.games[game_id]["status"] = "running"
            gamestate.games[game_id]["ai_results"] = [None] * len(game["ais"])
            gamestate.games[game_id]["ais_remaining"] = len(game["ais"])

        self._json_ok({"ok": True})
        t = threading.Thread(
            target=orchestration.run_auction_coordinator,
            args=(game_id,),
            daemon=True,
        )
        t.start()

    def _handle_resume_campaign(self, id_str: str) -> None:
        """Manually revive a stalled campaign (record still "running" but its
        conductor thread is gone) without restarting the server.

        404 no such campaign · 422 not resumable (not a campaign / not running /
        no checkpoint_version) · 409 a live conductor already owns it.
        """
        try:
            cid = int(id_str)
        except (TypeError, ValueError):
            self._json_error(404, "no such campaign")
            return
        game = gamestate.get_game(cid)
        if not game:
            self._json_error(404, "no such campaign")
            return
        # Only a checkpointed, still-"running" campaign is resumable. A done or
        # interrupted campaign (the latter predates checkpointing) cannot be
        # continued — it would have to restart from round 0.
        if (
            not game.get("is_campaign")
            or game.get("status") != "running"
            or int(game.get("checkpoint_version", 0) or 0) < 1
        ):
            self._json_error(422, "campaign not resumable")
            return
        # A live conductor for this id means it isn't actually stalled.
        with gamestate.lock:
            if cid in gamestate.runtime.active_campaigns:
                self._json_error(409, "campaign already running")
                return
        num_rounds = int(game.get("num_rounds", 0) or 0)
        resumed_from = {
            "round_idx": int(game.get("current_round_idx", 0) or 0),
            "stage": game.get("current_stage") or "opening_wire",
        }
        t = threading.Thread(
            target=orchestration.run_campaign_conductor,
            args=(cid, num_rounds),
            kwargs={"resume": True},
            name=f"campaign-resume-{cid}",
            daemon=True,
        )
        t.start()
        self._json_ok({
            "ok": True,
            "campaign_id": cid,
            "resumed_from": resumed_from,
        })

    def _handle_quick_game(self):
        """One-click preset: launch the two QUICK_TEST_TEAMS (The Operators and
        The Wreckers) head-to-head against the same roster + job slate. Each
        gets a different strategy prompt so the player can watch contrasting
        philosophies play the same game."""
        from heist.content import QUICK_TEST_TEAMS
        with gamestate.lock:
            if gamestate.runtime.game_running:
                self._json_error(409, "another game is already running")
                return
            gid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            # Take a defensive copy so the persisted record doesn't share
            # references with the module-level preset.
            ais = [dict(team) for team in QUICK_TEST_TEAMS]
            gamestate.games[gid] = {
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
            gamestate.runtime.game_running = True
            gamestate.event_history.clear()
        self._json_ok({"game_id": gid, "ok": True})
        t = threading.Thread(
            target=orchestration.run_auction_coordinator,
            args=(gid,),
            daemon=True,
        )
        t.start()

    def _handle_medium_campaign(self) -> None:
        """Medium Test preset: same three AIs as Quick Test, but 7 rounds."""
        from heist.content import MEDIUM_TEST_CAMPAIGN_ROUNDS
        self._handle_quick_campaign(num_rounds=MEDIUM_TEST_CAMPAIGN_ROUNDS)

    def _handle_quick_campaign(self, num_rounds: int | None = None) -> None:
        """One-click preset campaign with three contrasting codex-mini AIs —
        The Operators, The Wreckers, and The Ghost. Quick Test runs 3 rounds;
        Medium Test passes num_rounds=7."""
        from heist.content import QUICK_TEST_CAMPAIGN, QUICK_TEST_CAMPAIGN_ROUNDS
        if num_rounds is None:
            num_rounds = QUICK_TEST_CAMPAIGN_ROUNDS
        _pt = ZoneInfo("America/Los_Angeles")
        _now = datetime.now(_pt)
        _campaign_name = _now.strftime("%A %B %-d, %-I:%M %p PT")
        with gamestate.lock:
            gid = gamestate.runtime.next_id
            gamestate.runtime.next_id += 1
            ais = [dict(team) for team in QUICK_TEST_CAMPAIGN]
            gamestate.games[gid] = {
                "id": gid,
                "created_at": time.time(),
                "status": "running",
                "is_campaign": True,
                "name": _campaign_name,
                "num_rounds": num_rounds,
                "ais_remaining": len(ais),
                "ais_cfg": ais,
                "current_stage": "starting",
                "current_round_idx": 0,
                "quick_test": True,
                "campaign_state": {
                    "rounds_total": num_rounds, "banked_loot": 0,
                    "bankroll": 0, "standing_crew": [],
                    "round_results": [],
                    "between_round_log": [],
                },
                "game_states": [
                    {"ai_idx": i, "ai_name": ai["name"], "ai_game_id": None,
                     "status": "waiting", "banked_loot": 0,
                     "standing_crew": [], "round_results": []}
                    for i, ai in enumerate(ais)
                ],
            }
        try:
            save_game_record(dict(gamestate.games[gid]))
        except Exception as exc:
            log.warn("quick_campaign_persist_failed", error=str(exc))
        self._json_ok({"campaign_id": gid, "ok": True})
        t = threading.Thread(
            target=orchestration.run_campaign_conductor,
            args=(gid, num_rounds),
            daemon=True,
        )
        t.start()

    def _handle_delete_game(self, gid_str: str, *, force: bool = False) -> None:
        """Remove a game: drop it from the in-memory dict and delete both the
        persisted record and any per-AI runner snapshots. Pass force=True to
        delete a still-running game (useful for stuck campaigns)."""
        try:
            gid = int(gid_str)
        except ValueError:
            self._json_error(400, "bad game id")
            return
        with gamestate.lock:
            game = gamestate.games.get(gid)
            if not game:
                self._json_error(404, "game not found")
                return
            if game.get("status") == "running" and not force:
                self._json_error(
                    409,
                    "game is running — pass ?force=1 to delete it anyway",
                )
                return
            # Drop the in-memory record so future /api/games calls don't see it.
            gamestate.games.pop(gid, None)
        # Best-effort cleanup of every persisted artifact for this game.
        try:
            snapshots = list_pending_snapshots(gid)
        except Exception:
            snapshots = {}
        for ai_idx in snapshots:
            try:
                delete_runner_snapshot(gid, ai_idx)
            except Exception as exc:
                log.warn("delete_runner_snapshot_failed",
                         game_id=gid, ai_idx=ai_idx, error=str(exc))
        try:
            delete_game_record(gid)
        except Exception as exc:
            log.warn("delete_game_record_failed", game_id=gid, error=str(exc))
        log.info("game_deleted", game_id=gid)
        self._json_ok({"ok": True, "game_id": gid})

    # ── SSE ──

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        sub_q: queue.Queue = queue.Queue()
        with gamestate.lock:
            history = list(gamestate.event_history)
            gamestate.subscribers.add(sub_q)
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
            with gamestate.lock:
                gamestate.subscribers.discard(sub_q)
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


# ── server entry point ────────────────────────────────────────────────────────

class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def serve(port: int = 8000, web_dir: Path | None = None) -> None:
    # Allow callers to point the server at a different asset directory — e.g.
    # a git worktree — without restarting the whole process or touching state.
    # Reassign the module-level path globals before the server starts; they are
    # read fresh on every request so this takes effect immediately.
    if web_dir is not None:
        global _LOBBY_HTML, _SETUP_HTML, _HIRING_HTML, _JOB_HTML
        global _HEIST_HTML, _EPILOGUE_HTML, _CAMPAIGN_HTML
        global _SHELL_JS, _MOCKS_DIR, _TABS_DIR
        d = web_dir.resolve()
        _LOBBY_HTML    = d / "lobby.html"
        _SETUP_HTML    = d / "web" / "setup.html"
        _HIRING_HTML   = d / "hiring.html"
        _JOB_HTML      = d / "job.html"
        _HEIST_HTML    = d / "heist.html"
        _EPILOGUE_HTML = d / "epilogue.html"
        _CAMPAIGN_HTML = d / "campaign.html"
        _SHELL_JS      = d / "web" / "shell.js"
        _MOCKS_DIR     = d / "mocks"
        _TABS_DIR      = d / "web" / "tabs"
        print(f"Assets → {d}")

    games_recovered, ai_resuming = orchestration.recover_games()
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
