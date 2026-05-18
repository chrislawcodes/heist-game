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

import contextlib
import os
import random
import sys
import time
import traceback
from collections.abc import Callable
from typing import Any

from heist.ai import AgentTurn, HeistAI, parse_json_block
from heist.content import BANKROLL, JOBS, JOBS_BY_NAME, ROSTER, ROSTER_BY_ID
from heist.logs import log
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
    TurnLog,
)

EmitFn = Callable[[dict], None] | None
SceneCallback = Callable[[SceneResult], None]
SnapshotFn = Callable[[dict], None] | None

# Stage labels for snapshotting. Resume jumps to the stage *after* the one
# whose snapshot was last persisted.
STAGE_DRAFTING            = "drafting"
STAGE_JOB_PICKED          = "job_picked"
STAGE_CASTING_SUMMARY_DONE = "casting_summary_done"
STAGE_IN_SCENE            = "in_scene"
STAGE_EPILOGUE            = "epilogue"
STAGE_DONE                = "done"

# Min seconds between back-to-back AI turns when streaming to a viewer, so the
# player can absorb each beat. Only applies when `emit` is set (i.e. server
# mode); CLI mode is unaffected. Override with HEIST_TURN_DELAY=<seconds>.
TURN_DELAY_SECONDS = float(os.environ.get("HEIST_TURN_DELAY", "10"))
_last_turn_end_at: float | None = None


def _call(
    ai: HeistAI, prompt: str, label: str, logs: list[TurnLog], emit: EmitFn = None
) -> AgentTurn:
    """Time one AI call, log it, echo to stderr, and optionally emit turn events."""
    global _last_turn_end_at
    if emit and TURN_DELAY_SECONDS > 0 and _last_turn_end_at is not None:
        remaining = TURN_DELAY_SECONDS - (time.monotonic() - _last_turn_end_at)
        if remaining > 0:
            time.sleep(remaining)
    if emit:
        emit({"type": "turn_start", "label": label, "prompt": prompt})
    t0 = time.monotonic()
    try:
        turn = ai.ask(prompt)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        log.error(
            "ai_call_error",
            label=label,
            elapsed_ms=int(elapsed * 1000),
            prompt_len=len(prompt),
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        raise
    elapsed = time.monotonic() - t0
    logs.append(TurnLog(label=label, seconds=elapsed))
    print(f"  [round {label}: {elapsed:.1f}s]", file=sys.stderr)
    parsed = None
    with contextlib.suppress(Exception):
        parsed = parse_json_block(turn.text)
    log.info(
        "ai_call",
        label=label,
        elapsed_ms=int(elapsed * 1000),
        prompt_len=len(prompt),
        response_len=len(turn.text),
        parsed_ok=parsed is not None,
    )
    if emit:
        emit({"type": "turn_end", "label": label, "seconds": elapsed,
              "response": turn.text, "parsed": parsed})
        _last_turn_end_at = time.monotonic()
    return turn


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


_TRADECRAFT = """\
What you know about this work:

  • Every job is a profile of four challenge types — Electronic (cameras,
    networks, electronic locks), Physical (vaults, safes, structural),
    Confrontation (guards, armed response), and Social (blending in, talking
    your way through). Each one rates None, Low, Medium, or Hard.

  • Crew members have skill ratings in those areas — Low, Medium, or High.
    A specialist hits their level. A Hard challenge needs a High to clear
    alone, no exceptions.

  • Two crew members with skill in the same area work above the sum of their
    parts: pair them and you act at one level higher than the higher one,
    capped at High. Two Mediums together hit High. Two Lows together hit
    Medium. This is the move that makes a tight budget work — and it's how
    you cover a Hard area without paying for a $1,100 High specialist.

  • The exit always matters. A High Driver covers any escape; no driver
    means running on foot, and that limits which jobs you'll survive.

  • A Hard challenge with no High coverage and no two Mediums to pair on it
    is a walk into a wall. Plan around them or don't take the job."""


def _bid_prompt(strategy: str) -> str:
    return (
        "You are the Heist AI. You will play every creative role for a single heist: "
        "drafting the crew, picking the job, assigning crew to scenes, deciding at "
        "decision points, and narrating each scene in character. Stay in this role.\n\n"
        f"{_TRADECRAFT}\n\n"
        f"Player's strategy prompt:\n---\n{strategy}\n---\n\n"
        f"Bankroll: ${BANKROLL}. Roster (15 characters):\n{_roster_summary()}\n\n"
        "Draft your crew. Reply with ONLY a JSON object (no prose around it) of shape:\n"
        '{\n'
        '  "casting_strategy": "one-sentence strategy in your own words",\n'
        '  "bids": [\n'
        '    {"character_id": <int>, "bid": <int>=floor, "rationale": "<why>"}\n'
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
        "Pick the job this crew should attempt. Before you commit: for every Hard "
        "challenge in the job's profile, confirm the crew has either a High specialist "
        "in that area OR two Mediums who can pair on it. If neither, that job is a "
        "trap — pick a different one. Reply with ONLY JSON:\n"
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
        + "\n\nAssign one or more crew members to handle this scene. If a second "
        "crew member can support — same skill area as the challenge — send them too; "
        "pairs act one level higher than the better specialist. "
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
    ai: HeistAI, crew_so_far: list[Character], logs: list[TurnLog], emit: EmitFn = None
) -> list[Character]:
    fill_attempt = 0
    while len(crew_so_far) < 4:
        fill_attempt += 1
        remaining = 4 - len(crew_so_far)
        prompt = _fill_prompt(crew_so_far, remaining)
        turn = _call(ai, prompt, f"fill_{fill_attempt}", logs, emit)
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


def _snapshot(
    snapshot_fn: SnapshotFn,
    *,
    stage: str,
    strategy: str,
    ai: HeistAI,
    rng: random.Random,
    state: HeistState | None,
    extras: dict[str, Any],
    scene_idx: int,
) -> None:
    """Persist a runner-state snapshot. No-op when ``snapshot_fn`` is None.

    Defensive: if the snapshot raises (disk full, permission, etc.) we log
    and continue — losing snapshot fidelity is preferable to crashing a
    long-running heist."""
    if snapshot_fn is None:
        return
    from heist.persist import _serialize_rng
    from heist.serialize import state_to_dict
    payload: dict[str, Any] = {
        "stage": stage,
        "scene_idx": scene_idx,
        "strategy": strategy,
        "session_id": getattr(ai, "session_id", None),
        "rng_state": _serialize_rng(rng),
        "extras": {
            "strategy": extras.get("strategy", ""),
            "bid_logic": extras.get("bid_logic"),
            "casting_summary": extras.get("casting_summary", ""),
            "epilogue": extras.get("epilogue", ""),
            "job_viability_warning": extras.get("job_viability_warning"),
        },
        "state": state_to_dict(state) if state is not None else None,
    }
    try:
        snapshot_fn(payload)
    except Exception as exc:
        log.warn("snapshot_failed", stage=stage, error=str(exc))


def _broadcast_scene_done(
    emit: EmitFn, scene: Scene, state: HeistState, result: SceneResult
) -> None:
    if emit is None:
        return
    emit({
        "type": "scene_done",
        "scene_num": scene.number,
        "title": scene.title,
        "scene_type": scene.type,
        "challenge_skill": scene.challenge_skill,
        "challenge_level": scene.challenge_level.name if scene.challenge_level else None,
        "is_core": scene.is_core,
        "context": scene.context,
        "assigned_member_ids": result.assigned_member_ids,
        "reasoning": result.reasoning,
        "decision": result.decision,
        "success": result.success,
        "heat": state.heat,
        "aborted": state.aborted,
        "escape_success": state.escape_success,
        "escape_difficulty": state.escape_difficulty,
    })


def _draft_and_pick_job(
    strategy: str,
    ai: HeistAI,
    logs: list[TurnLog],
    extras: dict[str, Any],
    emit: EmitFn,
) -> tuple[Crew, Any]:
    """Stages 1+2: bidding + job selection. Returns (crew, job)."""
    bid_turn = _call(ai, _bid_prompt(strategy), "bid", logs, emit)
    bid_parsed = parse_json_block(bid_turn.text)
    extras["bid_logic"] = bid_parsed
    bids = _validate_bids(bid_parsed)
    crew_members = [c for c, _ in bids]
    crew_members = _fill_crew(ai, crew_members, logs, emit)
    crew = Crew(members=crew_members)
    if emit:
        from heist.serialize import crew_to_dict
        emit({"type": "crew_known", "crew": crew_to_dict(crew)})

    job_turn = _call(ai, _job_prompt(crew), "job_pick", logs, emit)
    job_parsed = parse_json_block(job_turn.text)
    name = job_parsed["job_name"]
    if name not in JOBS_BY_NAME:
        raise ValueError(f"AI picked unknown job {name!r}")
    job = JOBS_BY_NAME[name]
    if not job_is_viable(crew, job.profile):
        extras["job_viability_warning"] = (
            f"Crew lacks required Hard coverage for {job.name}; proceeding anyway."
        )
    if emit:
        from heist.serialize import job_to_dict
        emit({"type": "job_known", "job": job_to_dict(job)})
    return crew, job


def _roll_hidden_depth(
    job: Any, rng: random.Random, emit: EmitFn
) -> HiddenDepthRoll:
    element = rng.choice(job.hidden_depth)
    reward_label, reward_amount = rng.choice(job.reward_amounts)
    hidden = HiddenDepthRoll(
        element=element, reward_label=reward_label, reward_amount=reward_amount
    )
    if emit:
        emit({
            "type": "hidden_depth_rolled",
            "element_id": element.id,
            "description": element.description,
            "element_type": element.type,
            "reward_label": reward_label,
            "reward_amount": reward_amount,
        })
    return hidden


def _run_scene_loop(
    scenes: list[Scene],
    state: HeistState,
    ai: HeistAI,
    logs: list[TurnLog],
    extras: dict[str, Any],
    emit: EmitFn,
    on_scene: SceneCallback | None,
    snapshot_fn: SnapshotFn,
    strategy: str,
    rng: random.Random,
    start_idx: int = 0,
) -> None:
    """Execute scenes ``start_idx..end``, snapshotting after each."""
    for idx in range(start_idx, len(scenes)):
        scene = scenes[idx]
        if state.aborted and scene.type != "escape":
            continue
        result = _execute_scene(scene, state, ai, logs, emit)
        state.scene_results.append(result)
        extras["scene_narrations"].append(result)
        _broadcast_scene_done(emit, scene, state, result)
        if on_scene is not None:
            on_scene(result)
        _snapshot(
            snapshot_fn, stage=STAGE_IN_SCENE, strategy=strategy, ai=ai, rng=rng,
            state=state, extras=extras, scene_idx=idx + 1,
        )


def run_heist(
    strategy: str,
    ai: HeistAI,
    rng: random.Random | None = None,
    on_scene: SceneCallback | None = None,
    emit: EmitFn = None,
    snapshot_fn: SnapshotFn = None,
) -> tuple[HeistState, dict[str, Any]]:
    """Run one full heist end-to-end. Returns (final_state, extras)
    where extras carries the casting summary, scene narrations, and epilogue.

    If ``snapshot_fn`` is supplied, it's called after every major state
    mutation with a snapshot dict suitable for ``resume_heist``."""
    rng = rng or random.Random()
    logs: list[TurnLog] = []
    extras: dict[str, Any] = {
        "strategy": strategy,
        "bid_logic": None,
        "casting_summary": "",
        "scene_narrations": [],  # filled per scene
        "epilogue": "",
        "turn_logs": logs,
    }
    heist_start = time.monotonic()

    # 1+2. Draft + job selection
    crew, job = _draft_and_pick_job(strategy, ai, logs, extras, emit)
    # Snapshot at job_picked: enough to skip both _call("bid") and _call("job_pick").
    # state is None at this point — we synthesise a minimal state below.
    pre_state = HeistState(
        crew=crew, job=job,
        hidden_depth=HiddenDepthRoll(
            element=job.hidden_depth[0], reward_label="", reward_amount=0,
        ),
    )
    _snapshot(
        snapshot_fn, stage=STAGE_JOB_PICKED, strategy=strategy, ai=ai, rng=rng,
        state=pre_state, extras=extras, scene_idx=0,
    )

    # 3. Casting summary
    summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
    extras["casting_summary"] = parse_json_block(summary_turn.text).get("summary", "")

    # 4. Hidden depth roll
    from heist.scenes import generate_scenes
    hidden = _roll_hidden_depth(job, rng, emit)
    state = HeistState(crew=crew, job=job, hidden_depth=hidden)
    scenes = generate_scenes(job, hidden)
    _snapshot(
        snapshot_fn, stage=STAGE_CASTING_SUMMARY_DONE, strategy=strategy, ai=ai,
        rng=rng, state=state, extras=extras, scene_idx=0,
    )

    # 5. Scene loop
    _run_scene_loop(
        scenes, state, ai, logs, extras, emit, on_scene,
        snapshot_fn, strategy, rng, start_idx=0,
    )

    # 6. Escape already handled inside loop → compute reward
    _finalize_reward(state)

    # 7. Epilogue
    ep_turn = _call(ai, _epilogue_prompt(state), "epilogue", logs, emit)
    extras["epilogue"] = parse_json_block(ep_turn.text).get("epilogue", "")
    _snapshot(
        snapshot_fn, stage=STAGE_DONE, strategy=strategy, ai=ai, rng=rng,
        state=state, extras=extras, scene_idx=len(scenes),
    )

    total = time.monotonic() - heist_start
    extras["total_seconds"] = total
    print(
        f"\n[heist complete: {len(logs)} rounds, "
        f"{sum(t.seconds for t in logs):.1f}s in AI calls, "
        f"{total:.1f}s wall clock]",
        file=sys.stderr,
    )

    return state, extras


def resume_heist(
    snapshot: dict,
    ai: HeistAI,
    *,
    emit: EmitFn = None,
    snapshot_fn: SnapshotFn = None,
    on_scene: SceneCallback | None = None,
) -> tuple[HeistState, dict[str, Any]]:
    """Continue a heist from a runner snapshot.

    The caller must have already configured ``ai.session_id`` to the value
    from the snapshot (the server does this before spawning the resume
    thread, since AI construction is the server's responsibility).
    """
    from heist.persist import _deserialize_rng_into
    from heist.scenes import generate_scenes
    from heist.serialize import scene_result_from_dict, state_from_dict

    stage = snapshot.get("stage", STAGE_DRAFTING)
    strategy = snapshot.get("strategy", "")
    scene_idx = int(snapshot.get("scene_idx", 0))

    rng = random.Random()
    rng_state = snapshot.get("rng_state")
    if rng_state:
        _deserialize_rng_into(rng, rng_state)

    logs: list[TurnLog] = []
    extras_snap = snapshot.get("extras") or {}
    extras: dict[str, Any] = {
        "strategy": extras_snap.get("strategy", strategy),
        "bid_logic": extras_snap.get("bid_logic"),
        "casting_summary": extras_snap.get("casting_summary", ""),
        "scene_narrations": [],
        "epilogue": extras_snap.get("epilogue", ""),
        "turn_logs": logs,
    }
    if extras_snap.get("job_viability_warning"):
        extras["job_viability_warning"] = extras_snap["job_viability_warning"]

    heist_start = time.monotonic()

    # If we crashed before even picking a job, restart from scratch — no state
    # to inherit. Treat as a fresh run with the same strategy + RNG seed.
    if stage in (STAGE_DRAFTING, "") or snapshot.get("state") is None:
        return run_heist(strategy, ai, rng=rng, emit=emit, snapshot_fn=snapshot_fn,
                         on_scene=on_scene)

    state = state_from_dict(snapshot["state"])
    # Rehydrate scene_narrations from the persisted scene_results so the
    # caller-visible extras matches what a clean run would produce.
    extras["scene_narrations"] = [
        scene_result_from_dict(r)
        for r in snapshot["state"].get("scene_results", [])
    ]

    if stage == STAGE_JOB_PICKED:
        # Need to redo casting_summary, hidden_depth roll, scenes, scene loop, epilogue.
        if emit:
            from heist.serialize import crew_to_dict, job_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
            emit({"type": "job_known", "job": job_to_dict(state.job)})

        summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
        extras["casting_summary"] = parse_json_block(summary_turn.text).get("summary", "")

        hidden = _roll_hidden_depth(state.job, rng, emit)
        state = HeistState(crew=state.crew, job=state.job, hidden_depth=hidden)
        scenes = generate_scenes(state.job, hidden)
        _snapshot(
            snapshot_fn, stage=STAGE_CASTING_SUMMARY_DONE, strategy=strategy, ai=ai,
            rng=rng, state=state, extras=extras, scene_idx=0,
        )
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=0)

    elif stage == STAGE_CASTING_SUMMARY_DONE:
        # Hidden depth already rolled into state.hidden_depth. Generate scenes
        # and run from scene 0.
        if emit:
            from heist.serialize import crew_to_dict, job_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
            emit({"type": "job_known", "job": job_to_dict(state.job)})
            emit({
                "type": "hidden_depth_rolled",
                "element_id": state.hidden_depth.element.id,
                "description": state.hidden_depth.element.description,
                "element_type": state.hidden_depth.element.type,
                "reward_label": state.hidden_depth.reward_label,
                "reward_amount": state.hidden_depth.reward_amount,
            })
        scenes = generate_scenes(state.job, state.hidden_depth)
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=0)

    elif stage == STAGE_IN_SCENE:
        if emit:
            from heist.serialize import crew_to_dict, job_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
            emit({"type": "job_known", "job": job_to_dict(state.job)})
        scenes = generate_scenes(state.job, state.hidden_depth)
        # state.scene_results was loaded from the snapshot. _run_scene_loop
        # will append from there; truncate to scene_idx in case the snapshot
        # captured trailing partials.
        state.scene_results = state.scene_results[:scene_idx]
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=scene_idx)

    elif stage in (STAGE_EPILOGUE, STAGE_DONE):
        # State and scene_results already loaded. Just (re-)run epilogue if missing.
        pass
    else:
        raise ValueError(f"unknown resume stage: {stage!r}")

    _finalize_reward(state)

    if not extras.get("epilogue"):
        ep_turn = _call(ai, _epilogue_prompt(state), "epilogue", logs, emit)
        extras["epilogue"] = parse_json_block(ep_turn.text).get("epilogue", "")
        _snapshot(
            snapshot_fn, stage=STAGE_DONE, strategy=strategy, ai=ai, rng=rng,
            state=state, extras=extras, scene_idx=scene_idx,
        )

    total = time.monotonic() - heist_start
    extras["total_seconds"] = total
    print(
        f"\n[heist resumed + complete: {len(logs)} new rounds, "
        f"{sum(t.seconds for t in logs):.1f}s in AI calls, "
        f"{total:.1f}s wall clock]",
        file=sys.stderr,
    )
    return state, extras


def _execute_scene(
    scene: Scene, state: HeistState, ai: HeistAI, logs: list[TurnLog], emit: EmitFn = None
) -> SceneResult:
    if scene.type == "escape":
        return _execute_escape(scene, state, ai, logs, emit)

    if emit:
        emit({
            "type": "scene_start",
            "scene_num": scene.number,
            "title": scene.title,
            "scene_type": scene.type,
            "challenge_skill": scene.challenge_skill,
            "challenge_level": scene.challenge_level.name if scene.challenge_level else None,
            "is_core": scene.is_core,
            "context": scene.context,
        })

    assign_turn = _call(
        ai, _scene_assign_prompt(scene, state), f"scene_{scene.number}_assign", logs, emit
    )
    assign_parsed = parse_json_block(assign_turn.text)
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    assigned = [ROSTER_BY_ID[i] for i in member_ids if i in ROSTER_BY_ID]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    decision: dict | None = None
    success: bool | None = None
    outcome_summary: str

    if scene.type == "decision":
        dec_turn = _call(
            ai, _scene_decision_prompt(scene), f"scene_{scene.number}_decision", logs, emit
        )
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

    narrate_turn = _call(
        ai, _scene_narrate_prompt(scene, outcome_summary),
        f"scene_{scene.number}_narrate", logs, emit,
    )
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


def _execute_escape(
    scene: Scene, state: HeistState, ai: HeistAI, logs: list[TurnLog], emit: EmitFn = None
) -> SceneResult:
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
    if emit:
        emit({
            "type": "scene_start",
            "scene_num": scene.number,
            "title": scene.title,
            "scene_type": "escape",
            "challenge_skill": "driver",
            "challenge_level": None,
            "is_core": True,
            "context": scene.context,
        })

    assign_turn = _call(
        ai, _scene_assign_prompt(scene, state),
        f"scene_{scene.number}_escape_assign", logs, emit,
    )
    assign_parsed = parse_json_block(assign_turn.text)
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    narrate_turn = _call(
        ai, _scene_narrate_prompt(scene, outcome_summary),
        f"scene_{scene.number}_escape_narrate", logs, emit,
    )
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
