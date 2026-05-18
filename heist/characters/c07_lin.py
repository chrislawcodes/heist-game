"""Lin 'Closer' Park — Inside Man H, Safecracker L, $1,100."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=7,
    name='Lin "Closer" Park',
    skills={"inside_man": S.HIGH, "safecracker": S.LOW},
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
