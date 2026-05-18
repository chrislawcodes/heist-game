"""Marcus 'Prodigy' Renault — Hacker H, Driver L, $1,100."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=1,
    name='Marcus "Prodigy" Renault',
    skills={"hacker": S.HIGH, "driver": S.LOW},
    floor_cost=1100,
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
