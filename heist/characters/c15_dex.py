"""Dex Owusu — Driver L, Muscle L, $200."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=15,
    name="Dex Owusu",
    skills={"driver": S.LOW, "muscle": S.LOW},
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
