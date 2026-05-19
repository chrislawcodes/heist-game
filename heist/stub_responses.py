"""Hardcoded AI responses for iteration 1: lets the whole loop run end-to-end
without any real model calls. Iteration 3 replaces this with the codex/gemini
backends from heist.agents (a thin wrapper around the existing agents.py)."""

from __future__ import annotations

import json
import re

from heist.ai import StubHeistAI

_JOB_BIDS: dict[str, list[tuple[int, int, str]]] = {
    "The Museum Gala": [
        (10, 700, "High safecracker."),
        (8, 200, "Inside Man M; half of the collaboration."),
        (9, 400, "Inside Man M + Muscle L; other half of collaboration."),
        (13, 700, "High driver for a clean exit."),
    ],
    "The Armored Car": [
        (4, 700, "High muscle for the guards."),
        (11, 400, "Safecracker M for the truck's locks."),
        (13, 700, "High driver for the getaway."),
        (15, 200, "Muscle L + Driver L support."),
    ],
    "The Corporate Server Farm": [
        (1, 1100, "High hacker plus backup driver in one body."),
        (8, 200, "Inside Man M for the social layer."),
        (11, 400, "Safecracker M for the server-room lock."),
        (15, 200, "Muscle L + Driver L support."),
    ],
    "The Penthouse Caper": [
        (2, 200, "Hacker M for the smart home."),
        (11, 400, "Safecracker M + Hacker L for the wall safe."),
        (8, 200, "Inside Man M for the lobby."),
        (13, 700, "High driver for the exit."),
    ],
    "The Cargo Yard": [
        (10, 700, "High safecracker for the container locks."),
        (5, 400, "Muscle M + Driver L for the watchmen."),
        (13, 700, "High driver."),
        (2, 200, "Hacker M support."),
    ],
    "The Diplomatic Reception": [
        (8, 200, "Inside Man M; half of the social collaboration."),
        (9, 400, "Inside Man M + Muscle L; other half."),
        (14, 400, "Driver M + Inside Man L."),
        (10, 700, "Safecracker H if we pursue the real Romanov."),
    ],
    "The Casino Vault": [
        (2, 200, "Hacker M; half of the electronic collaboration."),
        (12, 200, "Safecracker L + Hacker L; the other half of hacker collab."),
        (10, 700, "Safecracker H for the vault."),
        (8, 200, "Inside Man M for the floor."),
    ],
}


def _bid_response(job_name: str) -> str:
    bids = [
        {"character_id": cid, "bid": amt, "rationale": why}
        for (cid, amt, why) in _JOB_BIDS[job_name]
    ]
    return json.dumps({
        "casting_strategy": f"Crew built for {job_name}.",
        "bids": bids,
        "reasoning": f"Composition picked to cover every Hard challenge in {job_name}.",
    })


def _fill_response() -> str:
    return json.dumps({"additions": [], "reasoning": "Crew already full."})


def _job_response(job_name: str) -> str:
    return json.dumps({
        "job_name": job_name,
        "reasoning": f"This crew was assembled to take on {job_name}.",
    })


def _casting_summary_response(job_name: str) -> str:
    return json.dumps({
        "summary": (
            f"_(stub casting summary for {job_name} — replaced with real model output in iter 3)_"
        )
    })


def _assign_response(member_ids: list[int], reasoning: str) -> str:
    return json.dumps({
        "assigned_member_ids": member_ids,
        "reasoning": reasoning,
    })


def _decision_response(pursue: bool, reasoning: str) -> str:
    return json.dumps({"pursue": pursue, "reasoning": reasoning})


def _narrate_response(text: str) -> str:
    return json.dumps({"narration": text})


def _epilogue_response() -> str:
    return json.dumps({
        "epilogue": (
            "By morning the diamond is gone and the gala's footage shows only a "
            "well-dressed couple and their guests, leaving with the rest of the crowd. "
            "The crew splits the take three ways: the bid that bought them in, the "
            "boss's cut, and a clean envelope each. Rook lays low. Theo and Pearl "
            "drift back to their day jobs. Slim is already eyeing the next car."
        )
    })


class _GenericStub(StubHeistAI):
    """A stub that supplies generic responses based on prompt content,
    so we can iterate without hand-curating every turn."""

    def __init__(self, job_name: str = "The Museum Gala"):
        super().__init__(responses=[])
        self._job_name = job_name

    def ask(self, prompt: str):
        text = self._dispatch(prompt)
        self._asked.append(prompt)
        self._idx += 1
        from heist.ai import AgentTurn
        return AgentTurn(text=text, session_id="stub-session")

    def _dispatch(self, prompt: str) -> str:
        if "Draft your crew" in prompt:
            return _bid_response(self._job_name)
        if "fill in" in prompt or "Pick from the remaining roster" in prompt:
            return _fill_response()
        if "Pick the job this crew" in prompt:
            return _job_response(self._job_name)
        if "casting summary" in prompt:
            return _casting_summary_response(self._job_name)
        if "Decision point" in prompt:
            # Default: decline bonus (conservative).
            return _decision_response(False, "Risk outweighs the bonus given the player's prompt.")
        if "Assign one or more crew" in prompt:
            # Try to pick a sensible default: prefer the crew member with the requested skill.
            return self._auto_assign(prompt)
        if "Narrate scene" in prompt:
            return self._auto_narrate(prompt)
        if "epilogue" in prompt:
            return _epilogue_response()
        raise RuntimeError(f"Stub got unrecognized prompt:\n{prompt[:300]}")

    def _auto_assign(self, prompt: str) -> str:
        # Heuristic: pick the first crew member id mentioned in the prompt.
        ids = [int(m) for m in re.findall(r"id=(\d+)", prompt)]
        if not ids:
            return _assign_response([], "no crew context")
        # If a challenge is named, try to pick the right specialist.
        skill_match = re.search(r"Challenge: (\w+),", prompt)
        if skill_match:
            wanted = skill_match.group(1)
            # find crew lines mentioning this skill
            from heist.content import ROSTER_BY_ID
            matching = [i for i in ids if wanted in ROSTER_BY_ID[i].skills]
            if matching:
                return _assign_response(matching[:2], f"{wanted} specialists")
        return _assign_response([ids[0]], "first available")

    def _auto_narrate(self, prompt: str) -> str:
        # Extract scene info; produce a plausible 2-3 line narration.
        m = re.search(r"scene (\d+) \(([^)]+)\)", prompt)
        scene_no = m.group(1) if m else "?"
        title = m.group(2) if m else "scene"
        outcome = "succeeded" if "success" in prompt else "failed" if "failure" in prompt else "ran"
        return _narrate_response(
            f"_(stub narration: scene {scene_no} — {title}, {outcome})_"
        )


def build_stub_ai(job_name: str = "The Museum Gala") -> StubHeistAI:
    return _GenericStub(job_name=job_name)
