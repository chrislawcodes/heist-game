"""Convert game dataclasses to JSON-serializable dicts."""
from __future__ import annotations

from enum import IntEnum
from typing import Any

from heist.state import Character, Crew, HeistState, Job, Scene, SceneResult


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
        "personality": c.personality,
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
