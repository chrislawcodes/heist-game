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
from heist.content import BANKROLL, JOBS, JOBS_BY_NAME, ROSTER_BY_ID
from heist.logs import log
from heist.mechanics import (
    Outcome,
    effective_skill,
    escape_resolves,
    free_probe_budget,
    job_is_viable,
    outcome_is_pass,
)
from heist.prompts import (
    _abort_decision_prompt,
    _bid_prompt,
    _campaign_context,
    _epilogue_prompt,
    _fill_prompt,
    _job_prompt,
    _scene_assign_prompt,
    _scene_decision_prompt,
    _scene_narrate_prompt,
    _scout_prompt,
    _summary_prompt,
)
from heist.resolution import (
    _catch_member_from_assigned,
    _finalize_reward,
    _free_members,
    _resolve_challenge_scene,
    _scene_category,
    _validate_bids,
)
from heist.scouting import apply_probes, roll_slate_scores
from heist.state import (
    Campaign,
    Character,
    Crew,
    HeistState,
    HiddenDepthRoll,
    Scene,
    SceneResult,
    ScoutState,
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
        # elapsed_ms wraps the whole ai.ask (incl. any retries + pauses);
        # attempt_ms is the clean latency of the single attempt that succeeded.
        elapsed_ms=int(elapsed * 1000),
        attempts=getattr(ai, "last_attempts", 1),
        attempt_ms=getattr(ai, "last_attempt_ms", int(elapsed * 1000)),
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


def _run_scout_turn(
    crew: Crew,
    available_jobs: list,
    slate_scores: dict[str, dict[str, int]],
    ai: HeistAI,
    logs: list[TurnLog],
    emit: EmitFn,
) -> ScoutState:
    """Pre-commit scouting: the AI probes the slate to reveal exact 1-10 challenge
    scores within its free budget (crew size + best-driver bonus). Emits a
    `scouted` event per applied probe so the viewer can reveal incrementally."""
    scout_state = ScoutState(free_probes=free_probe_budget(crew.members))
    if scout_state.free_probes <= 0:
        return scout_state
    try:
        _, parsed = _call_json(
            ai, _scout_prompt(crew, available_jobs, scout_state), "scout", logs, emit
        )
    except Exception as exc:
        log.warn("scout_turn_failed", error=str(exc))
        return scout_state
    if isinstance(parsed, dict):
        scout_state.rationale = str(parsed.get("rationale", "") or "")
    probes = parsed.get("probes", []) if isinstance(parsed, dict) else []
    events = apply_probes(
        scout_state, slate_scores, probes if isinstance(probes, list) else []
    )
    if emit:
        for ev in events:
            emit(ev)
    return scout_state


def pick_job_from_board(
    ai: HeistAI,
    crew: Crew,
    available_jobs: list,
    scout_state: ScoutState,
    campaign: Campaign,
    logs: list[TurnLog],
    emit: EmitFn,
) -> Any:
    """Ask the AI to pick a job from the board; fall back to the first available
    if it names an off-board / already-taken job. Returns the chosen Job.

    Extracted so the multi-AI conductor can resolve contention with the same
    pick + fallback logic the single-AI path uses."""
    ctx = _campaign_context(campaign)
    _, job_parsed = _call_json(
        ai,
        ctx + "\n\n" + _job_prompt(crew, available_jobs, scout_state),
        "job_pick", logs, emit,
    )
    jobs_by_name = {j.name: j for j in available_jobs}
    name = job_parsed.get("job_name", "") if isinstance(job_parsed, dict) else ""
    if name not in jobs_by_name:
        log.warn(
            "job_pick_fallback",
            picked=name,
            available=[j.name for j in available_jobs],
        )
        name = available_jobs[0].name
    return jobs_by_name[name]


def run_one_job(
    strategy: str,
    ai: HeistAI,
    campaign: Campaign,
    *,
    rng: random.Random,
    emit: EmitFn = None,
    snapshot_fn: SnapshotFn = None,
    board: list | None = None,
    assigned_job: Any | None = None,
    slate_scores: dict[str, dict[str, int]] | None = None,
    scout_state: ScoutState | None = None,
) -> tuple[HeistState, dict[str, Any]] | None:
    """Run one campaign round. Returns (state, extras) or None if no jobs.

    The slate is ``board`` (the round's contested board) when provided, else the
    full ``JOBS`` pool (single-heist / legacy). When ``assigned_job`` is given
    (the conductor already resolved contention) the internal job-pick is skipped.
    ``slate_scores`` / ``scout_state`` may be supplied by the conductor so its
    board-stage scouting carries into the heist; otherwise they're computed here.
    """
    from heist.scenes import generate_scenes
    from heist.state import Crew

    available_jobs = list(board) if board is not None else list(JOBS)
    if not available_jobs and assigned_job is None:
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

    # Roll the round's hidden challenge scores for the board (the conductor may
    # supply a shared roll), then scout before committing. The picked job reuses
    # its rolled scores.
    if slate_scores is None:
        slate_scores = roll_slate_scores(available_jobs, rng)
    if scout_state is None:
        scout_state = _run_scout_turn(crew, available_jobs, slate_scores, ai, logs, emit)

    if assigned_job is not None:
        job = assigned_job
    else:
        job = pick_job_from_board(ai, crew, available_jobs, scout_state, campaign, logs, emit)

    if emit:
        from heist.serialize import job_to_dict

        emit({"type": "job_known", "job": job_to_dict(job)})

    hidden = _roll_hidden_depth(job, rng, emit)
    state = HeistState(
        crew=crew, job=job, hidden_depth=hidden,
        challenge_scores=dict(slate_scores.get(job.name, {})),
        scout_state=scout_state,
    )
    scenes = generate_scenes(job, hidden, rng=rng, challenge_scores=state.challenge_scores)

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
    scenes = generate_scenes(job, hidden, rng=rng, challenge_scores=state.challenge_scores)
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
        scenes = generate_scenes(job, hidden, rng=rng, challenge_scores=state.challenge_scores)
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
        scenes = generate_scenes(job, hidden, rng=rng, challenge_scores=state.challenge_scores)
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
        scenes = generate_scenes(
            state.job, state.hidden_depth, rng=rng, challenge_scores=state.challenge_scores,
        )
        _run_scene_loop(scenes, state, ai, logs, extras, emit, on_scene,
                        snapshot_fn, strategy, rng, start_idx=0)

    elif stage == STAGE_IN_SCENE:
        if emit:
            from heist.serialize import crew_to_dict, job_to_dict
            emit({"type": "crew_known", "crew": crew_to_dict(state.crew)})
            emit({"type": "job_known", "job": job_to_dict(state.job)})
        scenes = generate_scenes(
            state.job, state.hidden_depth, rng=rng, challenge_scores=state.challenge_scores,
        )
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
