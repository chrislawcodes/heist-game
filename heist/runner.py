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
    Outcome,
    effective_skill,
    escape_resolves,
    job_is_viable,
    outcome_is_pass,
    resolve_outcome,
)
from heist.state import (
    CHALLENGE_TO_SKILL,
    Campaign,
    ChallengeLevel,
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
# whose snapshot was last persisted. Order matches the new run_heist flow:
# bid → casting_summary → job_pick → hidden_depth → scenes → epilogue → done.
STAGE_DRAFTING       = "drafting"          # initial / never snapshotted
STAGE_CREW_DRAFTED   = "crew_drafted"      # after bid: crew is known, no summary yet
STAGE_SUMMARY_DONE   = "summary_done"      # after casting_summary, no job yet
STAGE_JOB_PICKED     = "job_picked"        # after job_pick + hidden_depth rolled
STAGE_IN_SCENE       = "in_scene"          # snapshot after every scene
STAGE_EPILOGUE       = "epilogue"
STAGE_DONE           = "done"

_SKILL_TO_CATEGORY = {skill: category for category, skill in CHALLENGE_TO_SKILL.items()}


def _call(
    ai: HeistAI, prompt: str, label: str, logs: list[TurnLog], emit: EmitFn = None
) -> AgentTurn:
    """Time one AI call, log it, echo to stderr, and optionally emit turn events."""
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
    return turn


def _call_json(
    ai: HeistAI, prompt: str, label: str, logs: list[TurnLog],
    emit: EmitFn = None, retries: int = 2,
) -> tuple[AgentTurn, dict]:
    """Call the AI and parse its JSON response. On parse failure, re-ask the
    model in the same session (up to `retries` times) before giving up.

    The retry attempts do NOT emit viewer events and are not subject to the
    inter-turn pacing delay (pass emit=None), but they are still logged via
    _call's normal ai_call logging. If all attempts fail, the final parse
    exception propagates (hard-fail preserved)."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        if attempt == 0:
            turn = _call(ai, prompt, label, logs, emit)
        else:
            retry_prompt = (
                "Your last reply could not be parsed as JSON. Reply with ONLY "
                "the JSON object I asked for — no prose, no markdown fences, "
                "and make sure every string is properly closed and escaped."
            )
            # No emit on retries: keeps the viewer replay clean and skips the
            # inter-turn delay. Still logged as an ai_call by _call.
            turn = _call(ai, retry_prompt, f"{label}_retry{attempt}", logs, emit=None)
        try:
            return turn, parse_json_block(turn.text)
        except ValueError as exc:   # json.JSONDecodeError subclasses ValueError
            last_exc = exc
            log.warn("parse_retry", label=label, attempt=attempt, error=str(exc))
    assert last_exc is not None
    log.error("parse_failed_final", label=label, attempts=retries + 1, error=str(last_exc))
    raise last_exc


def _roster_summary() -> str:
    lines = []
    for c in ROSTER:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        lines.append(f"  - id={c.id}, name={c.name!r}, skills=({skills}), floor=${c.floor_cost}")
    return "\n".join(lines)


def _job_slate_summary(available_jobs: list | None = None) -> str:
    jobs = available_jobs if available_jobs is not None else JOBS
    lines = []
    for j in jobs:
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
        f"Bankroll: ${BANKROLL}. Roster (16 characters):\n{_roster_summary()}\n\n"
        "Draft your crew. Reply with ONLY a JSON object (no prose around it) of shape:\n"
        '{\n'
        '  "casting_strategy": "one-sentence strategy in your own words",\n'
        '  "bids": [\n'
        '    {"character_id": <int>, "bid": <int>=floor, "rationale": "<why>"}\n'
        '  ],\n'
        '  "reasoning": "<why this overall composition fits the prompt>"\n'
        "}\n"
        "Bids must be ≥ each character's floor cost. Total bids ≤ $2,000,000. "
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
        f"spend ≤ $2,000,000. Reply with ONLY JSON:\n"
        '{"additions": [<character_id>, ...], "reasoning": "<why>"}'
    )


def _job_prompt(crew: Crew, available_jobs: list | None = None) -> str:
    crew_lines = []
    for c in crew.members:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        crew_lines.append(f"  - {c.name}: {skills}")
    return (
        f"Crew assembled (spent ${crew.total_cost}/{BANKROLL}):\n"
        + "\n".join(crew_lines)
        + f"\n\nJob slate:\n{_job_slate_summary(available_jobs)}\n\n"
        "Pick the job this crew should attempt. Before you commit: for every Hard "
        "challenge in the job's profile, confirm the crew has either a High specialist "
        "in that area OR two Mediums who can pair on it. If neither, that job is a "
        "trap — pick a different one. Reply with ONLY JSON:\n"
        '{\n'
        '  "job_name": "<exact name>",\n'
        '  "why_this": "<why this job fits — crew skills, budget, risk>",\n'
        '  "why_not":  "<for each of the other jobs on the slate, one sentence on '
        'why it was a worse pick>"\n'
        "}"
    )


def _campaign_context(campaign: Campaign) -> str:
    return (
        f"Campaign context: Round {campaign.round_idx + 1}/{campaign.rounds_total}. "
        f"Notoriety: {campaign.notoriety}/10. "
        f"Banked loot: ${campaign.banked_loot:,}. "
        f"Standing crew: {len(campaign.standing_crew)} member(s)."
    )


def _summary_prompt() -> str:
    # Runs BEFORE job_pick — talk only about the crew composition. The job
    # hasn't been chosen yet.
    return (
        "Now write a casting summary (a transparent paragraph or two for the player) "
        "explaining the bid logic and who you hired. Be honest about the trade-offs "
        "you made. (You have not picked a job yet — focus on the crew composition.) "
        "Reply with ONLY the prose — 2-4 paragraphs in markdown, no heading."
    )


def _scene_assign_prompt(scene: Scene, state: HeistState) -> str:
    crew_lines = []
    free_members = [c for c in state.crew.members if c.id not in state.caught_member_ids]
    for c in free_members:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        crew_lines.append(f"  id={c.id}: {c.name} ({skills})")
    challenge_desc = ""
    if scene.challenge_skill is not None and scene.challenge_level is not None:
        challenge_desc = (
            f"  Challenge: {scene.challenge_skill}, level {scene.challenge_level.name}\n"
        )
    decision_note = (
        "\nThis is a BONUS opportunity — optional, not a core scene. You will be "
        "asked in the next step whether to pursue it. Do NOT set abort:true just "
        "to skip the bonus; use abort only to abandon the entire heist.\n"
        if scene.type == "decision" else ""
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
        "Set \"abort\": true ONLY to abandon the ENTIRE heist mid-run "
        "(not to skip a single scene).\n"
        + decision_note
        + "Reply with ONLY JSON:\n"
        '{"assigned_member_ids": [<int>, ...], "abort": <true|false>, '
        '"reasoning": "<why these people or why abort>"}'
    )


def _scene_decision_prompt(scene: Scene) -> str:
    return (
        f"Decision point in scene {scene.number}: {scene.context}\n"
        "Decide whether to pursue. Reply with ONLY JSON:\n"
        '{"pursue": <true|false>, "reasoning": "<why, with reference to the player\'s prompt>"}'
    )


def _abort_decision_prompt(scene: Scene, outcome_summary: str) -> str:
    core_note = " This was a core scene." if scene.is_core else ""
    return (
        f"Scene {scene.number} ({scene.title}) just failed.{core_note}\n"
        f"Outcome: {outcome_summary}\n"
        "Heat has already increased. Do you abort now — take the escape with "
        "whatever's secured — or push on to the next scene?\n"
        'Reply with ONLY JSON: {"abort": <true|false>, "reasoning": "<why, '
        'referencing your strategy and the crew\'s situation>"}'
    )


def _crew_brief(assigned: list) -> str:
    """One-paragraph brief per assigned character: voice, quirk, look."""
    lines = []
    for c in assigned:
        parts = [f"**{c.name}**"]
        if c.voice:
            parts.append(f"Voice: {c.voice}")
        if c.quirk:
            parts.append(f"Quirk: {c.quirk}")
        if c.look:
            parts.append(f"Look: {c.look}")
        lines.append(" | ".join(parts))
    return "\n".join(f"  - {ln}" for ln in lines)


def _scene_narrate_prompt(scene: Scene, outcome_summary: str, assigned: list | None = None) -> str:
    crew_section = ""
    if assigned:
        crew_section = (
            "\nAssigned crew for this scene:\n"
            f"{_crew_brief(assigned)}\n\n"
            "Write them as they actually are — use their specific voices, gestures, and looks.\n"
        )
    return (
        f"Narrate scene {scene.number} ({scene.title}) in 100-150 words. "
        "Keep it tight: short paragraphs, terse dialogue with minimal tags, "
        "concrete sensory detail over flowery prose."
        f"{crew_section}\n"
        "The mechanical outcome:\n"
        f"  {outcome_summary}\n\n"
        "Reply with ONLY the prose — in markdown, no heading."
    )


def _epilogue_prompt(state: HeistState) -> str:
    return (
        f"The heist is done. Final state:\n"
        f"  - Aborted: {state.aborted}\n"
        f"  - Escape: {state.escape_success}\n"
        f"  - Take: ${state.final_take:,}\n"
        f"  - Failed scenes: "
        f"{[r.scene.title for r in state.scene_results if r.success is False]}\n\n"
        "Write a short epilogue (100-200 words). Reply with ONLY the prose — "
        "in markdown, no heading."
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
        _, parsed = _call_json(ai, prompt, f"fill_{fill_attempt}", logs, emit)
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
) -> tuple[Outcome, str]:
    """Returns (outcome, outcome_summary)."""
    assert scene.challenge_skill is not None and scene.challenge_level is not None
    skill = effective_skill(assigned, scene.challenge_skill)
    outcome = resolve_outcome(skill, scene.challenge_level)
    gap = int(scene.challenge_level) - int(skill)
    if scene.challenge_level == ChallengeLevel.NONE:
        gap_text = "challenge level NONE"
    else:
        gap_text = f"gap {gap}"
    return outcome, (
        f"Crew skill in {scene.challenge_skill}: {skill.name}; "
        f"challenge level: {scene.challenge_level.name}; {gap_text}. "
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
            "auction_state": extras.get("auction_state"),
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
    emit: EmitFn,
    scene: Scene,
    state: HeistState,
    result: SceneResult,
    *,
    heat_delta: int,
    caught_member_id: int | None,
    loot_secured: int,
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
        "outcome": result.outcome,
        "heat_delta": heat_delta,
        "heat": state.heat,
        "caught_member_id": caught_member_id,
        "loot_secured": loot_secured,
        "secured_take": state.secured_take,
        "aborted": state.aborted,
        "escape_success": state.escape_success,
        "escape_difficulty": state.escape_difficulty,
    })


def _draft_crew(
    strategy: str,
    ai: HeistAI,
    logs: list[TurnLog],
    extras: dict[str, Any],
    emit: EmitFn,
) -> Crew:
    """Draft only — returns the assembled Crew. Job pick happens later, after
    the casting summary."""
    _, bid_parsed = _call_json(ai, _bid_prompt(strategy), "bid", logs, emit)
    extras["bid_logic"] = bid_parsed
    bids = _validate_bids(bid_parsed)
    crew_members = [c for c, _ in bids]
    crew_members = _fill_crew(ai, crew_members, logs, emit)
    crew = Crew(members=crew_members)
    if emit:
        from heist.serialize import crew_to_dict
        emit({"type": "crew_known", "crew": crew_to_dict(crew)})
    return crew


def _pick_job(crew: Crew, ai: HeistAI, logs: list[TurnLog], extras: dict, emit: EmitFn) -> Any:
    """Stage: pick a job given the assembled crew. Emits job_known."""
    _, job_parsed = _call_json(ai, _job_prompt(crew), "job_pick", logs, emit)
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
    return job


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
        heat_before = state.heat
        take_before = state.secured_take
        caught_count_before = len(state.caught_member_ids)
        result = _execute_scene(scene, state, ai, logs, emit, rng)
        heat_delta = state.heat - heat_before
        loot_secured = state.secured_take - take_before
        caught_member_id: int | None = None
        if len(state.caught_member_ids) > caught_count_before:
            caught_member_id = state.caught_member_ids[caught_count_before]
        state.scene_results.append(result)
        extras["scene_narrations"].append(result)
        _broadcast_scene_done(
            emit, scene, state, result,
            heat_delta=heat_delta,
            caught_member_id=caught_member_id,
            loot_secured=loot_secured,
        )
        if on_scene is not None:
            on_scene(result)
        _snapshot(
            snapshot_fn, stage=STAGE_IN_SCENE, strategy=strategy, ai=ai, rng=rng,
            state=state, extras=extras, scene_idx=idx + 1,
        )


def run_one_job(
    strategy: str,
    ai: HeistAI,
    campaign: Campaign,
    *,
    rng: random.Random,
    emit: EmitFn = None,
    snapshot_fn: SnapshotFn = None,
) -> tuple[HeistState, dict[str, Any]] | None:
    """Run one campaign round. Returns (state, extras) or None if job pool empty."""
    from heist.scenes import generate_scenes
    from heist.state import Crew

    available_jobs = [j for j in JOBS if j.name not in campaign.attempted_job_names]
    if not available_jobs:
        return None

    crew = Crew(members=list(campaign.standing_crew))
    logs: list[TurnLog] = []
    extras: dict[str, Any] = {
        "strategy": strategy,
        "bid_logic": None,
        "casting_summary": "",
        "scene_narrations": [],
        "epilogue": "",
        "turn_logs": logs,
        "campaign_round": campaign.round_idx,
    }

    # Job pick with campaign context prepended.
    ctx = _campaign_context(campaign)
    _, job_parsed = _call_json(
        ai, ctx + "\n\n" + _job_prompt(crew, available_jobs), "job_pick", logs, emit
    )

    # Validate; fall back to first available if AI picks an already-attempted job.
    jobs_by_name = {j.name: j for j in available_jobs}
    name = job_parsed.get("job_name", "")
    if name not in jobs_by_name:
        log.warn(
            "job_pick_fallback",
            picked=name,
            available=[j.name for j in available_jobs],
        )
        name = available_jobs[0].name
    job = jobs_by_name[name]

    if emit:
        from heist.serialize import job_to_dict

        emit({"type": "job_known", "job": job_to_dict(job)})

    hidden = _roll_hidden_depth(job, rng, emit)
    state = HeistState(crew=crew, job=job, hidden_depth=hidden)
    scenes = generate_scenes(job, hidden)

    _snapshot(
        snapshot_fn, stage=STAGE_JOB_PICKED, strategy=strategy, ai=ai,
        rng=rng, state=state, extras=extras, scene_idx=0,
    )
    _run_scene_loop(
        scenes, state, ai, logs, extras, emit, None,
        snapshot_fn, strategy, rng, start_idx=0,
    )
    _finalize_reward(state)
    _emit_heist_complete(emit, state)

    ep_turn = _call(ai, _epilogue_prompt(state), "epilogue", logs, emit)
    extras["epilogue"] = ep_turn.text
    extras["total_seconds"] = sum(t.seconds for t in logs)
    return state, extras


def run_heist(
    strategy: str,
    ai: HeistAI,
    *,
    crew: Crew | None = None,
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

    # Back-compat path: if no crew is provided, keep the legacy draft → fill
    # flow so older resume snapshots and single-AI tests still behave the same.
    if crew is None:
        crew = _draft_crew(strategy, ai, logs, extras, emit)
        # Snapshot crew_drafted: stash the crew so resume can skip _call("bid").
        # No job yet, so we synthesise a placeholder HeistState that just carries
        # the crew. resume_heist treats job/hidden_depth as TBD at this stage.
        placeholder_job = JOBS[0]   # never observed; replaced by real pick later
        pre_state = HeistState(
            crew=crew, job=placeholder_job,
            hidden_depth=HiddenDepthRoll(
                element=placeholder_job.hidden_depth[0], reward_label="", reward_amount=0,
            ),
        )
        _snapshot(
            snapshot_fn, stage=STAGE_CREW_DRAFTED, strategy=strategy, ai=ai, rng=rng,
            state=pre_state, extras=extras, scene_idx=0,
        )
    else:
        placeholder_job = JOBS[0]   # never observed; replaced by real pick later
        pre_state = HeistState(
            crew=crew, job=placeholder_job,
            hidden_depth=HiddenDepthRoll(
                element=placeholder_job.hidden_depth[0], reward_label="", reward_amount=0,
            ),
        )

    # 2. Casting summary (BEFORE job pick — talks only about the crew)
    summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
    extras["casting_summary"] = summary_turn.text
    _snapshot(
        snapshot_fn, stage=STAGE_SUMMARY_DONE, strategy=strategy, ai=ai, rng=rng,
        state=pre_state, extras=extras, scene_idx=0,
    )

    # 3. Job pick
    job = _pick_job(crew, ai, logs, extras, emit)

    # 4. Hidden depth roll
    from heist.scenes import generate_scenes
    hidden = _roll_hidden_depth(job, rng, emit)
    state = HeistState(crew=crew, job=job, hidden_depth=hidden)
    scenes = generate_scenes(job, hidden)
    _snapshot(
        snapshot_fn, stage=STAGE_JOB_PICKED, strategy=strategy, ai=ai,
        rng=rng, state=state, extras=extras, scene_idx=0,
    )

    # 5. Scene loop
    _run_scene_loop(
        scenes, state, ai, logs, extras, emit, on_scene,
        snapshot_fn, strategy, rng, start_idx=0,
    )

    # 6. Escape already handled inside loop → compute reward
    _finalize_reward(state)
    _emit_heist_complete(emit, state)

    # 7. Epilogue
    ep_turn = _call(ai, _epilogue_prompt(state), "epilogue", logs, emit)
    extras["epilogue"] = ep_turn.text
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

    if stage == STAGE_CREW_DRAFTED:
        # Crew drafted, no summary or job yet. Re-emit crew_known so a viewer
        # connecting post-restart can draw the board; then run summary, pick
        # job, roll hidden depth, run scenes, epilogue.
        if emit:
            from heist.serialize import crew_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
        summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
        extras["casting_summary"] = summary_turn.text
        _snapshot(
            snapshot_fn, stage=STAGE_SUMMARY_DONE, strategy=strategy, ai=ai,
            rng=rng, state=state, extras=extras, scene_idx=0,
        )
        job = _pick_job(state.crew, ai, logs, extras, emit)
        hidden = _roll_hidden_depth(job, rng, emit)
        state = HeistState(crew=state.crew, job=job, hidden_depth=hidden)
        scenes = generate_scenes(job, hidden)
        _snapshot(
            snapshot_fn, stage=STAGE_JOB_PICKED, strategy=strategy, ai=ai,
            rng=rng, state=state, extras=extras, scene_idx=0,
        )
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=0)

    elif stage == STAGE_SUMMARY_DONE:
        # Summary done, no job yet. Re-emit crew_known; pick job, roll hidden,
        # run scenes.
        if emit:
            from heist.serialize import crew_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
        job = _pick_job(state.crew, ai, logs, extras, emit)
        hidden = _roll_hidden_depth(job, rng, emit)
        state = HeistState(crew=state.crew, job=job, hidden_depth=hidden)
        scenes = generate_scenes(job, hidden)
        _snapshot(
            snapshot_fn, stage=STAGE_JOB_PICKED, strategy=strategy, ai=ai,
            rng=rng, state=state, extras=extras, scene_idx=0,
        )
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=0)

    elif stage == STAGE_JOB_PICKED:
        # Crew + summary + job all done, hidden depth already rolled.
        # Generate scenes and run from scene 0.
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
    _emit_heist_complete(emit, state)

    if not extras.get("epilogue"):
        ep_turn = _call(ai, _epilogue_prompt(state), "epilogue", logs, emit)
        extras["epilogue"] = ep_turn.text
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
    scene: Scene,
    state: HeistState,
    ai: HeistAI,
    logs: list[TurnLog],
    emit: EmitFn = None,
    rng: random.Random | None = None,
) -> SceneResult:
    if scene.type == "escape":
        assert rng is not None
        return _execute_escape(scene, state, ai, logs, emit, rng)

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

    _, assign_parsed = _call_json(
        ai, _scene_assign_prompt(scene, state), f"scene_{scene.number}_assign", logs, emit
    )
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    free_ids = {m.id for m in _free_members(state)}
    assigned = [ROSTER_BY_ID[i] for i in member_ids if i in free_ids and i in ROSTER_BY_ID]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    decision: dict | None = None
    success: bool | None = None
    outcome_summary: str
    scene_outcome: Outcome | None = None

    if bool(assign_parsed.get("abort", False)):
        state.aborted = True
        decision = {"abort": True, "reasoning": assignment_reasoning}
        outcome_summary = "Crew aborted the heist before resolving this scene."
        return SceneResult(
            scene=scene,
            assigned_member_ids=member_ids,
            success=None,
            narration="",
            reasoning=assignment_reasoning,
            decision=decision,
            outcome=None,
        )

    if scene.type == "decision":
        _, dec_parsed = _call_json(
            ai, _scene_decision_prompt(scene), f"scene_{scene.number}_decision", logs, emit
        )
        pursue = bool(dec_parsed.get("pursue", False))
        decision = {"pursue": pursue, "reasoning": dec_parsed.get("reasoning", "")}
        state.bonus_pursued = pursue
        if pursue:
            outcome, outcome_summary = _resolve_challenge_scene(scene, assigned)
            scene_outcome = outcome
            success = outcome_is_pass(outcome)
            state.bonus_succeeded = success
            if outcome != Outcome.CLEAN:
                state.heat += 1
            if outcome == Outcome.CAUGHT:
                caught = _catch_member_from_assigned(scene, assigned)
                if caught is not None and caught.id not in state.caught_member_ids:
                    state.caught_member_ids.append(caught.id)
            if success:
                # Sample bonus amount: midpoint of range
                el = state.hidden_depth.element
                lo, hi = el.effect["bonus_amount_range"]
                state.bonus_amount = (lo + hi) // 2
                state.secured_take += state.bonus_amount
            elif not success:
                state.heat += 1
                _, abort_parsed = _call_json(
                    ai, _abort_decision_prompt(scene, outcome_summary),
                    f"scene_{scene.number}_abort", logs, emit,
                )
                if abort_parsed.get("abort", False):
                    state.aborted = True
                    outcome_summary += " Crew decided to abort."
                else:
                    outcome_summary += " Crew is pushing on."
        else:
            outcome_summary = "Crew declined the bonus opportunity."
    elif scene.type in ("challenge", "hidden_depth"):
        outcome, outcome_summary = _resolve_challenge_scene(scene, assigned)
        scene_outcome = outcome
        success = outcome_is_pass(outcome)
        if outcome != Outcome.CLEAN:
            state.heat += 1
        if outcome == Outcome.CAUGHT:
            caught = _catch_member_from_assigned(scene, assigned)
            if caught is not None and caught.id not in state.caught_member_ids:
                state.caught_member_ids.append(caught.id)
        if success:
            category = _scene_category(scene)
            if category is not None and category in state.job.scene_loot:
                state.secured_take += state.job.scene_loot[category]
        else:
            _, abort_parsed = _call_json(
                ai, _abort_decision_prompt(scene, outcome_summary),
                f"scene_{scene.number}_abort", logs, emit,
            )
            if abort_parsed.get("abort", False):
                state.aborted = True
                outcome_summary += " Crew decided to abort."
            else:
                outcome_summary += " Crew is pushing on."
    elif scene.type in ("setup", "transition"):
        outcome_summary = f"{scene.title}: no mechanical resolution."
    else:
        outcome_summary = "(no resolution)"

    narrate_turn = _call(
        ai, _scene_narrate_prompt(scene, outcome_summary, assigned),
        f"scene_{scene.number}_narrate", logs, emit,
    )
    narration = narrate_turn.text

    return SceneResult(
        scene=scene,
        assigned_member_ids=member_ids,
        success=success,
        narration=narration,
        reasoning=assignment_reasoning,
        decision=decision,
        outcome=scene_outcome.name if scene_outcome is not None else None,
    )


def _execute_escape(
    scene: Scene,
    state: HeistState,
    ai: HeistAI,
    logs: list[TurnLog],
    emit: EmitFn = None,
    rng: random.Random | None = None,
) -> SceneResult:
    assert rng is not None
    free_members = _free_members(state)
    free_crew = Crew(members=free_members)
    difficulty = state.job.escape_modifier + state.heat
    success = bool(free_members) and escape_resolves(
        free_crew, state.heat, state.job.escape_modifier
    )[0]
    state.escape_success = success
    state.escape_difficulty = difficulty
    driver_skill = effective_skill(free_members, "driver")
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

    _, assign_parsed = _call_json(
        ai, _scene_assign_prompt(scene, state),
        f"scene_{scene.number}_escape_assign", logs, emit,
    )
    member_ids = [int(i) for i in assign_parsed.get("assigned_member_ids", [])]
    free_ids = {m.id for m in free_members}
    escape_assigned = [ROSTER_BY_ID[i] for i in member_ids if i in free_ids and i in ROSTER_BY_ID]
    assignment_reasoning = assign_parsed.get("reasoning", "")

    if not success:
        remaining_free = [m for m in free_members if m.id not in state.caught_member_ids]
        if remaining_free:
            caught = rng.choice(remaining_free)
            state.caught_member_ids.append(caught.id)

    narrate_turn = _call(
        ai, _scene_narrate_prompt(scene, outcome_summary, escape_assigned),
        f"scene_{scene.number}_escape_narrate", logs, emit,
    )
    narration = narrate_turn.text

    return SceneResult(
        scene=scene,
        assigned_member_ids=member_ids,
        success=success,
        narration=narration,
        reasoning=assignment_reasoning,
        decision=None,
    )


def _finalize_reward(state: HeistState) -> None:
    free = [m for m in state.crew.members if m.id not in state.caught_member_ids]
    state.final_take = state.secured_take if free else 0


def _emit_heist_complete(emit: EmitFn, state: HeistState) -> None:
    if emit is None:
        return
    free_ids = [m.id for m in state.crew.members if m.id not in state.caught_member_ids]
    emit({
        "type": "heist_complete",
        "final_take": state.final_take,
        "secured_take": state.secured_take,
        "escape_success": state.escape_success,
        "aborted": state.aborted,
        "caught_member_ids": list(state.caught_member_ids),
        "free_member_ids": free_ids,
    })
