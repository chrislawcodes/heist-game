"""Sasha Kuznetsova — Hacker M, $200."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=2,
    name="Sasha Kuznetsova",
    skills={"hacker": S.MEDIUM},
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
