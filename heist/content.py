"""Jobs and game constants.

Character roster lives in heist.characters — import from there.
Location/job definitions live in heist.locations — re-exported here for back-compat.
"""

from heist.characters import ROSTER, ROSTER_BY_ID  # noqa: F401 — re-exported for callers
from heist.locations import (  # noqa: F401
    ARMORED_CAR,
    CARGO_YARD,
    CASINO_VAULT,
    DIPLOMATIC_RECEPTION,
    JOBS,
    JOBS_BY_NAME,
    MUSEUM,
    PENTHOUSE,
    SERVER_FARM,
)

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
