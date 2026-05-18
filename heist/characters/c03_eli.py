"""Eli 'Owl' Park — Hacker L, Inside Man L, $200."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=3,
    name='Eli "Owl" Park',
    skills={"hacker": S.LOW, "inside_man": S.LOW},
    floor_cost=200,
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
