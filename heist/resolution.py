"""Game-balance resolution helpers: bid validation, scene outcome resolution,
member capture, and reward finalization. Pure functions over mechanics + state."""

from __future__ import annotations

from heist.content import BANKROLL, ROSTER_BY_ID
from heist.mechanics import Outcome, effective_skill_score, resolve_by_margin
from heist.state import CHALLENGE_TO_SKILL, ChallengeLevel, Character, HeistState, Scene, SkillLevel

# Fallback challenge score when a scene wasn't stamped (legacy/ad-hoc scenes).
_LEVEL_SCORE = {ChallengeLevel.LOW: 2, ChallengeLevel.MEDIUM: 5, ChallengeLevel.HARD: 9}

_SKILL_TO_CATEGORY = {skill: category for category, skill in CHALLENGE_TO_SKILL.items()}


def _validate_bids(parsed: dict) -> list[tuple[Character, int]]:
    bids: list[tuple[Character, int]] = []
    seen: set[int] = set()
    total = 0
    for raw in parsed.get("bids", []):
        cid = int(raw["character_id"])
        if cid in seen:
            continue
        if cid not in ROSTER_BY_ID:
            raise ValueError(f"Unknown character id in bid: {cid}")
        char = ROSTER_BY_ID[cid]
        bid = int(raw["bid"])
        if bid < char.floor_cost:
            raise ValueError(f"Bid {bid} for {char.name} below floor {char.floor_cost}")
        bids.append((char, bid))
        seen.add(cid)
        total += bid
    if total > BANKROLL:
        raise ValueError(f"Total bids ${total} exceed bankroll ${BANKROLL}")
    return bids


def _resolve_challenge_scene(
    scene: Scene, assigned: list[Character]
) -> tuple[Outcome, str]:
    """Returns (outcome, outcome_summary). Score-based (Phase 4): the crew's
    effective 1-10 score vs the scene's true challenge score."""
    assert scene.challenge_skill is not None and scene.challenge_level is not None
    eff = effective_skill_score(assigned, scene.challenge_skill)
    challenge_score = scene.challenge_score
    if challenge_score is None:
        challenge_score = _LEVEL_SCORE.get(scene.challenge_level, 0)
    outcome = resolve_by_margin(eff, challenge_score)
    margin = eff - challenge_score
    return outcome, (
        f"Crew {scene.challenge_skill} score {eff} vs challenge {challenge_score} "
        f"(margin {margin:+d}, published {scene.challenge_level.name}). "
        f"Result: {outcome.name.lower()}."
    )


def _free_members(state: HeistState) -> list[Character]:
    return [m for m in state.crew.members if m.id not in state.caught_member_ids]


def _catch_member_from_assigned(scene: Scene, assigned: list[Character]) -> Character | None:
    if not assigned or scene.challenge_skill is None:
        return None
    skill_holders = [
        member
        for member in assigned
        if member.skills.get(scene.challenge_skill, SkillLevel.NONE) != SkillLevel.NONE
    ]
    if len(skill_holders) == 1:
        return skill_holders[0]
    return min(assigned, key=lambda member: (member.floor_cost, member.id))


def _scene_category(scene: Scene) -> str | None:
    if scene.category is not None:
        return scene.category
    if scene.challenge_skill is not None:
        return _SKILL_TO_CATEGORY.get(scene.challenge_skill)
    return None

def _finalize_reward(state: HeistState) -> None:
    free = [m for m in state.crew.members if m.id not in state.caught_member_ids]
    state.final_take = state.secured_take if free else 0
