"""Rook Ferreira — Safecracker H, $700."""
from heist.state import Character, SkillLevel as S

CHARACTER = Character(
    id=10,
    name="Rook Ferreira",
    skills={"safecracker": S.HIGH},
    floor_cost=700,
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
