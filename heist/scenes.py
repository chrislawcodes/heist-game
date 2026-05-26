"""Generate the scene list for a heist from job profile + hidden depth roll.

Rules (documented in README):
- Scene 1 is always "setup".
- Med/Hard challenges from the job's profile become one challenge scene each,
  in canonical heist order: social, electronic, physical, confrontation.
- Hidden depth elements with "modifies" effects apply to the matching scene
  (no extra scene). With "adds" effects: a new scene is inserted.
- Bonus-with-cost elements become a decision-point scene before transition.
- Penultimate scene = "transition" (to exit).
- Final scene = "escape".
The runner now grades each scene outcome instead of using a binary pass/fail
cascade.
"""

import random

from heist.mechanics import roll_one_score, score_to_bucket
from heist.state import (
    CHALLENGE_TO_SKILL,
    ChallengeLevel,
    HiddenDepthElement,
    HiddenDepthRoll,
    Job,
    Scene,
)

CANONICAL_ORDER = ("social", "electronic", "physical", "confrontation")


def _apply_modifications(
    profile: dict[str, ChallengeLevel], hidden: HiddenDepthRoll
) -> tuple[
    dict[str, ChallengeLevel],
    list[tuple[str, ChallengeLevel]],
    HiddenDepthElement | None,
]:
    """Returns (modified_profile, added_challenges, bonus_element_or_none)."""
    modified = dict(profile)
    added: list[tuple[str, ChallengeLevel]] = []
    bonus: HiddenDepthElement | None = None
    effect = hidden.element.effect

    for chal, lvl in effect.get("modifies", []):
        modified[chal] = lvl
    for chal, lvl in effect.get("adds", []):
        added.append((chal, lvl))
    if "bonus_amount_range" in effect:
        bonus = hidden.element

    return modified, added, bonus


def generate_scenes(
    job: Job,
    hidden: HiddenDepthRoll,
    *,
    rng: random.Random | None = None,
    challenge_scores: dict[str, int] | None = None,
) -> list[Scene]:
    """Build the scene list, stamping each challenge scene's true 1-10 score.

    `challenge_scores` (if given) is the per-round defense map — it may be
    pre-rolled by scouting; it is filled in place for any category not yet rolled
    or whose bucket changed under hidden depth, so it ends as the round's truth.
    """
    rng = rng or random.Random()
    challenge_scores = challenge_scores if challenge_scores is not None else {}
    profile, added, bonus_element = _apply_modifications(job.profile, hidden)

    def _score_for(category: str, level: ChallengeLevel) -> int:
        sc = challenge_scores.get(category)
        if sc is None or int(score_to_bucket(sc)) != int(level):
            sc = roll_one_score(level, job.tier, rng)
            challenge_scores[category] = sc
        return sc

    scenes: list[Scene] = []
    n = 1

    scenes.append(
        Scene(
            number=n, type="setup", title="Setup & approach",
            challenge_skill=None, challenge_level=None, is_core=False,
            context=f"Job: {job.name}. {job.flavor}",
        )
    )
    n += 1

    el = hidden.element
    modifies_categories = {c for c, _ in el.effect.get("modifies", [])}

    for category in CANONICAL_ORDER:
        level = profile.get(category, ChallengeLevel.NONE)
        if level < ChallengeLevel.MEDIUM:
            continue
        is_core = level == ChallengeLevel.HARD
        ctx = (
            f"Hidden depth in play: {el.description}"
            if category in modifies_categories
            else ""
        )
        scenes.append(
            Scene(
                number=n, type="challenge",
                title=f"Challenge — {category}",
                challenge_skill=CHALLENGE_TO_SKILL[category],
                challenge_level=level, is_core=is_core, context=ctx,
                category=category,
                challenge_score=_score_for(category, level),
            )
        )
        n += 1

    for cat, lvl in added:
        is_core = lvl == ChallengeLevel.HARD
        scenes.append(
            Scene(
                number=n, type="hidden_depth",
                title=f"Hidden depth — {el.description}",
                challenge_skill=CHALLENGE_TO_SKILL[cat],
                challenge_level=lvl, is_core=is_core, context=el.description,
                category=cat,
                challenge_score=_score_for(cat, lvl),
            )
        )
        n += 1

    if bonus_element is not None:
        bonus_skill, bonus_level = bonus_element.effect["bonus_challenge"]
        lo, hi = bonus_element.effect["bonus_amount_range"]
        scenes.append(
            Scene(
                number=n, type="decision",
                title=f"Decision — pursue bonus: {bonus_element.description}",
                challenge_skill=bonus_skill,
                challenge_level=bonus_level, is_core=False,
                context=(
                    f"Bonus opportunity worth ${lo:,}–${hi:,}. Pursuing it requires "
                    f"a {bonus_level.name} {bonus_skill} challenge."
                ),
                challenge_score=roll_one_score(bonus_level, job.tier, rng),
            )
        )
        n += 1

    scenes.append(
        Scene(number=n, type="transition", title="Transition to exit",
              challenge_skill=None, challenge_level=None, is_core=False, context="")
    )
    n += 1
    scenes.append(
        Scene(number=n, type="escape", title="Escape",
              challenge_skill="driver", challenge_level=None, is_core=False, context="")
    )
    return scenes
