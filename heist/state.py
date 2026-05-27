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


class RevealLevel(IntEnum):
    """How much a player has scouted about one location dimension.
    HIDDEN → only flavor + reward range known; BUCKET → the Low/Med/Hard label;
    EXACT → the true 1-10 score. Advanced one step per scouting probe."""
    HIDDEN = 0
    BUCKET = 1
    EXACT = 2


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
    # PHASE 4 — public 1-10 score per owned skill (buckets: 1-3 Low, 4-7 Med,
    # 8-10 High). Drives pricing and resolution. The `skills` bucket map is
    # derived from these; character scores are public (scouting is locations-only).
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
    # PHASE 4 — stays EMPTY on the shared Job constant. The hidden 1-10 challenge
    # scores are rolled per round (mechanics.roll_challenge_scores) and live on
    # HeistState.challenge_scores; resolution compares crew score >= challenge score.
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
    # PHASE 4 — true 1-10 score for this scene's challenge, stamped at generation
    # from the round's rolled challenge_scores. None for non-challenge scenes.
    challenge_score: int | None = None


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
class ScoutState:
    """Per-round fog state — the single source of truth for what's been scouted.
    Read by both prompts and serialization so the two lanes never disagree.

    reveals:      job_name -> {challenge_category -> RevealLevel}
    reward_reveal: job_name -> narrow step (0 public range, 1 narrowed, 2 exact)
    free_probes:  crew size + best-driver bonus, granted at round start
    """
    reveals: dict[str, dict[str, RevealLevel]] = field(default_factory=dict)
    # Revealed EXACT challenge scores: job_name -> {category -> 1-10 score}.
    # Source of truth for what scouting has learned (buckets stay public).
    exact_scores: dict[str, dict[str, int]] = field(default_factory=dict)
    reward_reveal: dict[str, int] = field(default_factory=dict)
    free_probes: int = 0
    probes_spent_free: int = 0
    probes_paid: int = 0

    def level(self, job: str, category: str) -> RevealLevel:
        return self.reveals.get(job, {}).get(category, RevealLevel.HIDDEN)

    def scouted_score(self, job: str, category: str) -> int | None:
        return self.exact_scores.get(job, {}).get(category)

    def reveal(self, job: str, category: str) -> RevealLevel:
        """Advance one step (HIDDEN→BUCKET→EXACT); no-op at EXACT. Returns new level."""
        cur = self.level(job, category)
        if cur >= RevealLevel.EXACT:
            return cur
        nxt = RevealLevel(int(cur) + 1)
        self.reveals.setdefault(job, {})[category] = nxt
        return nxt

    def budget_remaining(self) -> int:
        return max(0, self.free_probes - self.probes_spent_free)


@dataclass
class HeistState:
    crew: Crew
    job: Job
    hidden_depth: HiddenDepthRoll
    # PHASE 4 — the round's rolled hidden challenge scores (category -> 1-10) and
    # the fog state. challenge_scores is the source for each Scene.challenge_score.
    challenge_scores: dict[str, int] = field(default_factory=dict)
    scout_state: "ScoutState" = field(default_factory=lambda: ScoutState())
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
    # PHASE 4 — what the crew scouted this round: [{job, category, score}].
    scouted: list[dict] = field(default_factory=list)


@dataclass
class Campaign:
    rounds_total: int
    bankroll: int
    banked_loot: int
    standing_crew: list["Character"] = field(default_factory=list)
    round_results: list[RoundResult] = field(default_factory=list)
    num_ais: int = 1
    between_round_log: list[dict] = field(default_factory=list)
    # Phase 4 (persistent scouting): hidden 1-10 challenge scores, rolled ONCE per
    # campaign and reused every round. Campaign-global (identical for all teams).
    # Empty ⇒ "not yet rolled" — roll on first use.
    slate_scores: dict[str, dict[str, int]] = field(default_factory=dict)
    # Per-team scouting memory that carries across rounds: only `reveals` and
    # `exact_scores` persist; the free-probe budget is granted fresh each round.
    scout_state: ScoutState = field(default_factory=ScoutState)

    @property
    def round_idx(self) -> int:
        return len(self.round_results)

    @property
    def current_round(self) -> int:
        return min(self.round_idx + 1, self.rounds_total)

    @property
    def total_rounds(self) -> int:
        return self.rounds_total
