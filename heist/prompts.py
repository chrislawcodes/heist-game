"""Prompt-string builders for the heist runner. Pure text — no AI calls, no state mutation."""

from __future__ import annotations

from heist.content import BANKROLL, JOBS, ROSTER
from heist.state import Campaign, Character, Crew, HeistState, Scene


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
    is a walk into a wall. Plan around them or don't take the job.

How a scene resolves — your crew's effective skill vs the challenge level:

  • Beat the level (skill higher than the challenge): CLEAN — you pass, no heat.
  • Match it exactly: SQUEAK — you pass, but heat +1.
  • Fall one level short: FAIL — the scene fails, heat +1.
  • Fall two or more levels short: CAUGHT — the scene fails AND a crew member
    is taken, heat +1.
  (A challenge rated None always comes up clean.)

Heat and the getaway:

  • Heat is your alarm level — it rises by 1 for every scene that isn't clean
    (squeak, fail, or caught).
  • The escape difficulty equals the job's escape rating plus your total heat.
    Your best Driver must be at or above that to get out (no Driver counts as
    Low). If the escape fails, one more crew member is caught.

The take:

  • You only secure loot from scenes you pass (clean or squeak). You KEEP that
    take only if at least one crew member escapes uncaught — if the whole crew
    is taken, you leave with nothing.
  • You can abort at any scene: you take the escape immediately with whatever
    you've secured so far.

Across a campaign (multiple rounds):

  • Heat carries forward as Notoriety: after each round Notoriety = previous
    Notoriety + that round's heat − 1 (it cools by 1 per round, never below 0).
  • If Notoriety reaches 9, the law raids you and the campaign ends early.
  • Crew caught on a failed escape are gone for the rest of the campaign."""


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
