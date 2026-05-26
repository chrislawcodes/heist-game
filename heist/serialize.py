"""Convert game dataclasses to JSON-serializable dicts.

Each ``*_to_dict`` has a matching ``*_from_dict`` so a serialized state can
be reconstructed byte-for-byte after a server restart (see ``heist.persist``).
The dict shape is the contract; if you add a field to a dataclass, update
both directions in the same change.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any, cast

from heist.content import JOBS_BY_NAME, ROSTER_BY_ID
from heist.state import (
    SKILLS,
    Campaign,
    ChallengeLevel,
    Character,
    Crew,
    HeistState,
    HiddenDepthElement,
    HiddenDepthRoll,
    Job,
    RoundResult,
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


def _skill_level_value(value: Any) -> int:
    if isinstance(value, SkillLevel):
        return int(value)
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, str):
        if value in SkillLevel.__members__:
            return int(SkillLevel[value])
        try:
            return int(value)
        except ValueError:
            return 0
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _primary_skill_key(skills: dict[str, Any] | None) -> str:
    skills = skills or {}
    best_key = SKILLS[0]
    best_rank = (-1, 0)
    for idx, key in enumerate(SKILLS):
        rank = (_skill_level_value(skills.get(key)), -idx)
        if rank > best_rank:
            best_rank = rank
            best_key = key
    return best_key


def _skill_level_name(value: Any) -> str:
    if isinstance(value, SkillLevel):
        return value.name
    if isinstance(value, str) and value in SkillLevel.__members__:
        return value
    try:
        return SkillLevel(int(value)).name
    except (TypeError, ValueError):
        return SkillLevel.NONE.name


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple, set)) else [value]
    out: list[int] = []
    for item in items:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


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
        "tier": job.tier,
        "challenge_scores": dict(job.challenge_scores),
        "scene_loot": dict(job.scene_loot),
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
        "category": s.category,
    }


def scene_result_to_dict(r: SceneResult) -> dict:
    return {
        "scene": scene_to_dict(r.scene),
        "assigned_member_ids": r.assigned_member_ids,
        "success": r.success,
        "narration": r.narration,
        "reasoning": r.reasoning,
        "decision": r.decision,
        "outcome": r.outcome,
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
        tier=d.get("tier", ""),
        challenge_scores={k: int(v) for k, v in d.get("challenge_scores", {}).items()},
        scene_loot={k: int(v) for k, v in d.get("scene_loot", {}).items()},
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
        category=d.get("category"),
    )


def scene_result_from_dict(d: dict) -> SceneResult:
    return SceneResult(
        scene=scene_from_dict(d["scene"]),
        assigned_member_ids=[int(i) for i in d.get("assigned_member_ids", [])],
        success=d.get("success"),
        narration=d.get("narration", ""),
        reasoning=d.get("reasoning", ""),
        decision=d.get("decision"),
        outcome=d.get("outcome"),
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
        caught_member_ids=[int(i) for i in d.get("caught_member_ids", [])],
        secured_take=int(d.get("secured_take", 0)),
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
        "caught_member_ids": list(state.caught_member_ids),
        "secured_take": state.secured_take,
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


def _round_result_to_dict(r: RoundResult) -> dict:
    return {
        "round_idx": r.round_idx,
        "job_name": r.job_name,
        "take": r.take,
        "aborted": r.aborted,
        "escape_success": r.escape_success,
        "heat": r.heat,
        "notoriety_before": r.notoriety_before,
        "notoriety_after": r.notoriety_after,
        "banked_after": r.banked_after,
        "caught_member_ids": list(r.caught_member_ids),
        "crew_ids": list(r.crew_ids),
    }


def _round_result_from_any(item: Any) -> RoundResult:
    if isinstance(item, RoundResult):
        return item
    if isinstance(item, dict):
        raw_escape = item.get("escape_success", item.get("escape"))
        if isinstance(raw_escape, str) and raw_escape in {"clean", "failed", "caught"}:
            raw_escape = raw_escape == "clean"
        return RoundResult(
            round_idx=_coerce_int(item.get("round_idx", item.get("round", 0))),
            job_name=str(item.get("job_name", item.get("job", "")) or ""),
            take=_coerce_int(item.get("take", 0)),
            aborted=bool(item.get("aborted", False)),
            escape_success=raw_escape,
            heat=_coerce_int(item.get("heat", 0)),
            notoriety_before=_coerce_int(item.get("notoriety_before", 0)),
            notoriety_after=_coerce_int(item.get("notoriety_after", 0)),
            banked_after=_coerce_int(item.get("banked_after", 0)),
            caught_member_ids=_coerce_int_list(item.get("caught_member_ids", [])),
            crew_ids=_coerce_int_list(item.get("crew_ids", [])),
        )
    raw_escape = getattr(item, "escape_success", getattr(item, "escape", None))
    if isinstance(raw_escape, str) and raw_escape in {"clean", "failed", "caught"}:
        raw_escape = raw_escape == "clean"
    return RoundResult(
        round_idx=_coerce_int(getattr(item, "round_idx", getattr(item, "round", 0))),
        job_name=str(getattr(item, "job_name", getattr(item, "job", "")) or ""),
        take=_coerce_int(getattr(item, "take", 0)),
        aborted=bool(getattr(item, "aborted", False)),
        escape_success=raw_escape,
        heat=_coerce_int(getattr(item, "heat", 0)),
        notoriety_before=_coerce_int(getattr(item, "notoriety_before", 0)),
        notoriety_after=_coerce_int(getattr(item, "notoriety_after", 0)),
        banked_after=_coerce_int(getattr(item, "banked_after", 0)),
        caught_member_ids=_coerce_int_list(getattr(item, "caught_member_ids", [])),
        crew_ids=_coerce_int_list(getattr(item, "crew_ids", [])),
    )


def campaign_to_dict(campaign: Campaign) -> dict:
    return {
        "game_id": getattr(campaign, "game_id", None),
        "rounds_total": campaign.rounds_total,
        "bankroll": campaign.bankroll,
        "banked_loot": campaign.banked_loot,
        "standing_crew": [character_to_dict(c) for c in campaign.standing_crew],
        "notoriety": campaign.notoriety,
        "attempted_job_names": sorted(campaign.attempted_job_names),
        "round_results": [_round_result_to_dict(r) for r in campaign.round_results],
        "between_round_log": [dict(entry) for entry in campaign.between_round_log],
    }


def campaign_from_dict(d: dict) -> Campaign:
    campaign = Campaign(
        rounds_total=int(d.get("rounds_total", d.get("total_rounds", 0))),
        bankroll=int(d.get("bankroll", 0)),
        banked_loot=int(d.get("banked_loot", 0)),
        standing_crew=[character_from_dict(c) for c in d.get("standing_crew", [])],
        notoriety=int(d.get("notoriety", 0)),
        attempted_job_names=set(d.get("attempted_job_names", [])),
        round_results=[_round_result_from_any(r) for r in d.get("round_results", [])],
        between_round_log=[dict(entry) for entry in d.get("between_round_log", [])],
    )
    game_id = d.get("game_id")
    if game_id is not None:
        cast(Any, campaign).game_id = game_id
    return campaign


def _state_value(entry: Any, key: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _normalize_skill_map(skills: Any) -> dict[str, Any]:
    if not isinstance(skills, dict):
        return {}
    return dict(skills)


def _crew_member_from_any(member: Any, roster_lookup: dict[int, Character]) -> dict:
    if isinstance(member, dict):
        out = dict(member)
        cid = out.get("char_id", out.get("id"))
        if cid is None:
            return out
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            return out
        canonical = roster_lookup.get(cid_int)
        if canonical is not None and not out.get("skills"):
            out["skills"] = {k: v.name for k, v in canonical.skills.items()}
        out["char_id"] = cid_int
        out["id"] = cid_int
        out.setdefault("name", canonical.name if canonical is not None else "")
        out.setdefault("captured", bool(out.get("captured", False)))
        out["skills"] = {
            k: _skill_level_name(v) for k, v in _normalize_skill_map(out.get("skills")).items()
        }
        out["primary"] = _primary_skill_key(out["skills"])
        return out

    cid = getattr(member, "id", None)
    if cid is None:
        return {}
    cid = int(cid)
    canonical = roster_lookup.get(cid, member if isinstance(member, Character) else None)
    skills = _normalize_skill_map(getattr(member, "skills", None))
    if not skills and canonical is not None:
        skills = dict(canonical.skills)
    skills_dict = {k: _skill_level_name(v) for k, v in skills.items()}
    name = getattr(member, "name", canonical.name if canonical is not None else "")
    return {
        "char_id": cid,
        "id": cid,
        "name": name,
        "skills": skills_dict,
        "primary": _primary_skill_key(skills_dict),
        "captured": bool(getattr(member, "captured", False)),
    }


def _escape_status_from_result(result: dict) -> str:
    escape = result.get("escape")
    if isinstance(escape, str) and escape in {"clean", "failed", "caught"}:
        return escape
    if result.get("caught") or result.get("captured") or result.get("caught_member_ids"):
        return "caught"
    if result.get("escape_success") is False:
        return "failed"
    return "clean"


def _coverage_from_crew(crew: list[dict]) -> dict[str, int]:
    out = {key: 0 for key in ("hack", "safe", "musc", "soc", "drive")}
    for member in crew:
        if member.get("captured"):
            continue
        skills = _normalize_skill_map(member.get("skills"))
        for key, api_key in (
            ("hack", "hacker"),
            ("safe", "safecracker"),
            ("musc", "muscle"),
            ("soc", "inside_man"),
            ("drive", "driver"),
        ):
            out[key] = max(out[key], _skill_level_value(skills.get(api_key)))
    return out


def campaign_state_to_dict(
    campaign: Campaign,
    game_states: Any,
    roster: list[Character],
    *,
    current_stage: str = "done",
    current_round_idx: int = 0,
    progress: dict | None = None,
) -> dict:
    roster_lookup = {c.id: c for c in roster}
    if isinstance(game_states, dict):
        entries = list(game_states.values())
    else:
        entries = list(game_states or [])

    standings_raw = []
    latest_reflections: dict[int, dict] = {}
    latest_reflections_by_name: dict[str, dict] = {}

    for idx, entry in enumerate(entries):
        ai_idx = int(_state_value(entry, "ai_idx", idx))
        ai_name = _state_value(entry, "ai_name", _state_value(entry, "name", f"AI {ai_idx + 1}"))
        ai_game_id = _state_value(entry, "ai_game_id", _state_value(entry, "game_id", None))
        round_game_ids: list[int | None] = list(
            _state_value(entry, "round_game_ids", []) or []
        )

        crew_raw = _state_value(entry, "crew")
        if crew_raw is None:
            crew_raw = _state_value(entry, "standing_crew", [])
        if isinstance(crew_raw, dict):
            crew_raw = crew_raw.get("members", crew_raw.get("crew", []))
        crew_members = [
            _crew_member_from_any(member, roster_lookup)
            for member in (crew_raw or [])
        ]

        captured_ids: set[int] = set()
        for cid in (
            _state_value(entry, "caught_member_ids", [])
            or _state_value(entry, "captured_member_ids", [])
        ):
            if cid is None:
                continue
            try:
                captured_ids.add(int(cid))
            except (TypeError, ValueError):
                continue
        for member in crew_members:
            cid = member.get("char_id")
            if cid in captured_ids:
                member["captured"] = True

        status = _state_value(entry, "status", None)
        if status not in {"done", "running", "waiting"}:
            if _state_value(entry, "running", False) or _state_value(entry, "in_progress", False):
                status = "running"
            elif _state_value(entry, "done", False) or _state_value(entry, "completed", False):
                status = "done"
            else:
                status = "waiting"

        round_results = _state_value(entry, "round_results", []) or []
        normalized_round_results = []
        for rr_idx, r in enumerate(round_results):
            if isinstance(r, dict):
                round_idx = _coerce_int(r.get("round_idx", rr_idx), rr_idx)
                job_name = r.get("job_name", r.get("job", ""))
                take = _coerce_int(r.get("take", 0), 0)
                escape_source = r
                heat = _coerce_int(r.get("heat", 0), 0)
                notoriety_before = _coerce_int(r.get("notoriety_before", 0), 0)
                notoriety_after = _coerce_int(r.get("notoriety_after", 0), 0)
                banked_after = _coerce_int(r.get("banked_after", 0), 0)
                caught_member_ids = _coerce_int_list(r.get("caught_member_ids", []))
                round_crew_ids = _coerce_int_list(r.get("crew_ids", []))
            else:
                round_idx = _coerce_int(getattr(r, "round_idx", rr_idx), rr_idx)
                job_name = getattr(r, "job_name", getattr(r, "job", ""))
                take = _coerce_int(getattr(r, "take", 0), 0)
                escape_source = {
                    "escape_success": getattr(r, "escape_success", None),
                    "caught_member_ids": getattr(r, "caught_member_ids", []),
                    "caught": getattr(r, "caught", False),
                    "captured": getattr(r, "captured", False),
                }
                heat = _coerce_int(getattr(r, "heat", 0), 0)
                notoriety_before = _coerce_int(getattr(r, "notoriety_before", 0), 0)
                notoriety_after = _coerce_int(getattr(r, "notoriety_after", 0), 0)
                banked_after = _coerce_int(getattr(r, "banked_after", 0), 0)
                caught_member_ids = _coerce_int_list(getattr(r, "caught_member_ids", []))
                round_crew_ids = _coerce_int_list(getattr(r, "crew_ids", []))
            aborted = bool(
                r.get("aborted", False) if isinstance(r, dict) else getattr(r, "aborted", False)
            )
            round_caught = set(caught_member_ids)
            round_crew = []
            for cid in round_crew_ids:
                char = roster_lookup.get(cid)
                if char is None:
                    continue
                member = _crew_member_from_any(char, roster_lookup)
                member["captured"] = cid in round_caught
                round_crew.append(member)
            normalized_round_results.append({
                "round_idx": round_idx,
                "job_name": str(job_name),
                "take": take,
                "aborted": aborted,
                "escape": _escape_status_from_result(escape_source),
                "heat": heat,
                "notoriety_before": notoriety_before,
                "notoriety_after": notoriety_after,
                "banked_after": banked_after,
                "caught_member_ids": caught_member_ids,
                "crew": round_crew,
                "game_id": round_game_ids[rr_idx] if rr_idx < len(round_game_ids) else None,
            })
        hiring_game_ids_list: list = _state_value(entry, "hiring_game_ids", []) or []
        for rr in normalized_round_results:
            ridx_raw = rr.get("round_idx")
            ridx_int = int(ridx_raw) if isinstance(ridx_raw, (int, float)) else None
            if ridx_int is not None and ridx_int < len(hiring_game_ids_list):
                rr["hiring_game_id"] = hiring_game_ids_list[ridx_int]
            else:
                rr.setdefault("hiring_game_id", None)
        last_round = None
        if round_results:
            last_raw = round_results[-1]
            if isinstance(last_raw, dict):
                last_round = {
                    "job": last_raw.get("job_name", last_raw.get("job")),
                    "take": int(last_raw.get("take", 0)),
                    "escape": _escape_status_from_result(last_raw),
                }
            else:
                last_round = {
                    "job": getattr(last_raw, "job_name", getattr(last_raw, "job", "")),
                    "take": int(getattr(last_raw, "take", 0)),
                    "escape": _escape_status_from_result(
                        {
                            "escape_success": getattr(last_raw, "escape_success", None),
                            "caught_member_ids": (
                                getattr(entry, "caught_member_ids", [])
                                if not isinstance(entry, dict)
                                else entry.get("caught_member_ids", [])
                            ),
                            "caught": getattr(last_raw, "caught", False),
                            "captured": getattr(last_raw, "captured", False),
                        }
                    ),
                }

        entry_brl: list[dict] = (
            list(entry.get("between_round_log", []))
            if isinstance(entry, dict)
            else list(getattr(entry, "between_round_log", []))
        )
        reflections_by_round = [
            {
                "round": brl_entry["round"],
                "learned": brl_entry.get("reflection", {}).get("learned", ""),
                "plan": brl_entry.get("reflection", {}).get("plan", ""),
            }
            for brl_entry in entry_brl
            if (
                brl_entry.get("stage") in ("reflection", None)
                and "reflection" in brl_entry
                and (
                    brl_entry.get("ai_idx") == ai_idx
                    or brl_entry.get("ai_name") == ai_name
                )
            )
        ]

        standings_raw.append({
            "ai_idx": ai_idx,
            "ai_name": ai_name,
            "ai_game_id": ai_game_id,
            "banked": int(_state_value(entry, "banked_loot", _state_value(entry, "banked", 0))),
            "notoriety": int(_state_value(entry, "notoriety", 0)),
            "last_round": last_round,
            "round_results": normalized_round_results,
            "crew": crew_members,
            "status": status,
            "reflections_by_round": reflections_by_round,
        })

        latest_reflection = _state_value(entry, "reflection", None)
        if latest_reflection:
            latest_reflections[ai_idx] = latest_reflection
            latest_reflections_by_name[str(ai_name)] = latest_reflection

    standings_raw.sort(key=lambda row: (-row["banked"], row["ai_idx"]))
    for rank, row in enumerate(standings_raw, start=1):
        row["rank"] = rank
        if row["last_round"] is None and campaign.round_results:
            # If the caller gave us only live standings data, fall back to the
            # campaign's most recent round result so the card still has a
            # useful summary.
            last = campaign.round_results[-1]
            row["last_round"] = {
                "job": last.job_name,
                "take": last.take,
                "escape": "clean" if last.escape_success else "failed",
            }
        reflection = (
            latest_reflections.get(row["ai_idx"])
            or latest_reflections_by_name.get(str(row["ai_name"]))
        )
        if reflection is None:
            # Search per-AI between_round_log in the standings entry
            ai_entry = next(
                (e for e in entries if int(_state_value(e, "ai_idx", -1)) == row["ai_idx"]),
                None,
            )
            ai_brl: list[dict] = (
                list(ai_entry.get("between_round_log", []))
                if isinstance(ai_entry, dict)
                else list(getattr(ai_entry, "between_round_log", []) if ai_entry else [])
            )
            matching = next(
                (
                    brl_e
                    for brl_e in reversed(ai_brl)
                    if (
                        brl_e.get("ai_idx") == row["ai_idx"]
                        or brl_e.get("ai_name") == row["ai_name"]
                    )
                ),
                None,
            )
            if matching is not None:
                reflection = matching.get("reflection")
        row["reflection"] = reflection

    round_indices = sorted({
        int(rr["round_idx"])
        for row in standings_raw
        for rr in row["round_results"]
        if rr.get("round_idx") is not None
    })
    round_results_by_ai: dict[int, dict[int, dict[str, Any]]] = {}
    for row in standings_raw:
        ai_idx = int(row["ai_idx"])
        round_results_by_ai[ai_idx] = cast(dict[int, dict[str, Any]], {})
        for rr in row["round_results"]:
            round_idx = int(rr["round_idx"])
            round_results_by_ai[ai_idx][round_idx] = rr

    have_banked_after = any(
        _coerce_int(rr.get("banked_after", 0), 0) > 0
        for row in standings_raw
        for rr in row["round_results"]
    )
    previous_rank_after_by_ai: dict[int, int] = {}
    for round_idx in round_indices:
        active_rows: list[tuple[int, int, dict[str, Any]]] = []
        for row in standings_raw:
            ai_idx = int(row["ai_idx"])
            ai_round_results = round_results_by_ai[ai_idx]
            round_result_entry = ai_round_results.get(round_idx)
            if round_result_entry is None:
                continue
            if have_banked_after:
                metric = _coerce_int(round_result_entry.get("banked_after", 0), 0)
            else:
                metric = _coerce_int(row.get("banked", 0), 0)
            active_rows.append((ai_idx, metric, round_result_entry))
        active_rows.sort(key=lambda item: (-item[1], item[0]))
        for rank_after, (ai_idx, _, round_result_entry) in enumerate(active_rows, start=1):
            prev_rank_after = previous_rank_after_by_ai.get(ai_idx)
            round_result_entry["rank_after"] = rank_after
            round_result_entry["rank_delta"] = (
                0 if prev_rank_after is None else prev_rank_after - rank_after
            )
            previous_rank_after_by_ai[ai_idx] = rank_after

    # Collect between_round_log from all per-AI entries (the shared campaign
    # object's between_round_log is always empty in multi-AI campaigns).
    all_brl: list[dict] = []
    for gs_entry in entries:
        gs_brl = (
            list(gs_entry.get("between_round_log", []))
            if isinstance(gs_entry, dict)
            else list(getattr(gs_entry, "between_round_log", []))
        )
        all_brl.extend(gs_brl)

    wire = []
    for entry in sorted(
        [e for e in all_brl if e.get("stage") in ("trash_talk", None)],
        key=lambda e: (int(e.get("round", 0)), int(e.get("ai_idx", 0))),
    ):
        trash = entry.get("trash_talk") or {}
        speaker_name = trash.get("speaker_name")
        speaker_char_id = trash.get("speaker_char_id")
        try:
            speaker_id = int(speaker_char_id) if speaker_char_id is not None else None
        except (TypeError, ValueError):
            speaker_id = None
        if speaker_id is not None and speaker_id in roster_lookup:
            speaker_name = roster_lookup[speaker_id].name
        speaker_member = None
        if speaker_id is not None and speaker_id in roster_lookup:
            speaker_member = _crew_member_from_any(roster_lookup[speaker_id], roster_lookup)
        wire.append({
            "round": int(entry.get("round", 0)),
            "ai_name": entry.get("ai_name"),
            "speaker_char_id": speaker_char_id,
            "speaker_name": speaker_name,
            "target_ai_name": trash.get("target_ai_name"),
            "text": trash.get("text", ""),
            "speaker": speaker_member,
        })

    return {
        "game_id": getattr(campaign, "game_id", None),
        "round": campaign.current_round,
        "total_rounds": campaign.total_rounds,
        "standings": standings_raw,
        "wire": wire,
        "current_stage": current_stage,
        "current_round_idx": current_round_idx,
        "progress": progress,
    }
