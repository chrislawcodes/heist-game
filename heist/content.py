"""Roster + jobs. Personalities and location flavor are placeholders in iteration 1
and get polished in iteration 4."""

from heist.state import (
    ChallengeLevel,
    Character,
    HiddenDepthElement,
    Job,
    SkillLevel,
)

H = SkillLevel.HIGH
M = SkillLevel.MEDIUM
L = SkillLevel.LOW

ROSTER: list[Character] = [
    Character(1, 'Marcus "Prodigy" Renault', {"hacker": H, "driver": L}, 1100,
              "[placeholder personality — iteration 4]"),
    Character(2, "Sasha Kuznetsova", {"hacker": M}, 200,
              "[placeholder personality — iteration 4]"),
    Character(3, 'Eli "Owl" Park', {"hacker": L, "inside_man": L}, 200,
              "[placeholder personality — iteration 4]"),
    Character(4, 'Vance "The Wall" Tobin', {"muscle": H}, 700,
              "[placeholder personality — iteration 4]"),
    Character(5, "Carla Reyes", {"muscle": M, "driver": L}, 400,
              "[placeholder personality — iteration 4]"),
    Character(6, "Big Mike Donato", {"muscle": L, "driver": L}, 200,
              "[placeholder personality — iteration 4]"),
    Character(7, 'Lin "Closer" Park', {"inside_man": H, "safecracker": L}, 1100,
              "[placeholder personality — iteration 4]"),
    Character(8, "Theo Ashland", {"inside_man": M}, 200,
              "[placeholder personality — iteration 4]"),
    Character(9, "Pearl Sutton", {"inside_man": M, "muscle": L}, 400,
              "[placeholder personality — iteration 4]"),
    Character(10, "Rook Ferreira", {"safecracker": H}, 700,
              "[placeholder personality — iteration 4]"),
    Character(11, 'Jolene "Jo" Hayes', {"safecracker": M, "hacker": L}, 400,
              "[placeholder personality — iteration 4]"),
    Character(12, "Nestor Bly", {"safecracker": L, "hacker": L}, 200,
              "[placeholder personality — iteration 4]"),
    Character(13, '"Slim" Adesanya', {"driver": H}, 700,
              "[placeholder personality — iteration 4]"),
    Character(14, "Margot Vinter", {"driver": M, "inside_man": L}, 400,
              "[placeholder personality — iteration 4]"),
    Character(15, "Dex Owusu", {"driver": L, "muscle": L}, 200,
              "[placeholder personality — iteration 4]"),
]

ROSTER_BY_ID: dict[int, Character] = {c.id: c for c in ROSTER}


MUSEUM = Job(
    name="The Museum Gala",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(1_500_000, 4_000_000),
    profile={
        "electronic": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.HARD,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "museum_display_case",
            "Diamond in temporary display case with backup proximity alarm.",
            "opportunity_with_cost",
            {"modifies": [("physical", ChallengeLevel.MEDIUM),
                          ("electronic", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "museum_off_duty_detective",
            "Off-duty detective at the gala recognizes one of the crew.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "museum_prince_security",
            "Prince's private security creates friction with museum guards.",
            "complication",
            {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "museum_emerald_necklace",
            "An emerald necklace in an adjacent case is also stealable.",
            "bonus_with_cost",
            {"bonus_amount_range": (1_000_000, 2_000_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "museum_gala_long",
            "Gala running long — more time but extended exposure.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "museum_biometric",
            "Undisclosed biometric locks on the vault.",
            "complication",
            {"modifies": [("electronic", ChallengeLevel.HARD)]},
        ),
    ],
    reward_amounts=[
        ("Standard valuation", 2_500_000),
        ("Minor piece", 1_800_000),
        ("Top-of-market centerpiece", 3_800_000),
    ],
)

ARMORED_CAR = Job(
    name="The Armored Car",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(800_000, 2_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.HARD,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "armored_third_guard",
            "Third guard hidden in cargo compartment.",
            "complication",
            {"modifies": [("confrontation", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "armored_truck_early",
            "Truck arrives ten minutes early.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "armored_school_bus",
            "School bus appears at the ambush point.",
            "complication",
            {"adds": [("social", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "armored_extra_deposit",
            "Extra cash deposit aboard. More reward, more loading time.",
            "bonus_with_cost",
            {"bonus_amount_range": (500_000, 1_000_000),
             "bonus_challenge": ("muscle", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "armored_rookie_guard",
            "Rookie guard on the team — easier in theory, more unpredictable.",
            "opportunity_with_cost",
            {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "armored_police_cruiser",
            "Police cruiser running parallel on the next street.",
            "complication",
            {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
        ),
    ],
    reward_amounts=[
        ("Standard load", 1_400_000),
        ("Light load", 900_000),
        ("Heavy day", 1_900_000),
    ],
)

SERVER_FARM = Job(
    name="The Corporate Server Farm",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(3_000_000, 8_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.MEDIUM,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "server_late_team",
            "Late-night research team in adjacent lab.",
            "complication",
            {"modifies": [("social", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "server_ceo_safe",
            "CEO's office wall safe.",
            "bonus_with_cost",
            {"bonus_amount_range": (1_000_000, 3_000_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "server_new_monitor",
            "New network monitoring software just deployed.",
            "complication",
            {"modifies": [("electronic", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "server_janitor_keycard",
            "Janitor's keycard left in a door — skips one electronic challenge "
            "but the window is narrow.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "server_shift_change",
            "Earlier-than-expected guard shift change.",
            "complication",
            {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "server_moved",
            "Target server moved to executive's office — different physical layout.",
            "complication",
            {"modifies": [("physical", ChallengeLevel.HARD)]},
        ),
    ],
    reward_amounts=[
        ("Standard formula", 6_000_000),
        ("Early-stage research", 3_500_000),
        ("Late-stage with patents", 7_800_000),
    ],
)

JOBS: list[Job] = [MUSEUM, ARMORED_CAR, SERVER_FARM]
JOBS_BY_NAME: dict[str, Job] = {j.name: j for j in JOBS}

BANKROLL = 2000

DEFAULT_PROMPT = (
    "I want to run a clean, professional heist with a balanced crew. Pick whichever job "
    "fits the crew best — I trust your judgment. Build me a team that can handle whatever "
    "comes up: I want at least one specialist in each area we'll need, with backup "
    "capability through secondary skills. Risk tolerance: moderate. Pursue bonus "
    "opportunities only when they're clearly worth it. Don't take unnecessary chances. "
    "If something goes sideways, prioritize getting out clean over maximizing the take. "
    "I want a Driver — I don't want to be running on foot."
)
