"""Hardcoded AI responses for iteration 1: lets the whole loop run end-to-end
without any real model calls. Iteration 3 replaces this with the codex/gemini
backends from heist.agents (a thin wrapper around the existing agents.py)."""

from __future__ import annotations

import json
import re

from heist.ai import StubHeistAI


def _bid_response() -> str:
    # Sensible balanced crew within $2000: Marcus + Vance is over budget;
    # this picks a credible Museum-leaning crew.
    return json.dumps({
        "casting_strategy": "Balanced crew with Inside Man coverage via collaboration.",
        "bids": [
            {"character_id": 10, "bid": 700, "priority": 1,
             "rationale": "High safecracker."},
            {"character_id": 8, "bid": 200, "priority": 2,
             "rationale": "Inside Man M; half of the collaboration."},
            {"character_id": 9, "bid": 400, "priority": 3,
             "rationale": "Inside Man M + Muscle L; other half of collaboration."},
            {"character_id": 13, "bid": 700, "priority": 4,
             "rationale": "High driver for a clean exit."},
        ],
        "reasoning": "Two Mediums in Inside Man stack to effective High via collaboration, "
                    "keeping us under budget and covering the Museum's twin Hard challenges."
    })


def _fill_response() -> str:
    return json.dumps({"additions": [], "reasoning": "Crew already full."})


def _job_response() -> str:
    return json.dumps({
        "job_name": "The Museum Gala",
        "reasoning": "We have High Safecracker (Rook) and collaboration-effective High Inside Man "
                    "(Theo + Pearl). This crew was built for the Museum."
    })


def _casting_summary_response() -> str:
    return json.dumps({
        "summary": (
            "**Crew:** Rook Ferreira (High Safecracker), Theo Ashland (Inside Man M), "
            "Pearl Sutton (Inside Man M + Muscle L), Slim Adesanya (High Driver). "
            "Total spend $2,000 — every dollar in play.\n\n"
            "**Logic:** The Museum needs Hard Safecracker AND Hard Inside Man. A solo "
            "High Inside Man (Lin) would cost $1,100, which makes the rest of the crew "
            "untenable. Using the collaboration rule, Theo + Pearl (both Medium) act as an "
            "effective High — same coverage, $700 cheaper. That buys us Rook for the vault "
            "and Slim for the exit.\n\n"
            "**Job:** The Museum Gala. Big purse, clean profile, and the puzzle the crew "
            "is built to solve."
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

    def ask(self, prompt: str):
        text = self._dispatch(prompt)
        self._asked.append(prompt)
        self._idx += 1
        from heist.ai import AgentTurn
        return AgentTurn(text=text, session_id="stub-session")

    def _dispatch(self, prompt: str) -> str:
        if "Draft your crew" in prompt:
            return _bid_response()
        if "fill in" in prompt or "Pick from the remaining roster" in prompt:
            return _fill_response()
        if "Pick the job this crew" in prompt:
            return _job_response()
        if "casting summary" in prompt:
            return _casting_summary_response()
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


def build_stub_ai() -> StubHeistAI:
    return _GenericStub(responses=[])
