"""Campaign loop: multi-round heist saga."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from heist.ai import HeistAI
from heist.board import build_board
from heist.content import BANKROLL, JOBS, JOBS_BY_NAME, ROSTER_BY_ID
from heist.logs import log
from heist.prompts import _summary_prompt
from heist.runner import (
    EmitFn,
    TurnLog,
    _call,
    _call_json,
    _draft_crew,
    run_one_job,
)
from heist.state import SKILLS, Campaign, Character, HeistState, RoundResult, SkillLevel


def _state_value(entry: Any, key: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _skill_key_value(level: Any) -> int:
    if isinstance(level, SkillLevel):
        return int(level)
    if isinstance(level, int):
        return level
    if isinstance(level, str) and level in SkillLevel.__members__:
        return int(SkillLevel[level])
    return 0


def _primary_skill_key(char: Character) -> str:
    best_key = SKILLS[0]
    best_rank = (-1, 0)
    for idx, key in enumerate(SKILLS):
        rank = (_skill_key_value(char.skills.get(key, SkillLevel.NONE)), -idx)
        if rank > best_rank:
            best_rank = rank
            best_key = key
    return best_key


def _active_crew_from_entry(entry: Any, roster_lookup: dict[int, Character]) -> list[Character]:
    crew_raw = _state_value(entry, "crew")
    if crew_raw is None:
        crew_raw = _state_value(entry, "standing_crew", [])
    if isinstance(crew_raw, dict):
        crew_raw = crew_raw.get("members", crew_raw.get("crew", []))
    captured_ids: set[int] = set()
    for cid in (
        _state_value(entry, "caught_member_ids", [])
        or _state_value(entry, "captured_member_ids", [])
    ):
        try:
            captured_ids.add(int(cid))
        except (TypeError, ValueError):
            continue

    crew: list[Character] = []
    for member in crew_raw or []:
        if isinstance(member, Character):
            char = member
        elif isinstance(member, dict):
            raw_cid = member.get("id", member.get("char_id"))
            if raw_cid is None:
                char = None
            else:
                try:
                    cid = int(raw_cid)
                except (TypeError, ValueError):
                    char = None
                else:
                    char = roster_lookup.get(cid) or ROSTER_BY_ID.get(cid)
        else:
            try:
                cid = int(member)
            except (TypeError, ValueError):
                char = None
            else:
                char = roster_lookup.get(cid) or ROSTER_BY_ID.get(cid)
        if char is None:
            continue
        if char.id in captured_ids:
            continue
        crew.append(char)
    return crew


def settle_round(
    campaign: Campaign,
    state: HeistState,
    *,
    board: list[str] | None = None,
    contested: bool = False,
) -> bool:
    """Update campaign in-place after one round. Returns True = end campaign."""
    scouted = [
        {"job": job, "category": cat, "score": score}
        for job, cats in state.scout_state.exact_scores.items()
        for cat, score in cats.items()
    ]
    return _settle_round_core(
        campaign,
        final_take=state.final_take,
        heat=state.heat,
        caught_member_ids=list(state.caught_member_ids),
        job_name=state.job.name,
        aborted=state.aborted,
        escape_success=state.escape_success,
        scouted=scouted,
        board=board,
        contested=contested,
    )


def _settle_round_core(
    campaign: Campaign,
    *,
    final_take: int,
    heat: int,
    caught_member_ids: list[int],
    job_name: str,
    aborted: bool,
    escape_success: bool | None,
    scouted: list[dict] | None = None,
    board: list[str] | None = None,
    contested: bool = False,
) -> bool:
    """Bank one round's outcome from primitive fields — no ``HeistState`` needed.

    Shared by ``settle_round`` (live play) and by campaign resume, which settles
    from a persisted ``pending_heist`` checkpoint without re-running the heist.
    Returns True if the campaign should end (crew wiped).
    """
    campaign.banked_loot += final_take
    # CONTESTED BOARD — the attempted job is consumed globally (never re-offered).
    campaign.consumed_jobs.add(job_name)
    crew_ids_snapshot = [c.id for c in campaign.standing_crew]

    # Remove only the captured members from standing crew.
    # A failed escape catches exactly one member; the rest escape with the loot.
    # Crew caught during scene challenges are also lost here.
    if caught_member_ids:
        caught_set = set(caught_member_ids)
        campaign.standing_crew = [
            c for c in campaign.standing_crew if c.id not in caught_set
        ]
        log.info(
            "crew_captured",
            captured_ids=list(caught_set),
            remaining=len(campaign.standing_crew),
        )

    campaign.round_results.append(RoundResult(
        round_idx=campaign.round_idx,
        job_name=job_name,
        take=final_take,
        aborted=aborted,
        escape_success=escape_success,
        heat=heat,
        banked_after=campaign.banked_loot,
        caught_member_ids=list(caught_member_ids),
        crew_ids=crew_ids_snapshot,
        scouted=list(scouted or []),
        board=list(board or []),
        contested=contested,
    ))

    crew_wiped = len(campaign.standing_crew) == 0
    if crew_wiped:
        log.info("campaign_end_crew_wiped")
    return crew_wiped


def _build_standings(
    ai_idx: int,
    ai_name: str,
    entries: list[Any],
) -> tuple[list[dict], int, list[dict]]:
    """Build sorted standings, self_rank, and rivals for a given AI."""
    standings = []
    for idx, entry in enumerate(entries):
        other_ai_idx = int(_state_value(entry, "ai_idx", idx))
        other_name = _state_value(
            entry,
            "ai_name",
            _state_value(entry, "name", f"AI {other_ai_idx + 1}"),
        )
        other_banked = int(
            _state_value(entry, "banked_loot", _state_value(entry, "banked", 0))
        )
        other_crew = _active_crew_from_entry(entry, ROSTER_BY_ID)
        standings.append({
            "ai_idx": other_ai_idx,
            "ai_name": other_name,
            "banked": other_banked,
            "crew_count": len(other_crew),
        })
    standings.sort(key=lambda row: (-row["banked"], row["ai_idx"]))
    rank_by_ai = {row["ai_idx"]: rank for rank, row in enumerate(standings, start=1)}
    self_rank = rank_by_ai.get(ai_idx, len(standings) or 1)
    rivals = [row for row in standings if row["ai_idx"] != ai_idx]
    return standings, self_rank, rivals


def _opening_wire_call(
    campaign: Campaign,
    ai_idx: int,
    round_idx: int,
    ai: HeistAI,
    game_states: list[Any],
    logs: list[TurnLog],
    emit: EmitFn,
) -> dict[str, Any]:
    """Generate the round-opening Wire entry for one AI.

    round_idx == 0 → "hopes" variant: no prior-round data; AI talks about
    what they plan to do and their read on rivals.
    round_idx > 0 → trash talk: references the result of round_idx - 1.

    Stores one entry in campaign.between_round_log with stage="trash_talk".
    Returns the stored entry dict.
    """
    entries = list(game_states or [])

    own_entry: Any = {}
    for e in entries:
        if int(_state_value(e, "ai_idx", -1)) == ai_idx:
            own_entry = e
            break

    ai_name = _state_value(
        own_entry,
        "ai_name",
        _state_value(own_entry, "name", f"AI {ai_idx + 1}"),
    )

    active_crew = _active_crew_from_entry(own_entry, ROSTER_BY_ID)
    active_ids = {m.id for m in active_crew}

    def _persona_block(member: Any) -> str:
        # Give the AI enough of each crew member's personality to pick a speaker
        # and write the trash talk in their distinct voice.
        bits: list[str] = [
            f"  - id {member.id} | {member.name} ({_primary_skill_key(member)})"
        ]
        if getattr(member, "voice", ""):
            bits.append(f"    voice: {member.voice}")
        if getattr(member, "motivation", ""):
            bits.append(f"    motivation: {member.motivation}")
        if getattr(member, "quirk", ""):
            bits.append(f"    quirk: {member.quirk}")
        if getattr(member, "signature_line", ""):
            bits.append(f'    signature line: "{member.signature_line}"')
        return "\n".join(bits)

    crew_personas = (
        "\n".join(_persona_block(m) for m in active_crew) or "  - none"
    )

    _, self_rank, rivals = _build_standings(ai_idx, ai_name, entries)

    if round_idx == 0:
        # Hopes variant
        banked = int(_state_value(own_entry, "banked_loot", _state_value(own_entry, "banked", 0)))
        prompt_lines = [
            f"You are the Heist AI for {ai_name}.",
            "This is the opening round. There are no past results yet.",
            "",
            "Your crew (pick ONE as the speaker, by id):",
            crew_personas,
            f"Your starting bankroll: ${banked:,}",
            "",
            "Rivals (rival crews/teams you can call out by name):",
        ]
        if rivals:
            for rival in rivals:
                prompt_lines.append(
                    f"- {rival['ai_name']} | crew {rival['crew_count']}"
                )
        else:
            prompt_lines.append("- None")
        prompt_lines.extend([
            "",
            f"You are rank {self_rank} (all crews are even — rank by position).",
            "Pick ONE of your own crew members as the speaker (use their id).",
            "Write the opening statement IN THAT SPEAKER'S VOICE — let their",
            "personality, motivation, quirk, and signature style come through.",
            "Address ONE named rival crew directly, by name, inside the line",
            'itself (e.g. "You Wreckers think...") — do not just mention them.',
            "Reply with ONLY JSON:",
            "{",
            '  "speaker_char_id": 4,',
            '  "target_ai_name": "Ghost",',
            '  "text": "4-6 sentences, first person, in the speaker\'s distinct voice — '
            'what you\'re going in for and what you think of the named rival. Stay in character."',
            "}",
        ])
    else:
        # Trash talk variant
        banked = int(_state_value(own_entry, "banked_loot", _state_value(own_entry, "banked", 0)))
        job_name = _state_value(
            own_entry,
            "job_name",
            _state_value(own_entry, "job", "Unknown job"),
        )
        take = int(_state_value(own_entry, "take", 0))
        escape_success = _state_value(own_entry, "escape_success", None)
        caught_ids_raw = (
            _state_value(own_entry, "caught_member_ids", [])
            or _state_value(own_entry, "captured_member_ids", [])
        )
        caught_names: list[str] = []
        for cid in caught_ids_raw:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            char = ROSTER_BY_ID.get(cid_int)
            if char is not None:
                caught_names.append(char.name)
        if caught_ids_raw:
            escape_text = "caught"
        elif escape_success is True:
            escape_text = "clean"
        elif escape_success is False:
            escape_text = "failed"
        else:
            escape_text = "unknown"

        standings, self_rank, rivals = _build_standings(ai_idx, ai_name, entries)
        rank_by_ai = {row["ai_idx"]: rank for rank, row in enumerate(standings, start=1)}

        prompt_lines = [
            f"You are the Heist AI for {ai_name}.",
            f"Round {round_idx} just ended.",
            "",
            "This round:",
            f"- Job: {job_name}",
            f"- Take: ${take:,}",
            f"- Escape: {escape_text}",
            f"- Caught crew: {', '.join(caught_names) if caught_names else 'none'}",
            "",
            "Your campaign totals:",
            f"- Banked loot: ${banked:,}",
            "",
            "Your crew (pick ONE as the speaker, by id):",
            crew_personas,
            "",
            "Rivals (rival crews/teams you can call out by name):",
        ]
        if rivals:
            for rival in rivals:
                prompt_lines.append(
                    f"- Rank {rank_by_ai[rival['ai_idx']]}: {rival['ai_name']} | "
                    f"banked ${rival['banked']:,} | crew {rival['crew_count']}"
                )
        else:
            prompt_lines.append("- None")
        prompt_lines.extend([
            "",
            f"You are rank {self_rank}.",
            "Pick ONE of your own active crew members as the speaker (use their id).",
            "Write the trash talk IN THAT SPEAKER'S VOICE — let their personality,",
            "motivation, quirk, and signature style come through, and react to how",
            "this round actually went (the take, the escape, anyone caught).",
            "Address ONE named rival crew directly, by name, inside the line itself",
            '(e.g. "You Wreckers got lucky...") — do not just mention them.',
            "Reply with ONLY JSON:",
            "{",
            '  "speaker_char_id": 4,',
            '  "target_ai_name": "Ghost",',
            '  "text": "4-6 sentences, first person, in the speaker\'s distinct voice — '
            'react to this round and jab the named rival. Stay in character."',
            "}",
        ])

    prompt = "\n".join(prompt_lines)

    if ai is None:
        log.warn("opening_wire_missing_ai", ai_idx=ai_idx, round=round_idx)
        parsed: dict[str, Any] = {}
    else:
        try:
            _, parsed = _call_json(
                ai,
                prompt,
                f"opening_wire_{round_idx}_ai{ai_idx}",
                logs,
                emit,
            )
        except Exception as exc:
            log.warn(
                "opening_wire_call_failed",
                ai_idx=ai_idx,
                round=round_idx,
                error=str(exc),
            )
            parsed = {}

    speaker_id: int | None = active_crew[0].id if active_crew else None
    requested_speaker_id = parsed.get("speaker_char_id")
    if requested_speaker_id is not None:
        try:
            requested_speaker_id = int(requested_speaker_id)
        except (TypeError, ValueError):
            log.warn(
                "opening_wire_bad_speaker_id",
                ai_idx=ai_idx,
                round=round_idx,
                value=parsed.get("speaker_char_id"),
            )
        else:
            if requested_speaker_id in active_ids:
                speaker_id = requested_speaker_id
            elif active_crew:
                log.warn(
                    "opening_wire_speaker_fallback",
                    ai_idx=ai_idx,
                    round=round_idx,
                    requested=requested_speaker_id,
                )
                speaker_id = active_crew[0].id
    elif active_crew:
        speaker_id = active_crew[0].id

    _, self_rank, rivals = _build_standings(ai_idx, ai_name, entries)
    rank_by_ai_final: dict[int, int] = {}
    standings_final, _, _ = _build_standings(ai_idx, ai_name, entries)
    for rank, row in enumerate(standings_final, start=1):
        rank_by_ai_final[row["ai_idx"]] = rank

    target_name = parsed.get("target_ai_name")
    target_rival = next((r for r in rivals if r["ai_name"] == target_name), None)
    if target_rival is None and rivals:
        target_rival = min(
            rivals,
            key=lambda r: (
                abs(rank_by_ai_final.get(r["ai_idx"], len(rivals)) - self_rank),
                -r["banked"],
                r["ai_idx"],
            ),
        )
        if target_name is not None:
            log.warn(
                "opening_wire_target_fallback",
                ai_idx=ai_idx,
                round=round_idx,
                requested=target_name,
                fallback=target_rival["ai_name"],
            )
    target_name = target_rival["ai_name"] if target_rival is not None else target_name

    text = (parsed.get("text", "").strip() or "We're ready.")[:900]

    entry: dict[str, Any] = {
        "round": round_idx,
        "stage": "trash_talk",
        "ai_idx": ai_idx,
        "ai_name": ai_name,
        "trash_talk": {
            "speaker_char_id": speaker_id,
            "target_ai_name": target_name,
            "text": text,
        },
    }
    campaign.between_round_log.append(entry)
    return entry


def _reflection_call(
    campaign: Campaign,
    ai_idx: int,
    round_idx: int,
    ai: HeistAI,
    game_states: list[Any],
    logs: list[TurnLog],
    emit: EmitFn,
) -> dict[str, Any]:
    """Generate the round-end reflection for one AI.

    Stores one entry in campaign.between_round_log with stage="reflection".
    Returns the stored entry dict.
    """
    entries = list(game_states or [])

    own_entry: Any = {}
    for e in entries:
        if int(_state_value(e, "ai_idx", -1)) == ai_idx:
            own_entry = e
            break

    ai_name = _state_value(
        own_entry,
        "ai_name",
        _state_value(own_entry, "name", f"AI {ai_idx + 1}"),
    )

    active_crew = _active_crew_from_entry(own_entry, ROSTER_BY_ID)
    active_crew_lines = (
        ", ".join(f"{m.name} ({_primary_skill_key(m)})" for m in active_crew)
        or "none"
    )

    banked = int(_state_value(own_entry, "banked_loot", _state_value(own_entry, "banked", 0)))
    job_name = _state_value(
        own_entry,
        "job_name",
        _state_value(own_entry, "job", "Unknown job"),
    )
    take = int(_state_value(own_entry, "take", 0))
    escape_success = _state_value(own_entry, "escape_success", None)
    caught_ids_raw = (
        _state_value(own_entry, "caught_member_ids", [])
        or _state_value(own_entry, "captured_member_ids", [])
    )
    caught_names: list[str] = []
    for cid in caught_ids_raw:
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            continue
        char = ROSTER_BY_ID.get(cid_int)
        if char is not None:
            caught_names.append(char.name)
    if caught_ids_raw:
        escape_text = "caught"
    elif escape_success is True:
        escape_text = "clean"
    elif escape_success is False:
        escape_text = "failed"
    else:
        escape_text = "unknown"

    standings, self_rank, rivals = _build_standings(ai_idx, ai_name, entries)
    rank_by_ai = {row["ai_idx"]: rank for rank, row in enumerate(standings, start=1)}

    prompt_lines = [
        f"You are the Heist AI for {ai_name}.",
        f"Round {round_idx + 1} just completed.",
        "",
        "This round:",
        f"- Job: {job_name}",
        f"- Take: ${take:,}",
        f"- Escape: {escape_text}",
        f"- Caught crew: {', '.join(caught_names) if caught_names else 'none'}",
        "",
        "Campaign totals after this round:",
        f"- Banked loot: ${banked:,}",
        f"- Active crew: {active_crew_lines}",
        "",
        "Rivals:",
    ]
    if rivals:
        for rival in rivals:
            prompt_lines.append(
                f"- Rank {rank_by_ai[rival['ai_idx']]}: {rival['ai_name']} | "
                f"banked ${rival['banked']:,}"
            )
    else:
        prompt_lines.append("- None")
    prompt_lines.extend([
        "",
        "Reply with ONLY JSON:",
        "{",
        '  "learned": "one or two sentences about what this round taught",',
        '  "plan": "one or two sentences about next round strategy"',
        "}",
    ])
    prompt = "\n".join(prompt_lines)

    if ai is None:
        log.warn("reflection_missing_ai", ai_idx=ai_idx, round=round_idx)
        parsed: dict[str, Any] = {}
    else:
        try:
            _, parsed = _call_json(
                ai,
                prompt,
                f"reflection_{round_idx}_ai{ai_idx}",
                logs,
                emit,
            )
        except Exception as exc:
            log.warn(
                "reflection_call_failed",
                ai_idx=ai_idx,
                round=round_idx,
                error=str(exc),
            )
            parsed = {}

    learned = (parsed.get("learned", "").strip()
               or "We learned more about the room and the people in it.")
    plan = (parsed.get("plan", "").strip()
            or "Stay disciplined and hit the next round cleaner.")

    entry: dict[str, Any] = {
        "round": round_idx,
        "stage": "reflection",
        "ai_idx": ai_idx,
        "ai_name": ai_name,
        "reflection": {
            "learned": learned,
            "plan": plan,
        },
    }
    campaign.between_round_log.append(entry)
    return entry


OnRoundFn = Callable[[Campaign, HeistState, dict[str, Any]], None] | None


def run_campaign(
    strategy: str,
    ai: HeistAI,
    *,
    rounds: int = 10,
    num_ais: int = 1,
    rng: random.Random | None = None,
    on_round: OnRoundFn = None,
    before_round: Callable[[int], None] | None = None,
    emit: EmitFn = None,
) -> tuple[Campaign, list[dict[str, Any]]]:
    """Draft once, then loop run_one_job up to `rounds` times."""
    rng = rng or random.Random()
    logs: list[TurnLog] = []

    draft_extras: dict[str, Any] = {}
    crew = _draft_crew(strategy, ai, logs, extras=draft_extras, emit=emit)
    summary_turn = _call(ai, _summary_prompt(), "casting_summary", logs, emit)
    casting_summary = summary_turn.text

    campaign = Campaign(
        rounds_total=rounds,
        bankroll=BANKROLL - crew.total_cost,
        banked_loot=0,
        standing_crew=list(crew.members),
        round_results=[],
        num_ais=num_ais,
    )
    round_extras_list: list[dict[str, Any]] = []

    for _n in range(rounds):
        if not campaign.standing_crew:
            log.info("campaign_loop_no_crew", round=_n)
            break
        if before_round is not None:
            before_round(campaign.round_idx)
        # Build this round's board (subset of the pool minus globally-consumed
        # jobs); the AI sees only the board. Seeded per round for determinism.
        board_names = build_board(
            JOBS, campaign.consumed_jobs, campaign.round_idx, rounds,
            campaign.banked_loot, trailing_bankroll=campaign.banked_loot,
            rng=random.Random(1000 + campaign.round_idx),
        )
        if not board_names:
            log.info("campaign_loop_jobs_exhausted", round=_n)
            break
        board_objs = [JOBS_BY_NAME[n] for n in board_names]
        result = run_one_job(strategy, ai, campaign, rng=rng, emit=emit, board=board_objs)
        if result is None:
            log.info("campaign_loop_jobs_exhausted", round=_n)
            break
        state, extras = result
        extras["casting_summary"] = casting_summary
        round_extras_list.append(extras)
        ended = settle_round(campaign, state, board=board_names)
        if on_round:
            on_round(campaign, state, extras)
        if ended:
            break

    return campaign, round_extras_list
