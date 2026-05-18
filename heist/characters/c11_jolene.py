"""Jolene 'Jo' Hayes — Safecracker M, Hacker L, $400."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=11,
    name='Jolene "Jo" Hayes',
    skills={"safecracker": S.MEDIUM, "hacker": S.LOW},
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
