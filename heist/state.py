from dataclasses import dataclass, field
from enum import IntEnum


class SkillLevel(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ChallengeLevel(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HARD = 3


SKILLS = ("hacker", "safecracker", "muscle", "inside_man", "driver")
CHALLENGE_TO_SKILL = {
    "electronic": "hacker",
    "physical": "safecracker",
    "confrontation": "muscle",
    "social": "inside_man",
}


@dataclass(frozen=True)
class Character:
    id: int
    name: str
    skills: dict[str, SkillLevel]
    floor_cost: int
    # Profile fields — all optional so mechanical-only definitions stay concise.
    backstory: str = ""
    voice: str = ""
    motivation: str = ""
    quirk: str = ""
    crew_dynamic: str = ""
    weakness: str = ""
    look: str = ""
    signature_line: str = ""
    # PHASE 4 FORWARD-COMPAT — intentionally empty until Phase 4 ships.
    # Each skill will carry a hidden 1–10 score under its public bucket
    # (1–3 = Low, 4–6 = Medium, 7–10 = High). Resolution will use the true
    # score instead of the bucket. DO NOT populate or use this field before
    # Phase 4; scouting and score-resolution must ship together.
    skill_scores: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class HiddenDepthElement:
    id: str
    description: str
    type: str  # "complication" | "opportunity_with_cost" | "bonus_with_cost"
    # effect shape: {"modifies": [(challenge, new_level)], "adds": [(challenge, level)],
    #                "bonus_amount_range": (lo, hi), "bonus_challenge": (skill, level)}
    effect: dict


@dataclass(frozen=True)
class Job:
    name: str
    flavor: str
    reward_range: tuple[int, int]
    profile: dict[str, ChallengeLevel]
    escape_modifier: int
    hidden_depth: list[HiddenDepthElement]
    reward_amounts: list[tuple[str, int]]
    tier: str = ""
    # PHASE 4 FORWARD-COMPAT — intentionally empty until Phase 4 ships.
    # Each challenge in a job's profile will carry a hidden 1–10 score under
    # its public bucket. Resolution: crew skill_score >= challenge_score →
    # success. DO NOT populate or use this field before Phase 4; scouting
    # and score-resolution must ship together.
    challenge_scores: dict[str, int] = field(default_factory=dict)
    scene_loot: dict[str, int] = field(default_factory=dict)


@dataclass
class Crew:
    members: list[Character]

    @property
    def total_cost(self) -> int:
        return sum(m.floor_cost for m in self.members)


@dataclass
class HiddenDepthRoll:
    element: HiddenDepthElement
    reward_label: str
    reward_amount: int


@dataclass(frozen=True)
class Scene:
    number: int
    type: str  # "setup" | "challenge" | "hidden_depth" | "decision" | "transition" | "escape"
    title: str
    challenge_skill: str | None
    challenge_level: ChallengeLevel | None
    is_core: bool
    context: str
    category: str | None = None


@dataclass
class SceneResult:
    scene: Scene
    assigned_member_ids: list[int]
    success: bool | None
    narration: str
    reasoning: str
    decision: dict | None = None
    outcome: str | None = None  # "CLEAN"/"SQUEAK"/"FAIL"/"CAUGHT"; None for non-challenge scenes


@dataclass(frozen=True)
class TurnLog:
    """One AI call's wall-clock cost. Logged per round so the player can see
    where the heist's runtime went."""
    label: str
    seconds: float


@dataclass
class HeistState:
    crew: Crew
    job: Job
    hidden_depth: HiddenDepthRoll
    scene_results: list[SceneResult] = field(default_factory=list)
    caught_member_ids: list[int] = field(default_factory=list)
    secured_take: int = 0
    heat: int = 0
    aborted: bool = False
    bonus_pursued: bool = False
    bonus_succeeded: bool = False
    bonus_amount: int = 0
    escape_success: bool | None = None
    escape_difficulty: int | None = None
    final_take: int = 0


@dataclass
class RoundResult:
    round_idx: int
    job_name: str
    take: int
    aborted: bool
    escape_success: bool | None
    heat: int
    banked_after: int = 0
    caught_member_ids: list[int] = field(default_factory=list)
    crew_ids: list[int] = field(default_factory=list)


@dataclass
class Campaign:
    rounds_total: int
    bankroll: int
    banked_loot: int
    standing_crew: list["Character"] = field(default_factory=list)
    round_results: list[RoundResult] = field(default_factory=list)
    num_ais: int = 1
    between_round_log: list[dict] = field(default_factory=list)

    @property
    def round_idx(self) -> int:
        return len(self.round_results)

    @property
    def current_round(self) -> int:
        return min(self.round_idx + 1, self.rounds_total)

    @property
    def total_rounds(self) -> int:
        return self.rounds_total
