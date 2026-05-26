"""Hardcoded AI responses for iteration 1: lets the whole loop run end-to-end
without any real model calls. Iteration 3 replaces this with the codex/gemini
backends from heist.agents (a thin wrapper around the existing agents.py)."""

from __future__ import annotations

import json
import re

from heist.ai import StubHeistAI

_JOB_BIDS: dict[str, list[tuple[int, int, str]]] = {
    "The Museum Gala": [
        (10, 700_000, "High safecracker."),
        (8, 200_000, "Inside Man M; half of the collaboration."),
        (9, 400_000, "Inside Man M + Muscle L; other half of collaboration."),
        (13, 700_000, "High driver for a clean exit."),
    ],
    "The Armored Car": [
        (4, 700_000, "High muscle for the guards."),
        (5, 400_000, "Muscle M + Driver L backup."),
        (13, 700_000, "High driver for the getaway."),
        (2, 200_000, "Hacker M for any electronic interference."),
    ],
    "The Corporate Server Farm": [
        (1, 1_100_000, "High hacker plus backup driver in one body."),
        (8, 200_000, "Inside Man M for the social layer."),
        (11, 400_000, "Safecracker M for the server-room lock."),
        (3, 200_000, "Hacker L + Inside Man L — cheap third pair of eyes."),
    ],
    "The Penthouse Caper": [
        (2, 200_000, "Hacker M for the smart home."),
        (11, 400_000, "Safecracker M + Hacker L for the wall safe."),
        (8, 200_000, "Inside Man M for the lobby."),
        (13, 700_000, "High driver for the exit."),
    ],
    "The Cargo Yard": [
        (10, 700_000, "High safecracker for the container locks."),
        (5, 400_000, "Muscle M + Driver L for the watchmen."),
        (13, 700_000, "High driver."),
        (2, 200_000, "Hacker M support."),
    ],
    "The Diplomatic Reception": [
        (8, 200_000, "Inside Man M; half of the social collaboration."),
        (9, 400_000, "Inside Man M + Muscle L; other half."),
        (14, 400_000, "Driver M + Inside Man L."),
        (10, 700_000, "Safecracker H if we pursue the real Romanov."),
    ],
    "The Casino Vault": [
        (2, 200_000, "Hacker M; half of the electronic collaboration."),
        (12, 400_000, "Safecracker M + Hacker L; the other half of hacker collab."),
        (10, 700_000, "Safecracker H for the vault."),
        (8, 200_000, "Inside Man M for the floor."),
    ],
}


def _bid_response(job_name: str) -> str:
    # Bid each pick's true floor cost (the hardcoded amounts in _JOB_BIDS are
    # legacy hints; pricing is owned by the curve in mechanics.score_floor_cost).
    from heist.content import ROSTER_BY_ID
    bids = [
        {"character_id": cid, "bid": ROSTER_BY_ID[cid].floor_cost, "rationale": why}
        for (cid, _amt, why) in _JOB_BIDS[job_name]
    ]
    return json.dumps({
        "casting_strategy": f"Crew built for {job_name}.",
        "bids": bids,
        "reasoning": f"Composition picked to cover every Hard challenge in {job_name}.",
    })


def _fill_response() -> str:
    return json.dumps({"additions": [], "reasoning": "Crew already full."})


def _round_bid_response(prompt: str) -> str:
    """Stub bidder for the round-based auction (heist.auction._round_bid_prompt).

    Parses the prompt for remaining slots, bankroll, and the available pool,
    then bids on the cheapest characters that fit the budget. A small
    per-strategy offset is added to the bid amount so two stub AIs don't tie
    on the same cheapest picks every round (which would never resolve)."""
    have_match = re.search(r"crew so far \((\d+)/4\)", prompt)
    have = int(have_match.group(1)) if have_match else 0
    need = max(0, 4 - have)
    bank_match = re.search(r"Your bankroll: \$(\d+)", prompt)
    bankroll = int(bank_match.group(1)) if bank_match else 0
    strat_match = re.search(r"Player's strategy:\n---\n(.*?)\n---", prompt, re.DOTALL)
    strategy = strat_match.group(1) if strat_match else ""
    # Deterministic per-AI bid offset so two stubs don't bid identically and
    # tie every round (which would never resolve, hitting the round cap with
    # empty crews). A position-weighted char sum mod a prime makes distinct
    # strategy strings essentially never collide; the higher-offset AI wins
    # contested picks and the other takes the next round's leftovers. Capped
    # small (0-136) so four picks stay within bankroll.
    offset = sum((i + 1) * ord(ch) for i, ch in enumerate(strategy)) % 137
    avail = [
        (int(cid), int(floor))
        for cid, floor in re.findall(r"id=(\d+),.*?floor=\$(\d+)", prompt)
    ]
    avail.sort(key=lambda x: (x[1], x[0]))
    bids: list[dict] = []
    spent = 0
    for cid, floor in avail:
        if len(bids) >= need:
            break
        amount = floor + offset
        if spent + amount > bankroll:
            continue
        bids.append({
            "character_id": cid,
            "bid": amount,
            "rationale": "Cheapest affordable pick to fill the crew.",
        })
        spent += amount
    if not bids:
        return json.dumps({
            "bids": [],
            "pass": True,
            "reasoning": "Nothing affordable left; standing pat.",
        })
    return json.dumps({
        "bids": bids,
        "pass": False,
        "reasoning": "Filling the crew with the best-value picks available.",
    })


def _job_response(job_name: str) -> str:
    return json.dumps({
        "job_name": job_name,
        "reasoning": f"This crew was assembled to take on {job_name}.",
    })


def _casting_summary_response(job_name: str) -> str:
    return f"_(stub casting summary for {job_name} — replaced with real model output in iter 3)_"


def _assign_response(member_ids: list[int], reasoning: str) -> str:
    return json.dumps({
        "assigned_member_ids": member_ids,
        "reasoning": reasoning,
    })


def _decision_response(pursue: bool, reasoning: str) -> str:
    return json.dumps({"pursue": pursue, "reasoning": reasoning})


def _narrate_response(text: str) -> str:
    return text


def _epilogue_response() -> str:
    return (
        "By morning the diamond is gone and the gala's footage shows only a "
        "well-dressed couple and their guests, leaving with the rest of the crowd. "
        "The crew splits the take three ways: the bid that bought them in, the "
        "boss's cut, and a clean envelope each. Rook lays low. Theo and Pearl "
        "drift back to their day jobs. Slim is already eyeing the next car."
    )


def _abort_response(abort: bool, reasoning: str) -> str:
    return json.dumps({"abort": abort, "reasoning": reasoning})


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
        if "of crew bidding" in prompt:
            return _round_bid_response(prompt)
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
        if "Do you abort now" in prompt:
            # Default: push on (lets tests run all scenes).
            return _abort_response(False, "Pushing on — the job isn't lost yet.")
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
