"""Carla Reyes — Muscle M, Driver L, $400."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=5,
    name="Carla Reyes",
    skills={"muscle": S.MEDIUM, "driver": S.LOW},
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
