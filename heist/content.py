"""Jobs and game constants.

Character roster lives in heist.characters — import from there.
"""

from heist.characters import ROSTER, ROSTER_BY_ID  # noqa: F401 — re-exported for callers
from heist.state import (
    ChallengeLevel,
    HiddenDepthElement,
    Job,
)

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

PENTHOUSE = Job(
    name="The Penthouse Caper",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(400_000, 1_200_000),
    profile={
        "electronic": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.NONE,
        "social": ChallengeLevel.LOW,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "penthouse_cleaning_crew",
            "Cleaning service mid-shift in the building.",
            "complication",
            {"modifies": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "penthouse_smart_home",
            "Smart-home AI assistant is active and recording.",
            "complication",
            {"modifies": [("electronic", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "penthouse_hidden_picasso",
            "Bedroom safe holds a Picasso study in addition to the main room art.",
            "bonus_with_cost",
            {"bonus_amount_range": (300_000, 700_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "penthouse_roommate",
            "The owner's brother is crashing for the week — a sleepy civilian.",
            "complication",
            {"adds": [("confrontation", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "penthouse_wifi_backdoor",
            "Someone else has already breached the home wifi — an exploitable backdoor.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.LOW)],
             "adds": [("social", ChallengeLevel.LOW)]},
        ),
    ],
    reward_amounts=[
        ("Cash + watches", 450_000),
        ("Art + safe", 850_000),
        ("Everything incl. crypto wallet", 1_150_000),
    ],
)

CARGO_YARD = Job(
    name="The Cargo Yard",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(1_200_000, 3_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "cargo_customs_inspector",
            "Customs inspector doing late-night inventory in the yard.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "cargo_buried_container",
            "Target container is buried under three others — needs the dock crane.",
            "complication",
            {"adds": [("physical", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "cargo_sister_container",
            "An identical container nearby holds the same goods — second score available.",
            "bonus_with_cost",
            {"bonus_amount_range": (400_000, 1_000_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "cargo_sleeping_watchman",
            "One of the two watchmen is asleep; the other is jumpy and looking for company.",
            "opportunity_with_cost",
            {"modifies": [("confrontation", ChallengeLevel.LOW)],
             "adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "cargo_hidden_jewels",
            "The manifest lies — the real cargo is jewels hidden in the container walls.",
            "opportunity_with_cost",
            {"adds": [("physical", ChallengeLevel.MEDIUM)]},
        ),
    ],
    reward_amounts=[
        ("Authenticated icons", 1_800_000),
        ("Counterfeits + small score", 1_300_000),
        ("Hidden jewels", 2_800_000),
    ],
)

DIPLOMATIC_RECEPTION = Job(
    name="The Diplomatic Reception",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(1_500_000, 4_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.HARD,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "diplomatic_dummy_diamond",
            "The public diamond is paste — the real Romanov is in the ambassador's office safe.",
            "opportunity_with_cost",
            {"modifies": [("physical", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "diplomatic_plainclothes_agent",
            "A plainclothes intelligence agent is working the room.",
            "complication",
            {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "diplomatic_speech_window",
            "Ambassador delivers a 20-minute farewell speech — everyone's distracted.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.MEDIUM)],
             "adds": [("electronic", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "diplomatic_classified_docs",
            "Briefing folder on the ambassador's desk could be lifted alongside the diamond.",
            "bonus_with_cost",
            {"bonus_amount_range": (600_000, 1_500_000),
             "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
        ),
        HiddenDepthElement(
            "diplomatic_press_photographer",
            "Photojournalist with a press pass keeps positioning near the target.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
    ],
    reward_amounts=[
        ("Public-diamond replica", 1_700_000),
        ("Authentic Romanov", 3_200_000),
        ("Romanov + classified docs", 3_800_000),
    ],
)

CASINO_VAULT = Job(
    name="The Casino Vault",
    flavor="[placeholder flavor — iteration 4]",
    reward_range=(5_000_000, 12_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.MEDIUM,
    },
    escape_modifier=0,
    hidden_depth=[
        HiddenDepthElement(
            "casino_floor_distraction",
            "High-roller and the pit boss have a public altercation — the floor is distracted.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.LOW),
                          ("confrontation", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "casino_external_auditor",
            "External auditor working inside the vault during the hit.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "casino_biometric_glitch",
            "Backup biometric scanner is offline — short window before the on-call tech arrives.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.MEDIUM)],
             "adds": [("physical", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "casino_whale_suite_safe",
            "The Macau whale's penthouse suite safe holds his private stake.",
            "bonus_with_cost",
            {"bonus_amount_range": (3_000_000, 6_000_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
        ),
        HiddenDepthElement(
            "casino_security_chief",
            "Head of security is roaming on a hair-trigger — ex-IDF, not a man to bluff.",
            "complication",
            {"modifies": [("confrontation", ChallengeLevel.HARD)]},
        ),
    ],
    reward_amounts=[
        ("Standard float", 7_000_000),
        ("High-roller weekend take", 10_500_000),
        ("Float + chip reserves", 12_000_000),
    ],
)

JOBS: list[Job] = [
    MUSEUM, ARMORED_CAR, SERVER_FARM,
    PENTHOUSE, CARGO_YARD, DIPLOMATIC_RECEPTION, CASINO_VAULT,
]
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

# ── Quick-test team prompts ───────────────────────────────────────────────────
#
# /api/quick-game runs two AIs side-by-side against the same roster + job slate.
# Each gets a contrasting strategy so the player can watch two philosophies play
# the same game. Team names show up in the viewer's AI picker + crew columns.

OPERATORS_PROMPT = (
    "We are professionals. Run a quiet, surgical heist. Build a balanced crew with one "
    "specialist per challenge area (electronic, physical, confrontation, social), and "
    "include a real Driver — running on foot is not an option. Leave at least a small "
    "budget cushion; don't spend the whole bankroll.\n\n"
    "Pick the lowest-risk job on the slate that the crew can plausibly cover end-to-end. "
    "Do not reach for a Hard challenge unless you have a HIGH specialist OR two MEDIUMs "
    "to pair on it.\n\n"
    "Risk tolerance: low. Decline bonus opportunities that add heat or expose the crew. "
    "If a core scene fails, ABORT — live to work another day. The take matters less than "
    "the clean exit."
)

WRECKERS_PROMPT = (
    "We came to break things. Stack the crew with MUSCLE and pair them on the "
    "confrontation track so we hit effective HIGH. Bring at least one safecracker for "
    "physical work. A Driver is nice but not required — if it's a choice between a Driver "
    "and a fourth muscle, take the muscle. Spend the whole bankroll; don't leave money on "
    "the table.\n\n"
    "Pick the highest-reward job on the slate that we can plausibly survive. Lean into "
    "Hard confrontation jobs (Armored Car, Cargo Yard) — that's where our edge is.\n\n"
    "Risk tolerance: high. ALWAYS pursue bonus opportunities — that's where the real "
    "money is. If a scene goes sideways, push through; heat is the cost of doing big "
    "business. Do not abort unless the escape is mechanically impossible."
)

# Preset used by /api/quick-game. Order matters: index 0 → AI A, index 1 → AI B.
QUICK_TEST_TEAMS: list[dict] = [
    {"name": "The Operators", "prompt": OPERATORS_PROMPT, "agent": "codex-mini"},
    {"name": "The Wreckers",  "prompt": WRECKERS_PROMPT,  "agent": "codex-mini"},
]
