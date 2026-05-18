"""Big Mike Donato — Muscle L, Driver L, $200."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=6,
    name="Big Mike Donato",
    skills={"muscle": S.LOW, "driver": S.LOW},
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
