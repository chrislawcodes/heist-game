"""Margot Vinter — Driver M, Inside Man L, $400."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=14,
    name="Margot Vinter",
    skills={"driver": S.MEDIUM, "inside_man": S.LOW},
    floor_cost=400,
    # ── Profile (see heist/characters/_TEMPLATE.md for rubric + examples) ──
    backstory="",
    voice="",
    motivation="",
    quirk="",
    crew_dynamic="",
    weakness="",
    look="",
    signature_line="",
)
