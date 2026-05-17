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
    personality: str


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


@dataclass
class SceneResult:
    scene: Scene
    assigned_member_ids: list[int]
    success: bool | None
    narration: str
    reasoning: str
    decision: dict | None = None


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
    heat: int = 0
    aborted: bool = False
    bonus_pursued: bool = False
    bonus_succeeded: bool = False
    bonus_amount: int = 0
    escape_success: bool | None = None
    escape_difficulty: int | None = None
    final_take: int = 0
