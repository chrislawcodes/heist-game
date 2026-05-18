"""Pearl Sutton — Inside Man M, Muscle L, $400."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=9,
    name="Pearl Sutton",
    skills={"inside_man": S.MEDIUM, "muscle": S.LOW},
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
