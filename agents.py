import json
import subprocess
from dataclasses import dataclass


@dataclass
class Turn:
    text: str
    session_id: str


def ask_codex(prompt: str, session_id: str | None = None, timeout: int = 600, model: str | None = None) -> Turn:
    if session_id:
        cmd = ["codex", "exec", "resume", session_id,
               "--json", "--skip-git-repo-check", prompt]
    else:
        cmd = ["codex", "exec",
               "--json", "--sandbox", "read-only", "--skip-git-repo-check"]
        if model:
            cmd += ["-m", model]
        cmd += [prompt]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=timeout, check=True)
    events = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
    sid = session_id or next(
        e["thread_id"] for e in events if e.get("type") == "thread.started"
    )
    text = next(
        e["item"]["text"] for e in events
        if e.get("type") == "item.completed"
        and e.get("item", {}).get("type") == "agent_message"
    )
    return Turn(text=text, session_id=sid)


def ask_gemini(prompt: str, session_id: str | None = None, timeout: int = 600) -> Turn:
    cmd = ["gemini", "-o", "json"]
    if session_id:
        cmd += ["--resume", session_id]
    cmd += ["-p", prompt]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=timeout, check=True)
    # stdout may be prefixed with non-JSON warnings; find the start of the object
    start = r.stdout.find("{")
    data = json.loads(r.stdout[start:])
    return Turn(text=data["response"], session_id=data["session_id"])
