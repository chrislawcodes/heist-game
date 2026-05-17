"""Render a completed HeistState + extras into a markdown report."""

from heist.content import ROSTER_BY_ID
from heist.state import HeistState, SceneResult


def render_markdown(state: HeistState, extras: dict) -> str:
    out: list[str] = []
    out.append(f"# Heist Report: {state.job.name}")
    out.append("")
    out.append("## Strategy")
    out.append("")
    out.append(_blockquote(extras.get("strategy", "")))
    out.append("")

    out.append("## Casting")
    out.append("")
    out.append(extras.get("casting_summary", "_(no casting summary)_"))
    out.append("")
    out.append("### Crew")
    for c in state.crew.members:
        skills = ", ".join(f"{s} {lvl.name}" for s, lvl in c.skills.items())
        out.append(f"- **{c.name}** — {skills} — ${c.floor_cost}")
    out.append(f"\n_Total spend: ${state.crew.total_cost:,} / $2,000_")
    out.append("")
    out.append(f"### Job selected: {state.job.name}")
    out.append("")

    out.append("## Heist")
    out.append("")
    for result in extras.get("scene_narrations", []):
        out.extend(_render_scene(result))
        out.append("")

    out.append("## Epilogue")
    out.append("")
    out.append(extras.get("epilogue", "_(no epilogue)_"))
    out.append("")

    out.append("## Outcome")
    out.append("")
    out.append(f"- **Take:** ${state.final_take:,}")
    out.append(f"- **Aborted:** {state.aborted}")
    if state.escape_success is True:
        escape_status = "succeeded"
    elif state.escape_success is False:
        escape_status = "failed"
    else:
        escape_status = "n/a"
    out.append(f"- **Escape:** {escape_status}")
    if state.bonus_pursued:
        out.append(
            f"- **Bonus pursuit:** "
            f"{'succeeded' if state.bonus_succeeded else 'failed'} "
            f"(+${state.bonus_amount:,})"
            if state.bonus_succeeded
            else "- **Bonus pursuit:** failed"
        )
    out.append(f"- **Hidden depth:** {state.hidden_depth.element.description}")
    out.append(
        f"- **Reward roll:** {state.hidden_depth.reward_label} "
        f"(${state.hidden_depth.reward_amount:,})"
    )

    return "\n".join(out) + "\n"


def _render_scene(result: SceneResult) -> list[str]:
    out: list[str] = []
    out.append(f"### Scene {result.scene.number} — {result.scene.title}")
    out.append("")
    assigned_names = [
        ROSTER_BY_ID[i].name for i in result.assigned_member_ids if i in ROSTER_BY_ID
    ]
    meta_bits = []
    if assigned_names:
        meta_bits.append(f"**Personnel:** {', '.join(assigned_names)}")
    if result.reasoning:
        meta_bits.append(f"**Reasoning:** {result.reasoning}")
    if result.success is not None:
        meta_bits.append(
            f"**Mechanical outcome:** {'success' if result.success else 'failure'}"
        )
    if result.decision is not None:
        meta_bits.append(
            f"**Decision:** "
            f"{'pursued' if result.decision['pursue'] else 'declined'} — "
            f"{result.decision['reasoning']}"
        )
    if meta_bits:
        out.append("_" + " · ".join(meta_bits) + "_")
        out.append("")
    out.append(result.narration)
    return out


def _blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines() or [text])
