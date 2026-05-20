"""Convert game dataclasses to JSON-serializable dicts.

Each ``*_to_dict`` has a matching ``*_from_dict`` so a serialized state can
be reconstructed byte-for-byte after a server restart (see ``heist.persist``).
The dict shape is the contract; if you add a field to a dataclass, update
both directions in the same change.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any

from heist.content import JOBS_BY_NAME, ROSTER_BY_ID
from heist.state import (
    ChallengeLevel,
    Character,
    Crew,
    HeistState,
    HiddenDepthElement,
    HiddenDepthRoll,
    Job,
    Scene,
    SceneResult,
    SkillLevel,
)


def _deep(obj: Any) -> Any:
    if isinstance(obj, IntEnum):
        return obj.name
    if isinstance(obj, dict):
        return {k: _deep(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep(v) for v in obj]
    return obj


def character_to_dict(c: Character) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "skills": {k: v.name for k, v in c.skills.items()},
        "floor_cost": c.floor_cost,
        "backstory": c.backstory,
        "voice": c.voice,
        "motivation": c.motivation,
        "quirk": c.quirk,
        "crew_dynamic": c.crew_dynamic,
        "weakness": c.weakness,
        "look": c.look,
        "signature_line": c.signature_line,
        "skill_scores": dict(c.skill_scores),
    }


def crew_to_dict(crew: Crew) -> dict:
    return {
        "members": [character_to_dict(m) for m in crew.members],
        "total_cost": crew.total_cost,
    }


def job_to_dict(job: Job) -> dict:
    return {
        "name": job.name,
        "flavor": job.flavor,
        "reward_range": list(job.reward_range),
        "profile": {k: v.name for k, v in job.profile.items()},
        "escape_modifier": job.escape_modifier,
        "challenge_scores": dict(job.challenge_scores),
    }


def scene_to_dict(s: Scene) -> dict:
    return {
        "number": s.number,
        "type": s.type,
        "title": s.title,
        "challenge_skill": s.challenge_skill,
        "challenge_level": s.challenge_level.name if s.challenge_level else None,
        "is_core": s.is_core,
        "context": s.context,
    }


def scene_result_to_dict(r: SceneResult) -> dict:
    return {
        "scene": scene_to_dict(r.scene),
        "assigned_member_ids": r.assigned_member_ids,
        "success": r.success,
        "narration": r.narration,
        "reasoning": r.reasoning,
        "decision": r.decision,
    }


# ── inverse helpers (dict → dataclass) ──────────────────────────────────────
# Looking up characters and jobs by id/name from the static content tables
# rather than re-hydrating them keeps Character/Job objects identity-equal to
# the ones the runner uses elsewhere (and avoids drift when content evolves).


def character_from_dict(d: dict) -> Character:
    """Look up the canonical Character by id. Falls back to building one from
    the dict if the id has been removed from the roster — useful for replaying
    an old game whose roster has since changed."""
    cid = int(d["id"])
    if cid in ROSTER_BY_ID:
        return ROSTER_BY_ID[cid]
    return Character(
        id=cid,
        name=d["name"],
        skills={k: SkillLevel[v] for k, v in d["skills"].items()},
        floor_cost=int(d["floor_cost"]),
        backstory=d.get("backstory", ""),
        voice=d.get("voice", ""),
        motivation=d.get("motivation", ""),
        quirk=d.get("quirk", ""),
        crew_dynamic=d.get("crew_dynamic", ""),
        weakness=d.get("weakness", ""),
        look=d.get("look", ""),
        signature_line=d.get("signature_line", ""),
        skill_scores={k: int(v) for k, v in d.get("skill_scores", {}).items()},
    )


def crew_from_dict(d: dict) -> Crew:
    return Crew(members=[character_from_dict(m) for m in d["members"]])


def job_from_dict(d: dict) -> Job:
    name = d["name"]
    if name in JOBS_BY_NAME:
        return JOBS_BY_NAME[name]
    # Fallback for replays of jobs no longer in content.py — we lose
    # hidden_depth and reward_amounts, but the rest is enough to display.
    return Job(
        name=name,
        flavor=d.get("flavor", ""),
        reward_range=tuple(d.get("reward_range", [0, 0])),
        profile={k: ChallengeLevel[v] for k, v in d["profile"].items()},
        escape_modifier=int(d.get("escape_modifier", 0)),
        hidden_depth=[],
        reward_amounts=[],
        challenge_scores={k: int(v) for k, v in d.get("challenge_scores", {}).items()},
    )


def scene_from_dict(d: dict) -> Scene:
    raw_level = d.get("challenge_level")
    level = ChallengeLevel[raw_level] if raw_level else None
    return Scene(
        number=int(d["number"]),
        type=d["type"],
        title=d["title"],
        challenge_skill=d.get("challenge_skill"),
        challenge_level=level,
        is_core=bool(d.get("is_core", False)),
        context=d.get("context", ""),
    )


def scene_result_from_dict(d: dict) -> SceneResult:
    return SceneResult(
        scene=scene_from_dict(d["scene"]),
        assigned_member_ids=[int(i) for i in d.get("assigned_member_ids", [])],
        success=d.get("success"),
        narration=d.get("narration", ""),
        reasoning=d.get("reasoning", ""),
        decision=d.get("decision"),
    )


def hidden_depth_from_dict(d: dict, job: Job) -> HiddenDepthRoll:
    el_d = d["element"]
    el_id = el_d["id"]
    # Prefer the canonical element (carries the full ``effect`` dict that the
    # runner needs for bonus amounts and modifications).
    canonical = next((e for e in job.hidden_depth if e.id == el_id), None)
    element = canonical or HiddenDepthElement(
        id=el_id,
        description=el_d.get("description", ""),
        type=el_d.get("type", ""),
        effect={},
    )
    return HiddenDepthRoll(
        element=element,
        reward_label=d.get("reward_label", ""),
        reward_amount=int(d.get("reward_amount", 0)),
    )


def state_from_dict(d: dict) -> HeistState:
    job = job_from_dict(d["job"])
    crew = crew_from_dict(d["crew"])
    hidden = hidden_depth_from_dict(d["hidden_depth"], job)
    state = HeistState(
        crew=crew,
        job=job,
        hidden_depth=hidden,
        scene_results=[scene_result_from_dict(r) for r in d.get("scene_results", [])],
        heat=int(d.get("heat", 0)),
        aborted=bool(d.get("aborted", False)),
        bonus_pursued=bool(d.get("bonus_pursued", False)),
        bonus_succeeded=bool(d.get("bonus_succeeded", False)),
        bonus_amount=int(d.get("bonus_amount", 0)),
        escape_success=d.get("escape_success"),
        escape_difficulty=d.get("escape_difficulty"),
        final_take=int(d.get("final_take", 0)),
    )
    return state


def state_to_dict(state: HeistState) -> dict:
    return {
        "crew": crew_to_dict(state.crew),
        "job": job_to_dict(state.job),
        "heat": state.heat,
        "aborted": state.aborted,
        "bonus_pursued": state.bonus_pursued,
        "bonus_succeeded": state.bonus_succeeded,
        "bonus_amount": state.bonus_amount,
        "escape_success": state.escape_success,
        "escape_difficulty": state.escape_difficulty,
        "final_take": state.final_take,
        "scene_results": [scene_result_to_dict(r) for r in state.scene_results],
        "hidden_depth": {
            "element": {
                "id": state.hidden_depth.element.id,
                "description": state.hidden_depth.element.description,
                "type": state.hidden_depth.element.type,
            },
            "reward_label": state.hidden_depth.reward_label,
            "reward_amount": state.hidden_depth.reward_amount,
        },
    }
