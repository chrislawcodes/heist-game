"""Local browser UI for the heist game.

Run:  python -m heist.server
Open: http://127.0.0.1:8000

This is a single-user, localhost-only server. No auth, no tunnels.
The FastAPI handler wraps `run_heist()` in a worker thread and streams
each scene to the browser as NDJSON (one JSON object per line) so the
page can render scenes as they arrive instead of waiting for the heist
to finish.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from heist.ai import HeistAI
from heist.content import DEFAULT_PROMPT, ROSTER_BY_ID
from heist.runner import run_heist
from heist.state import HeistState, SceneResult

WEB_DIR = Path(__file__).parent / "web"


class HeistRequest(BaseModel):
    prompt: str
    agent: str = "codex"
    seed: int | None = None


def _build_ai(agent: str) -> HeistAI:
    if agent == "stub":
        from heist.stub_responses import build_stub_ai
        return build_stub_ai()
    if agent == "codex":
        from heist.backends import CodexHeistAI
        return CodexHeistAI()
    if agent == "gemini":
        from heist.backends import GeminiHeistAI
        return GeminiHeistAI()
    raise ValueError(f"unknown agent: {agent}")


def _scene_event(result: SceneResult) -> dict[str, Any]:
    personnel = [ROSTER_BY_ID[i].name for i in result.assigned_member_ids if i in ROSTER_BY_ID]
    return {
        "type": "scene",
        "number": result.scene.number,
        "scene_type": result.scene.type,
        "title": result.scene.title,
        "personnel": personnel,
        "reasoning": result.reasoning,
        "narration": result.narration,
        "success": result.success,
        "decision": result.decision,
    }


def _final_event(state: HeistState, extras: dict) -> dict[str, Any]:
    return {
        "type": "done",
        "casting_summary": extras.get("casting_summary", ""),
        "epilogue": extras.get("epilogue", ""),
        "outcome": {
            "job_name": state.job.name,
            "take": state.final_take,
            "aborted": state.aborted,
            "escape_success": state.escape_success,
            "hidden_depth": state.hidden_depth.element.description,
            "reward_label": state.hidden_depth.reward_label,
            "reward_amount": state.hidden_depth.reward_amount,
        },
        "timing": {
            "rounds": [
                {"label": t.label, "seconds": round(t.seconds, 1)}
                for t in extras.get("turn_logs", [])
            ],
            "total_seconds": round(extras.get("total_seconds", 0), 1),
        },
    }


async def _heist_stream(req: HeistRequest) -> AsyncIterator[bytes]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(q.put_nowait, event)

    def on_scene(result: SceneResult) -> None:
        emit(_scene_event(result))

    def worker() -> None:
        try:
            ai = _build_ai(req.agent)
            rng = random.Random(req.seed)
            state, extras = run_heist(req.prompt, ai, rng=rng, on_scene=on_scene)
            emit(_final_event(state, extras))
        except Exception as e:
            emit({"type": "error", "message": f"{type(e).__name__}: {e}"})

    threading.Thread(target=worker, daemon=True).start()

    emit({"type": "started", "agent": req.agent, "prompt": req.prompt})

    while True:
        event = await q.get()
        yield (json.dumps(event) + "\n").encode("utf-8")
        if event["type"] in ("done", "error"):
            return


def build_app() -> FastAPI:
    app = FastAPI(title="heist-game")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (WEB_DIR / "index.html").read_text()

    @app.get("/api/default-prompt")
    async def default_prompt() -> dict[str, str]:
        return {"prompt": DEFAULT_PROMPT}

    @app.post("/api/heist")
    async def heist_endpoint(req: HeistRequest) -> StreamingResponse:
        return StreamingResponse(
            _heist_stream(req),
            media_type="application/x-ndjson",
        )

    return app


app = build_app()


def main() -> None:
    import uvicorn
    print("Heist game serving at http://127.0.0.1:8000", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
