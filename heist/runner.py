"""Orchestrate a single Phase 1 heist end-to-end.

Flow (matches design doc "high-level flow"):
    1. Ask AI for bids → validate & assemble crew (fill gaps if needed).
    2. Ask AI for job selection → validate viability.
    3. Ask AI for casting summary.
    4. Roll hidden depth.
    5. Generate scene list.
    6. For each scene: assignment → mechanical resolution → narration.
    7. Resolve escape; narrate.
    8. Compute reward; ask AI for epilogue.

The AI talks in JSON for structured steps; the runner parses defensively.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from heist.ai import HeistAI, parse_json_block
from heist.content import BANKROLL, JOBS, JOBS_BY_NAME, ROSTER, ROSTER_BY_ID
from heist.mechanics import (
    effective_skill,
    escape_resolves,
    job_is_viable,
    resolves_challenge,
)
from heist.state import (
    Character,
    Crew,
    HeistState,
    HiddenDepthRoll,
    Scene,
    SceneResult,
    SkillLevel,
)

SceneCallback = Callable[[SceneResult], None]


def _roster_summary() -> str:
    lines = []
    for c in ROSTER:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        lines.append(f"  - id={c.id}, name={c.name!r}, skills=({skills}), floor=${c.floor_cost}")
    return "\n".join(lines)


def _job_slate_summary() -> str:
    lines = []
    for j in JOBS:
        prof = " | ".join(f"{k} {v.name}" for k, v in j.profile.items())
        lines.append(
            f"  - {j.name!r}: reward ${j.reward_range[0]:,}-${j.reward_range[1]:,}, "
            f"profile [{prof}]"
        )
    return "\n".join(lines)


def _bid_prompt(strategy: str) -> str:
    return (
        "You are the Heist AI. You will play every creative role for a single heist: "
        "drafting the crew, picking the job, assigning crew to scenes, deciding at "
        "decision points, and narrating each scene in character. Stay in this role.\n\n"
        f"Player's strategy prompt:\n---\n{strategy}\n---\n\n"
        f"Bankroll: ${BANKROLL}. Roster (15 characters):\n{_roster_summary()}\n\n"
        "Draft your crew. Reply with ONLY a JSON object (no prose around it) of shape:\n"
        '{\n'
        '  "casting_strategy": "one-sentence strategy in your own words",\n'
        '  "bids": [\n'
        '    {"character_id": <int>, "bid": <int>=floor, "priority": <int 1=highest>, '
        '"rationale": "<why>"}\n'
        '  ],\n'
        '  "reasoning": "<why this overall composition fits the prompt>"\n'
        "}\n"
        "Bids must be ≥ each character's floor cost. Total bids ≤ $2000. "
        "Aim for 4 crew slots. If you can't quite hit 4 within budget, leave room — "
        "I'll ask you to fill in."
    )


def _fill_prompt(crew_so_far: list[Character], remaining: int) -> str:
    have = ", ".join(f"{c.name} (${c.floor_cost})" for c in crew_so_far)
    spent = sum(c.floor_cost for c in crew_so_far)
    return (
        f"Your bids hired {len(crew_so_far)}/4: [{have}]. "
        f"Spent ${spent}, ${BANKROLL - spent} left, need {remaining} more slots.\n"
        "Pick from the remaining roster (those not already hired) such that total "
        f"spend ≤ $2000. Reply with ONLY JSON:\n"
        '{"additions": [<character_id>, ...], "reasoning": "<why>"}'
    )


def _job_prompt(crew: Crew) -> str:
    crew_lines = []
    for c in crew.members:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        crew_lines.append(f"  - {c.name}: {skills}")
    return (
        f"Crew assembled (spent ${crew.total_cost}/{BANKROLL}):\n"
        + "\n".join(crew_lines)
        + f"\n\nJob slate:\n{_job_slate_summary()}\n\n"
        "Pick the job this crew should attempt. Reply with ONLY JSON:\n"
        '{"job_name": "<exact name>", "reasoning": "<why this job, given the crew and prompt>"}'
    )


def _summary_prompt() -> str:
    return (
        "Now write the casting summary (a transparent paragraph or two for the player) "
        "explaining the bid logic, who you hired, and which job you picked. Be honest "
        "about the trade-offs you made. Reply with ONLY JSON:\n"
        '{"summary": "<2-4 paragraphs in markdown, no leading heading>"}'
    )


def _scene_assign_prompt(scene: Scene, state: HeistState) -> str:
    crew_lines = []
    for c in state.crew.members:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        crew_lines.append(f"  id={c.id}: {c.name} ({skills})")
    challenge_desc = ""
    if scene.challenge_skill is not None and scene.challenge_level is not None:
        challenge_desc = (
            f"  Challenge: {scene.challenge_skill}, level {scene.challenge_level.name}\n"
        )
    return (
        f"Scene {scene.number} of the heist — {scene.title}.\n"
        f"  Type: {scene.type}\n"
        + challenge_desc
        + (f"  Context: {scene.context}\n" if scene.context else "")
        + "\nCrew on this job:\n" + "\n".join(crew_lines)
        + "\n\nAssign one or more crew members to handle this scene. "
        "Reply with ONLY JSON:\n"
        '{"assigned_member_ids": [<int>, ...], "reasoning": "<why these people>"}'
    )


def _scene_decision_prompt(scene: Scene) -> str:
    return (
        f"Decision point in scene {scene.number}: {scene.context}\n"
        "Decide whether to pursue. Reply with ONLY JSON:\n"
        '{"pursue": <true|false>, "reasoning": "<why, with reference to the player\'s prompt>"}'
    )


def _scene_narrate_prompt(scene: Scene, outcome_summary: str) -> str:
    return (
        f"Narrate scene {scene.number} ({scene.title}) in 200-400 words. Use the "
        "characters' voices. The mechanical outcome:\n"
        f"  {outcome_summary}\n\n"
        "Reply with ONLY JSON:\n"
        '{"narration": "<the prose, in markdown, no heading>"}'
    )


def _epilogue_prompt(state: HeistState) -> str:
    return (
        f"The heist is done. Final state:\n"
        f"  - Aborted: {state.aborted}\n"
        f"  - Escape: {state.escape_success}\n"
        f"  - Take: ${state.final_take:,}\n"
        f"  - Failed scenes: "
        f"{[r.scene.title for r in state.scene_results if r.success is False]}\n\n"
        "Write a short epilogue (100-200 words). Reply with ONLY JSON:\n"
        '{"epilogue": "<the prose, in markdown, no heading>"}'
    )


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


def _fill_crew(
    ai: HeistAI, crew_so_far: list[Character]
) -> list[Character]:
    while len(crew_so_far) < 4:
        remaining = 4 - len(crew_so_far)
        prompt = _fill_prompt(crew_so_far, remaining)
        turn = ai.ask(prompt)
        parsed = parse_json_block(turn.text)
        added_any = False
        spent = sum(c.floor_cost for c in crew_so_far)
        existing_ids = {c.id for c in crew_so_far}
        for cid in parsed.get("additions", []):
            cid = int(cid)
            if cid in existing_ids or cid not in ROSTER_BY_ID:
                continue
            char = ROSTER_BY_ID[cid]
            if spent + char.floor_cost > BANKROLL:
                continue
            crew_so_far.append(char)
            existing_ids.add(cid)
            spent += char.floor_cost
            added_any = True
            if len(crew_so_far) >= 4:
                break
        if not added_any:
            # AI couldn't / wouldn't help — bail with whatever we have
            break
    return crew_so_far


def _resolve_challenge_scene(
    scene: Scene, assigned: list[Character]
) -> tuple[bool, str]:
    """Returns (success, outcome_summary)."""
    assert scene.challenge_skill is not None and scene.challenge_level is not None
    skill = effective_skill(assigned, scene.challenge_skill)
    success = resolves_challenge(skill, scene.challenge_level)
    label = "success" if success else "failure"
    return success, (
        f"Crew skill in {scene.challenge_skill}: {skill.name}; "
        f"challenge level: {scene.challenge_level.name}. Result: {label}."
    )


def _apply_failure_cascade(state: HeistState, scene: Scene) -> None:
    if scene.is_core:
        state.aborted = True
    else:
        state.heat += 1


def run_heist(
    strategy: str,
    ai: HeistAI,
    rng: random.Random | None = None,
    on_scene: SceneCallback | None = None,
) -> tuple[HeistState, dict[str, Any]]:
    """Run one full heist end-to-end. Returns (final_state, extras)
    where extras carries the casting summary, scene narrations, and epilogue."""
    rng = rng or random.Random()
    extras: dict[str, Any] = {
        "strategy": strategy,
        "bid_logic": None,
        "casting_summary": "",
        "scene_narrations": [],  # filled per scene
        "epilogue": "",
    }

    # 1. Draft
    bid_turn = ai.ask(_bid_prompt(strategy))
    bid_parsed = parse_json_block(bid_turn.text)
    extras["bid_logic"] = bid_parsed
    bids = _validate_bids(bid_parsed)
    crew_members = [c for c, _ in bids]
    crew_members = _fill_crew(ai, crew_members)
    crew = Crew(members=crew_members)

    # 2. Job selection
    job_turn = ai.ask(_job_prompt(crew))
    job_parsed = parse_json_block(job_turn.text)
    name = job_parsed["job_name"]
    if name not in JOBS_BY_NAME:
        raise ValueError(f"AI picked unknown job {name!r}")
    job = JOBS_BY_NAME[name]
    if not job_is_viable(crew, job.profile):
        # Don't fail outright — the design wants this to be visible.
        # We still attempt the job; core failures will surface in the loop.
        extras["job_viability_warning"] = (
            f"Crew lacks required Hard coverage for {job.name}; proceeding anyway."
        )

    # 3. Casting summary
    summary_turn = ai.ask(_summary_prompt())
    extras["casting_summary"] = parse_json_block(summary_turn.text).get("summary", "")

    # 4. Hidden depth roll
    from heist.scenes import generate_scenes
    element = rng.choice(job.hidden_depth)
    reward_label, reward_amount = rng.choice(job.reward_amounts)
    hidden = HiddenDepthRoll(
        element=element, reward_label=reward_label, reward_amount=reward_amount
    )

    state = HeistState(crew=crew, job=job, hidden_depth=hidden)
    scenes = generate_scenes(job, hidden)

    # 5. Scene loop
    for scene in scenes:
        if state.aborted and scene.type != "escape":
            # Skip remaining body scenes once aborted; still narrate the escape (failed).
            continue
        result = _execute_scene(scene, state, ai)
        state.scene_results.append(result)
        extras["scene_narrations"].append(result)
        if on_scene is not None:
            on_scene(result)

    # 6. Escape resolution (already handled inside loop) → compute reward
    _finalize_reward(state)

    # 7. Epilogue
    ep_turn = ai.ask(_epilogue_prompt(state))
    extras["epilogue"] = parse_json_block(ep_turn.text).get("epilogue", "")

    return state, extras


def _execute_scene(scene: Scene, state: HeistState, ai: HeistAI) -> SceneResult:
    if scene.type == "escape":
        return _execute_escape(scene, state, ai)

    assign_turn = ai.ask(_scene_assign_prompt(scene, state))
    assign_parsed = parse_json_block(assign_turn.text)
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    assigned = [ROSTER_BY_ID[i] for i in member_ids if i in ROSTER_BY_ID]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    decision: dict | None = None
    success: bool | None = None
    outcome_summary: str

    if scene.type == "decision":
        dec_turn = ai.ask(_scene_decision_prompt(scene))
        dec_parsed = parse_json_block(dec_turn.text)
        pursue = bool(dec_parsed.get("pursue", False))
        decision = {"pursue": pursue, "reasoning": dec_parsed.get("reasoning", "")}
        state.bonus_pursued = pursue
        if pursue:
            success, outcome_summary = _resolve_challenge_scene(scene, assigned)
            state.bonus_succeeded = success
            if success:
                # Sample bonus amount: midpoint of range
                el = state.hidden_depth.element
                lo, hi = el.effect["bonus_amount_range"]
                state.bonus_amount = (lo + hi) // 2
            elif not success:
                _apply_failure_cascade(state, scene)
        else:
            outcome_summary = "Crew declined the bonus opportunity."
    elif scene.type in ("challenge", "hidden_depth"):
        success, outcome_summary = _resolve_challenge_scene(scene, assigned)
        if not success:
            _apply_failure_cascade(state, scene)
    elif scene.type in ("setup", "transition"):
        outcome_summary = f"{scene.title}: no mechanical resolution."
    else:
        outcome_summary = "(no resolution)"

    narrate_turn = ai.ask(_scene_narrate_prompt(scene, outcome_summary))
    narrate_parsed = parse_json_block(narrate_turn.text)
    narration = narrate_parsed.get("narration", "")

    return SceneResult(
        scene=scene,
        assigned_member_ids=member_ids,
        success=success,
        narration=narration,
        reasoning=assignment_reasoning,
        decision=decision,
    )


def _execute_escape(scene: Scene, state: HeistState, ai: HeistAI) -> SceneResult:
    success, difficulty = escape_resolves(
        state.crew, state.heat, state.job.escape_modifier
    )
    state.escape_success = success
    state.escape_difficulty = difficulty
    driver_skill = effective_skill(state.crew.members, "driver")
    if driver_skill == SkillLevel.NONE:
        driver_skill = SkillLevel.LOW
    outcome_summary = (
        f"Escape difficulty {difficulty} (escape mod {state.job.escape_modifier} "
        f"+ heat {state.heat}); best Driver skill {driver_skill.name}. "
        f"Result: {'success' if success else 'failure'}."
    )

    # Ask AI to assign — for escape, usually the Driver(s). Still let the AI pick.
    assign_turn = ai.ask(_scene_assign_prompt(scene, state))
    assign_parsed = parse_json_block(assign_turn.text)
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    narrate_turn = ai.ask(_scene_narrate_prompt(scene, outcome_summary))
    narration = parse_json_block(narrate_turn.text).get("narration", "")

    return SceneResult(
        scene=scene,
        assigned_member_ids=member_ids,
        success=success,
        narration=narration,
        reasoning=assignment_reasoning,
        decision=None,
    )


def _finalize_reward(state: HeistState) -> None:
    if state.aborted or state.escape_success is False:
        state.final_take = 0
        return
    state.final_take = state.hidden_depth.reward_amount + (
        state.bonus_amount if state.bonus_succeeded else 0
    )
