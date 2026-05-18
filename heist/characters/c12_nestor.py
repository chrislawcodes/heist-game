"""Nestor Bly — Safecracker L, Hacker L, $200."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=12,
    name="Nestor Bly",
    skills={"safecracker": S.LOW, "hacker": S.LOW},
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
