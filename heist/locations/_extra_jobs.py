"""Extra job content for the contested job board (spec 002, US5 / Decision 8).

~35 additional ``Job`` definitions that deepen the pool so a 4-team, 10-round
campaign (~40 jobs consumed) never runs dry. Reward follows the same climb
model as the core slate (plan Decision 6 / FR-006..008):
  - clean take = sum(scene_loot.values()), floor >= $1,000,000;
  - take climbs with difficulty (0-Hard ~$1.0-1.6M, 1-Hard ~$2.0-3.5M,
    2-Hard ~$5-9M); the $15-18M jackpots stay with the two elite core jobs;
  - reward_range ~= (round(0.55 * take), take + best reward_amounts valuation);
  - scene_loot only pays into ACTIVE (non-NONE) profile categories.

``locations/__init__.py`` splices ``NEW_JOBS`` into the canonical ``JOBS`` list.
"""

from heist.state import ChallengeLevel, HiddenDepthElement, Job

NEW_JOBS = [
    # ----------------------------------------------------------------------
    # 0-HARD JOBS (14) — easy/medium tier, clean take $1.0-1.6M
    # ----------------------------------------------------------------------
    Job(
        name="The Jewelers' Row",
        flavor=(
            "A block of family jewelry shops shares one tired alarm contractor and one "
            "night watchman who treats his rounds like a stroll. Pick the right three "
            "display cases and you walk before the coffee's cold — no crowd, no vault, "
            "just glass, time, and a steady hand."
        ),
        reward_range=(650_000, 1_600_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.NONE,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "jewelers_shared_alarm",
                "The shared alarm loop has a known dead leg between two shops.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "jewelers_insomniac_owner",
                "One owner is upstairs, awake, and protective of his stock.",
                "complication",
                {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "jewelers_back_safe",
                "A back-room safe holds estate pieces awaiting appraisal.",
                "bonus_with_cost",
                {"bonus_amount_range": (300_000, 600_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Three best cases", 1_100_000),
            ("Whole front display", 1_350_000),
            ("Display plus estate safe", 1_550_000),
        ],
        scene_loot={"electronic": 300_000, "physical": 900_000},
    ),
    Job(
        name="The Boutique Hotel Safe",
        flavor=(
            "A discreet luxury hotel keeps a guest valuables room behind the front desk, "
            "stuffed with watches and cash from clients who'd never file a report. The "
            "night manager is the only obstacle, and he scares easy."
        ),
        reward_range=(600_000, 1_550_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "hotel_late_checkin",
                "A late check-in keeps the lobby busy past the planned window.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "hotel_master_key",
                "The night manager's master keycard opens the valuables room directly.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "hotel_celebrity_suite",
                "A celebrity suite upstairs was left unlocked with jewelry on the dresser.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 500_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Valuables room", 1_050_000),
            ("Room plus front cash", 1_300_000),
            ("Room plus celebrity suite", 1_500_000),
        ],
        scene_loot={"social": 400_000, "physical": 700_000},
    ),
    Job(
        name="Riverside Data Center",
        flavor=(
            "A mid-tier colocation facility hosts a crypto exchange's cold-wallet keys on "
            "an air-gapped machine. The badge readers are off-the-shelf and the lone tech "
            "spends his shift watching highlights. Get the hacker to the right rack."
        ),
        reward_range=(700_000, 1_650_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.LOW,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "riverside_default_creds",
                "The badge controller still runs vendor default credentials.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "riverside_audit_team",
                "A compliance auditor is doing a surprise after-hours walkthrough.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "riverside_second_cage",
                "A neighboring cage hosts a fintech's backup wallet, briefly unlocked.",
                "bonus_with_cost",
                {"bonus_amount_range": (350_000, 650_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
            HiddenDepthElement(
                "riverside_camera_loop",
                "The CCTV DVR has a writable share — footage can be looped.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.LOW)],
                 "adds": [("physical", ChallengeLevel.LOW)]},
            ),
        ],
        reward_amounts=[
            ("Cold-wallet keys", 1_150_000),
            ("Keys plus hot float", 1_400_000),
            ("Keys plus neighbor cage", 1_600_000),
        ],
        scene_loot={"electronic": 1_100_000, "physical": 200_000},
    ),
    Job(
        name="The Suburban Card Room",
        flavor=(
            "An unlicensed high-stakes poker game runs out of a McMansion basement, and "
            "the buy-ins live in a duffel by the bar. The muscle at the door is for show; "
            "the players are lawyers and dentists who won't shoot. Read the room and lift "
            "the bag."
        ),
        reward_range=(600_000, 1_450_000),
        profile={
            "electronic": ChallengeLevel.NONE,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "cardroom_drunk_host",
                "The host is drunk and oversharing — easy to play.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "cardroom_off_duty_cop",
                "One player is an off-duty cop carrying under his blazer.",
                "complication",
                {"modifies": [("confrontation", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "cardroom_back_room_stash",
                "The house keeps a second bank in a back-room gun safe.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 450_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The buy-in duffel", 1_000_000),
            ("Duffel plus side pots", 1_200_000),
            ("Duffel plus house bank", 1_400_000),
        ],
        scene_loot={"confrontation": 300_000, "social": 800_000},
    ),
    Job(
        name="The Estate Auction",
        flavor=(
            "A deceased collector's estate goes to auction, and the most valuable lot is "
            "quietly mispriced in the catalog. Bid honest, then walk out with the real "
            "piece and leave a convincing fake on the block. Charm, paperwork, and nerve."
        ),
        reward_range=(700_000, 1_600_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "auction_distracted_house",
                "The auction house is short-staffed and rushing lots through.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "auction_provenance_expert",
                "An invited provenance expert eyes the swapped piece too closely.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "auction_back_lot",
                "An unsold back lot of coins can be carried off in the confusion.",
                "bonus_with_cost",
                {"bonus_amount_range": (300_000, 600_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The mispriced lot", 1_100_000),
            ("Lot plus catalog swap", 1_300_000),
            ("Lot plus back coins", 1_550_000),
        ],
        scene_loot={"social": 800_000, "electronic": 500_000},
    ),
    Job(
        name="The Loading Dock",
        flavor=(
            "A big-box distribution dock signs for a pallet of new flagship phones every "
            "Tuesday at dawn. The forklift driver is the only soul awake, and the manifest "
            "is signed before it's checked. Be the crew in the high-vis vests."
        ),
        reward_range=(650_000, 1_500_000),
        profile={
            "electronic": ChallengeLevel.NONE,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "dock_clipboard_authority",
                "A borrowed clipboard and vest read as legitimate to the staff.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "dock_real_supervisor",
                "The real shift supervisor shows up early and starts asking names.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "dock_second_pallet",
                "A second pallet of premium tablets sits unattended by the bay door.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 500_000),
                 "bonus_challenge": ("muscle", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The phone pallet", 1_050_000),
            ("Pallet plus accessories", 1_250_000),
            ("Pallet plus tablets", 1_450_000),
        ],
        scene_loot={"physical": 900_000, "social": 250_000},
    ),
    Job(
        name="The Pawn King's Backroom",
        flavor=(
            "A neighborhood pawn empire launders far more than it lends, and the real "
            "money sleeps in a backroom safe behind the bulletproof glass. The owner is "
            "old, mean, and home alone after close. Quiet hands beat loud ones here."
        ),
        reward_range=(600_000, 1_500_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.NONE,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "pawn_panic_button",
                "There's a foot-pedal panic button behind the counter.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "pawn_old_safe",
                "The backroom safe is a decades-old model with a forgiving dial.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "pawn_jewelry_tray",
                "A tray of unredeemed jewelry sits in the front display.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 450_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.LOW)},
            ),
        ],
        reward_amounts=[
            ("Backroom safe", 1_000_000),
            ("Safe plus register", 1_200_000),
            ("Safe plus jewelry", 1_450_000),
        ],
        scene_loot={"physical": 700_000, "confrontation": 350_000},
    ),
    Job(
        name="The Campus Lab",
        flavor=(
            "A university spinout keeps a prototype battery cell in a teaching lab with a "
            "code lock a freshman could guess. Grad students drift in at odd hours, but "
            "nobody questions another lab coat. In, swap, out."
        ),
        reward_range=(600_000, 1_550_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.LOW,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "campus_propped_door",
                "A fire door is propped open by a smoker on break.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.NONE)],
                 "adds": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "campus_all_nighter",
                "A grad student pulling an all-nighter won't leave the bench.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "campus_server_closet",
                "The lab's data closet holds the unpublished research dataset.",
                "bonus_with_cost",
                {"bonus_amount_range": (300_000, 600_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Prototype cell", 1_050_000),
            ("Cell plus schematics", 1_250_000),
            ("Cell plus dataset", 1_500_000),
        ],
        scene_loot={"electronic": 750_000, "physical": 300_000},
    ),
    Job(
        name="The Wine Cellar",
        flavor=(
            "A restaurateur's private cellar holds a few cases of legendary vintage worth "
            "more than the building. The climate locks are finicky and the sommelier is "
            "loyal, but the alley door is an afterthought. Cool hands, careful crates."
        ),
        reward_range=(650_000, 1_450_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.LOW,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "cellar_temp_alarm",
                "Opening the cellar too long trips a temperature alarm.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "cellar_delivery_window",
                "A scheduled produce delivery leaves the alley door wide open.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "cellar_collector_locker",
                "A private collector's locker in the back holds a single priceless magnum.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 500_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Two cases", 1_000_000),
            ("Full rack", 1_200_000),
            ("Rack plus the magnum", 1_400_000),
        ],
        scene_loot={"physical": 1_000_000, "social": 200_000},
    ),
    Job(
        name="The Film Set Vault",
        flavor=(
            "A heist movie shoots overnight with real period jewelry on loan for the "
            "close-ups, locked in a prop trailer between takes. The set is chaos, the "
            "guards are extras, and a crew with the right lanyards is invisible. Steal "
            "the real thing in plain sight."
        ),
        reward_range=(700_000, 1_550_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "filmset_call_sheet",
                "A leaked call sheet shows exactly when the trailer goes unwatched.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "filmset_real_security",
                "The loan house sent a genuine guard who knows every piece by sight.",
                "complication",
                {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "filmset_star_trailer",
                "The lead actor's trailer safe holds a personal watch collection.",
                "bonus_with_cost",
                {"bonus_amount_range": (300_000, 600_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The loaned jewelry", 1_100_000),
            ("Jewelry plus props", 1_300_000),
            ("Jewelry plus star's watches", 1_500_000),
        ],
        scene_loot={"social": 800_000, "physical": 450_000},
    ),
    Job(
        name="The Charity Phone Bank",
        flavor=(
            "A telethon's donation processing room sits one floor below the cameras, "
            "stuffed with cash gifts and pre-filled card receipts. The volunteers are "
            "trusting and the supervisor is on air. Walk in as staff, walk out with the "
            "night's haul."
        ),
        reward_range=(600_000, 1_450_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.NONE,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "phonebank_volunteer_badge",
                "Spare volunteer badges are stacked unguarded by the door.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "phonebank_payment_processor",
                "The card terminal logs every swipe to a watchful processor.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "phonebank_anonymous_gift",
                "An anonymous bearer-bond gift was dropped at the desk tonight.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 450_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Cash gifts", 1_000_000),
            ("Cash plus card data", 1_200_000),
            ("Cash plus bearer bond", 1_400_000),
        ],
        scene_loot={"electronic": 500_000, "social": 600_000},
    ),
    Job(
        name="The Repo Lot",
        flavor=(
            "An impound yard holds a seized exotic-car collection pending a court fight, "
            "keys in a lockbox in the shack. The lone yard dog is friendlier than the "
            "fence is tall. Hot-load two onto a flatbed and roll."
        ),
        reward_range=(750_000, 1_650_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.NONE,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "repo_keybox_code",
                "The lockbox code is scrawled on a sticky note in the shack.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "repo_gps_trackers",
                "The seized cars still carry active GPS trackers.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "repo_owners_safe",
                "A repo'd safe in the evidence shed was never inventoried.",
                "bonus_with_cost",
                {"bonus_amount_range": (300_000, 650_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Two exotics", 1_150_000),
            ("Two plus parts", 1_400_000),
            ("Cars plus the safe", 1_600_000),
        ],
        scene_loot={"physical": 1_100_000, "confrontation": 250_000},
    ),
    Job(
        name="The Dealership Showroom",
        flavor=(
            "A luxury dealership parks its limited-run halo car on a turntable behind big "
            "glass, key fob in the manager's desk. The alarm is loud but slow, and the "
            "block empties after midnight. Glass, gas, gone before the patrol loops back."
        ),
        reward_range=(650_000, 1_550_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.NONE,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "dealership_service_bay",
                "The service bay roll-door was left unlatched after closing.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "dealership_silent_alarm",
                "A silent alarm pings a private patrol, not the police — but fast.",
                "complication",
                {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "dealership_finance_drawer",
                "The finance office keeps a cash drawer for under-the-table deals.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 500_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.LOW)},
            ),
        ],
        reward_amounts=[
            ("The halo car", 1_050_000),
            ("Car plus a second", 1_300_000),
            ("Cars plus finance cash", 1_500_000),
        ],
        scene_loot={"electronic": 400_000, "physical": 800_000},
    ),
    Job(
        name="The Numismatist's Shop",
        flavor=(
            "A rare-coin dealer keeps a legendary error-mint penny in a desk safe and "
            "talks about it to anyone who'll listen. The shop is small, the cameras are "
            "decorative, and the dealer trusts a fellow collector. Talk your way to the "
            "back and pocket a fortune in copper."
        ),
        reward_range=(650_000, 1_450_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="easy",
        hidden_depth=[
            HiddenDepthElement(
                "coin_lonely_dealer",
                "The dealer is lonely and desperate to show off — easy to engage.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "coin_suspicious_partner",
                "A sharp-eyed business partner returns from lunch early.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "coin_consignment_tray",
                "A consignment tray of gold sovereigns sits behind the counter.",
                "bonus_with_cost",
                {"bonus_amount_range": (250_000, 450_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.LOW)},
            ),
        ],
        reward_amounts=[
            ("The error penny", 1_000_000),
            ("Penny plus rare set", 1_200_000),
            ("Penny plus sovereigns", 1_400_000),
        ],
        scene_loot={"social": 1_000_000, "physical": 200_000},
    ),
    # ----------------------------------------------------------------------
    # 1-HARD JOBS (14) — easy/medium tier (a few hard), clean take $2.0-3.5M
    # ----------------------------------------------------------------------
    Job(
        name="The Opera House",
        flavor=(
            "Opening night at the grand opera, and a patron's diamond rivière glitters in "
            "the royal box. The lock is trivial; the room is not. Five hundred eyes, a "
            "private security detail, and a dress code you'd better honor. Get invited, "
            "play your part, and lift it between acts."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.HARD,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "opera_intermission",
                "The long second intermission empties the box for fifteen minutes.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "opera_gossip_columnist",
                "A society columnist memorizes faces and is hunting for a scoop.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "opera_patron_safe",
                "The patron's coat-check claim opens a private vault of family jewels.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_400_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
            ),
            HiddenDepthElement(
                "opera_detail_swap",
                "The security detail rotates shifts mid-performance — a brief gap.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.NONE)],
                 "adds": [("physical", ChallengeLevel.MEDIUM)]},
            ),
        ],
        reward_amounts=[
            ("The rivière", 2_400_000),
            ("Rivière plus earrings", 2_900_000),
            ("Rivière plus family vault", 3_300_000),
        ],
        scene_loot={"social": 2_000_000, "physical": 500_000},
    ),
    Job(
        name="Subway Vault Transfer",
        flavor=(
            "The transit authority moves a day's fare cash through a maintenance tunnel "
            "on a schedule that never changes. The escort is two transit cops who've "
            "never been hit. Drop into the tunnel, take the cart, and be on the platform "
            "before the next train."
        ),
        reward_range=(1_250_000, 3_300_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.NONE,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "subway_signal_delay",
                "A signal delay holds the next train, widening the window.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "subway_third_escort",
                "A third escort joined the transfer this week without notice.",
                "complication",
                {"modifies": [("confrontation", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "subway_token_room",
                "An old token-counting room nearby still holds bagged coin.",
                "bonus_with_cost",
                {"bonus_amount_range": (600_000, 1_200_000),
                 "bonus_challenge": ("muscle", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The fare cart", 2_300_000),
            ("Cart plus deposit bags", 2_800_000),
            ("Cart plus token room", 3_200_000),
        ],
        scene_loot={"confrontation": 1_900_000, "electronic": 400_000},
    ),
    Job(
        name="The Biotech Cleanroom",
        flavor=(
            "A gene-therapy startup keeps its master cell line behind an airlock with "
            "intrusion detection that thinks for itself. Beat the network, gown up, and "
            "extract the vial without tripping the contamination protocol that locks "
            "every door."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.LOW,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "biotech_maintenance_mode",
                "The IDS is in maintenance mode for a vendor patch tonight.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "biotech_contam_lockdown",
                "A dropped sample triggers a contamination lockdown of the wing.",
                "complication",
                {"adds": [("physical", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "biotech_freezer_farm",
                "The minus-eighty freezer farm holds a second salable cell line.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Master cell line", 2_400_000),
            ("Line plus protocols", 2_900_000),
            ("Line plus freezer farm", 3_300_000),
        ],
        scene_loot={"electronic": 2_000_000, "physical": 500_000},
    ),
    Job(
        name="The Yacht Charter",
        flavor=(
            "A hedge-fund manager's superyacht sits at anchor for a weekend party, a wall "
            "safe of bearer bonds below deck. The deckhands are temps and the host is "
            "drunk, but the safe is serious and the only way off is the water. Board as "
            "guests, crack it, and swim."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "yacht_party_chaos",
                "The party's a mess — nobody's checking the lower decks.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "yacht_captain_aboard",
                "The captain stayed aboard and patrols the companionway.",
                "complication",
                {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "yacht_tender_garage",
                "The tender garage hides a crate of undeclared art.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
            HiddenDepthElement(
                "yacht_radar_window",
                "Coast patrol radar has a known blind window near the headland.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.NONE)]},
            ),
        ],
        reward_amounts=[
            ("Bearer bonds", 2_400_000),
            ("Bonds plus cash", 2_900_000),
            ("Bonds plus art crate", 3_300_000),
        ],
        scene_loot={"physical": 2_100_000, "social": 400_000},
    ),
    Job(
        name="The Bank Night Drop",
        flavor=(
            "A regional bank's after-hours deposit room fills up over a holiday weekend, "
            "and the branch runs a skeleton crew. The vault timer is the easy part; the "
            "armed guard who never sits down is the hard one. Take him quiet or take the "
            "whole night to talk him still."
        ),
        reward_range=(1_250_000, 3_300_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.LOW,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "nightdrop_holiday_pileup",
                "Holiday deposits pile up — far more cash than a normal night.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.MEDIUM)],
                 "adds": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "nightdrop_silent_pendant",
                "The guard wears a silent panic pendant tied to a fast response.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "nightdrop_sdb_room",
                "The safe-deposit-box room shares the timer window with the vault.",
                "bonus_with_cost",
                {"bonus_amount_range": (600_000, 1_200_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("Deposit room", 2_300_000),
            ("Room plus vault cash", 2_800_000),
            ("Room plus deposit boxes", 3_200_000),
        ],
        scene_loot={"confrontation": 1_700_000, "physical": 600_000},
    ),
    Job(
        name="The Gold Refinery",
        flavor=(
            "A small precious-metals refinery pours bars overnight and stores the day's "
            "run in a strong room with one heavy door. The molten floor is no place to "
            "fight, and the door is purpose-built. This is a safecracker's whole evening "
            "and a backbreaking carry."
        ),
        reward_range=(1_450_000, 3_600_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.NONE,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "refinery_pour_schedule",
                "The pour schedule clears the floor of staff for a known hour.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "refinery_thermal_sensors",
                "Thermal sensors on the strong room flag any body heat near the door.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "refinery_scrap_bin",
                "The scrap reclaim bin is richer than anyone bothered to log.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_400_000),
                 "bonus_challenge": ("muscle", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Night's pour", 2_500_000),
            ("Pour plus reserves", 3_100_000),
            ("Pour plus scrap bin", 3_500_000),
        ],
        scene_loot={"physical": 2_200_000, "electronic": 400_000},
    ),
    Job(
        name="The Tech Keynote",
        flavor=(
            "A trillion-dollar company unveils its next chip on stage, and the working "
            "silicon is the only one of its kind on Earth. The convention floor is a sea "
            "of badges and handlers. Beat the prototype's locator beacon, smile at the "
            "right PR rep, and pocket the future."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "keynote_demo_chaos",
                "A live-demo crash sends handlers scrambling — cover for a grab.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "keynote_rfid_beacon",
                "Every prototype carries an RFID beacon tuned to the exits.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "keynote_green_room",
                "The green room laptop holds the unreleased roadmap.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The prototype chip", 2_400_000),
            ("Chip plus reference board", 2_900_000),
            ("Chip plus roadmap", 3_300_000),
        ],
        scene_loot={"electronic": 1_900_000, "social": 600_000},
    ),
    Job(
        name="The Cathedral Reliquary",
        flavor=(
            "A historic cathedral guards a jeweled reliquary that only leaves its case "
            "for high mass. The clergy are watchful and the faithful are everywhere, but "
            "the lock is centuries old. The hard part is the crowd of believers who'd lay "
            "down their lives for it."
        ),
        reward_range=(1_250_000, 3_300_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "cathedral_restoration",
                "Scaffolding from a restoration gives quiet access to the apse.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "cathedral_vigil",
                "An overnight prayer vigil keeps devoted parishioners in the nave.",
                "complication",
                {"modifies": [("confrontation", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "cathedral_treasury",
                "The locked treasury behind the altar holds gold chalices.",
                "bonus_with_cost",
                {"bonus_amount_range": (600_000, 1_200_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The reliquary", 2_300_000),
            ("Reliquary plus icons", 2_800_000),
            ("Reliquary plus treasury", 3_200_000),
        ],
        scene_loot={"confrontation": 1_700_000, "social": 600_000},
    ),
    Job(
        name="The Vineyard Estate",
        flavor=(
            "A wine baron's hilltop villa keeps a rare-bottle collection and a wall safe "
            "of cash behind a fence and a pack of dogs. The staff sleep in the guest "
            "house, but the grounds bite back. Over the wall, past the dogs, into the "
            "cellar — and don't break a thing on the way out."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.LOW,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "vineyard_kennel_feeding",
                "The dogs are kenneled and fed during the staff's evening meal.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.LOW)]},
            ),
            HiddenDepthElement(
                "vineyard_motion_lights",
                "New motion-triggered floodlights blanket the south slope.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "vineyard_tasting_room",
                "The tasting room display holds an auctionable century-old vintage.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Cellar plus safe", 2_400_000),
            ("Plus the art", 2_900_000),
            ("Plus century vintage", 3_300_000),
        ],
        scene_loot={"physical": 2_000_000, "confrontation": 500_000},
    ),
    Job(
        name="The Trading Floor After Hours",
        flavor=(
            "A boutique brokerage leaves its signing terminals live overnight, and a "
            "patient hacker can move a fortune before the morning reconciliation. The "
            "network is hardened and a roaming guard checks the floor, but nobody expects "
            "the theft to be quiet keystrokes in the dark."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "trading_logged_in",
                "A trader left a privileged session logged in over the weekend.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "trading_fraud_monitor",
                "An automated fraud monitor flags any transfer over a threshold.",
                "complication",
                {"adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "trading_partner_office",
                "A managing partner's office holds a personal crypto cold wallet.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Overnight transfers", 2_400_000),
            ("Transfers plus float", 2_900_000),
            ("Plus cold wallet", 3_300_000),
        ],
        scene_loot={"electronic": 2_100_000, "social": 400_000},
    ),
    Job(
        name="The Fight Night Gate",
        flavor=(
            "A championship bout fills an arena, and the night's gate cash funnels into a "
            "count room guarded by the promoter's enforcers. The crowd is a perfect cover "
            "and a perfect trap. Get past the muscle and the cash is stacked and waiting "
            "before the bank truck arrives."
        ),
        reward_range=(1_250_000, 3_300_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "fight_main_event",
                "The main event empties the corridors of staff for ten minutes.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "fight_promoter_grudge",
                "The promoter's enforcers are jumpy after a recent shakedown.",
                "complication",
                {"modifies": [("confrontation", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "fight_vip_skim",
                "The VIP betting window keeps an off-book skim in a drop box.",
                "bonus_with_cost",
                {"bonus_amount_range": (600_000, 1_200_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Gate cash", 2_300_000),
            ("Gate plus concessions", 2_800_000),
            ("Gate plus VIP skim", 3_200_000),
        ],
        scene_loot={"confrontation": 1_800_000, "social": 500_000},
    ),
    Job(
        name="The Watchmaker's Atelier",
        flavor=(
            "An independent master watchmaker assembles seven-figure complications to "
            "order, and a finished grand tourbillon is in his workshop awaiting its "
            "buyer. The street door is fine; the workshop vault is a fortress he built "
            "himself. One exquisite object, one impossible little door."
        ),
        reward_range=(1_450_000, 3_600_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.LOW,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "watch_courier_window",
                "The buyer's courier is due — the vault gets opened on a schedule.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "watch_seismic_sensor",
                "The vault sits on a seismic sensor tuned to drilling vibration.",
                "complication",
                {"modifies": [("physical", ChallengeLevel.HARD)],
                 "adds": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "watch_parts_drawer",
                "A drawer of movement blanks and rare dials is worth a small fortune.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_400_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("The tourbillon", 2_500_000),
            ("Plus client pieces", 3_100_000),
            ("Plus parts drawer", 3_500_000),
        ],
        scene_loot={"physical": 2_300_000, "electronic": 300_000},
    ),
    Job(
        name="The Election Night Count",
        flavor=(
            "A county election warehouse holds sealed donor war-chests and a server of "
            "blackmail-grade voter data on the chaotic night of a count. The place crawls "
            "with observers and a sheriff's detail. Walk in credentialed, beat the chain "
            "of custody, and leave the seals looking untouched."
        ),
        reward_range=(1_250_000, 3_300_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.HARD,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "election_credential_chaos",
                "The credential desk is overwhelmed and waving people through.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "election_partisan_observer",
                "A hawk-eyed partisan observer documents every face on the floor.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "election_data_server",
                "The voter-data server can be cloned for a blackmail buyer.",
                "bonus_with_cost",
                {"bonus_amount_range": (600_000, 1_200_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Donor war-chests", 2_300_000),
            ("Chests plus ledgers", 2_800_000),
            ("Chests plus data server", 3_200_000),
        ],
        scene_loot={"social": 1_900_000, "electronic": 400_000},
    ),
    Job(
        name="The Surgeon's Townhouse",
        flavor=(
            "A celebrity plastic surgeon keeps cash, a watch wall, and a discreet wall "
            "safe of patient blackmail in his brownstone, alarmed to the teeth. He's at a "
            "fundraiser till midnight; the housekeeper isn't. Beat the system, charm the "
            "staff, and be gone before the car returns."
        ),
        reward_range=(1_400_000, 3_400_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="medium",
        hidden_depth=[
            HiddenDepthElement(
                "surgeon_installer_code",
                "The alarm installer left a backdoor service code in the panel.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "surgeon_nanny_cam",
                "Hidden nanny cams stream to the surgeon's phone in real time.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "surgeon_blackmail_safe",
                "The patient blackmail safe is worth more than the watches to the right buyer.",
                "bonus_with_cost",
                {"bonus_amount_range": (700_000, 1_300_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
            ),
        ],
        reward_amounts=[
            ("Cash plus watches", 2_400_000),
            ("Plus art", 2_900_000),
            ("Plus blackmail safe", 3_300_000),
        ],
        scene_loot={"electronic": 1_900_000, "physical": 600_000},
    ),
    # ----------------------------------------------------------------------
    # 2-HARD JOBS (7) — medium/hard tier, clean take $5-9M
    # ----------------------------------------------------------------------
    Job(
        name="The Sovereign Wealth Vault",
        flavor=(
            "A sovereign fund parks physical bearer instruments in a private bank's deep "
            "vault, behind a hardened door and a network that watches itself. The bankers "
            "are discreet and the guards are ex-military. Beat the electronics and the "
            "steel both, or don't come at all."
        ),
        reward_range=(3_600_000, 8_400_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.LOW,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "sovereign_firmware_flaw",
                "The vault controller runs firmware with a published flaw.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "sovereign_dual_control",
                "Dual-control protocol means two staff must authorize every entry.",
                "complication",
                {"adds": [("social", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "sovereign_private_boxes",
                "Adjacent private boxes hold uncut stones for select clients.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_500_000, 3_000_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
            ),
            HiddenDepthElement(
                "sovereign_armory",
                "The guards' armory is staffed by a single bored sentry tonight.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.LOW)]},
            ),
        ],
        reward_amounts=[
            ("Bearer instruments", 5_500_000),
            ("Plus gold reserve", 7_200_000),
            ("Plus private boxes", 8_300_000),
        ],
        scene_loot={"electronic": 3_000_000, "physical": 3_500_000},
    ),
    Job(
        name="The Cartel Stash House",
        flavor=(
            "A drug cartel's accounting house holds walls of vacuum-sealed cash and the "
            "ledgers that name everyone. It's defended by men who shoot first and a "
            "counting room behind a steel cage. There's no talking your way out of this "
            "one — only in, fast and hard, and out faster."
        ),
        reward_range=(3_600_000, 8_400_000),
        profile={
            "electronic": ChallengeLevel.LOW,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.MEDIUM,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "cartel_shipment_night",
                "It's shipment night — the crew is distracted loading trucks.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "cartel_sicario_visit",
                "A senior sicario arrives unannounced with his own bodyguards.",
                "complication",
                {"modifies": [("confrontation", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "cartel_ledger_room",
                "The ledger room data is worth a fortune to a rival or the feds.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_500_000, 3_000_000),
                 "bonus_challenge": ("inside_man", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("Sealed cash walls", 5_500_000),
            ("Cash plus reserves", 7_200_000),
            ("Cash plus ledgers", 8_300_000),
        ],
        scene_loot={"physical": 3_500_000, "confrontation": 3_000_000},
    ),
    Job(
        name="The Crypto Exchange HQ",
        flavor=(
            "An offshore exchange runs its hot wallets out of a hardened headquarters, "
            "guarded by the best network defense money can buy and a social-engineering "
            "policy that trusts no one. Beat the machines and beat the people, and a "
            "nine-figure float is yours in a single irreversible transaction."
        ),
        reward_range=(3_600_000, 8_600_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.LOW,
            "confrontation": ChallengeLevel.NONE,
            "social": ChallengeLevel.HARD,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "crypto_oncall_admin",
                "A junior on-call admin can be social-engineered for a token.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "crypto_hardware_keys",
                "Withdrawals require physical hardware keys held by two officers.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "crypto_treasury_vault",
                "The cold treasury seed phrase is etched on a plate in the founder's office.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_600_000, 3_000_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("Hot wallet float", 5_700_000),
            ("Float plus fees vault", 7_400_000),
            ("Plus cold treasury", 8_500_000),
        ],
        scene_loot={"electronic": 4_000_000, "social": 2_500_000},
    ),
    Job(
        name="The Royal Jewel Tour",
        flavor=(
            "A touring exhibition of crown jewels stops in the city under a security "
            "envelope built for heads of state — biometric cases, a plainclothes detail, "
            "and a hardened transport. Beat the room full of watchers and the cases "
            "themselves. History rarely sits this close to the public."
        ),
        reward_range=(3_600_000, 8_600_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.HARD,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "royal_press_preview",
                "The press preview floods the hall with credentialed strangers.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "royal_case_seismics",
                "The display cases share a seismic and capacitance sensor net.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "royal_coronation_ring",
                "A coronation ring travels in a separate locked courier case.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_600_000, 3_000_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("The centerpiece", 5_700_000),
            ("Centerpiece plus tiara", 7_400_000),
            ("Plus coronation ring", 8_500_000),
        ],
        scene_loot={"electronic": 3_500_000, "social": 3_000_000},
    ),
    Job(
        name="The Defense Contractor",
        flavor=(
            "A defense firm keeps a classified guidance prototype in a secure facility "
            "ringed by armed response and an intrusion network that assumes the worst. "
            "The cleared staff are vetted and loyal. Beat the wire and beat the guards, "
            "and a foreign buyer pays a fortune for the box you carry out."
        ),
        reward_range=(3_600_000, 8_300_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.MEDIUM,
            "confrontation": ChallengeLevel.HARD,
            "social": ChallengeLevel.LOW,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "defense_drill_night",
                "A scheduled response drill has the guards expecting a false alarm.",
                "opportunity_with_cost",
                {"modifies": [("confrontation", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "defense_scif_lockdown",
                "Breaching the SCIF triggers an automatic facility lockdown.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)],
                 "adds": [("physical", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "defense_blueprint_cache",
                "A blueprint cache for the next-gen platform sits in the same vault.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_500_000, 2_800_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("Guidance prototype", 5_400_000),
            ("Prototype plus firmware", 7_000_000),
            ("Plus blueprint cache", 8_200_000),
        ],
        scene_loot={"electronic": 3_500_000, "physical": 3_000_000},
    ),
    Job(
        name="The Auction House Vault",
        flavor=(
            "The flagship auction house stores the season's consignments — old masters, "
            "rare stones, a Fabergé egg — in a basement vault between sales. The cataloguers "
            "are everywhere and the vault is no joke. Talk past the experts and crack the "
            "steel before the next viewing opens the doors."
        ),
        reward_range=(3_600_000, 8_600_000),
        profile={
            "electronic": ChallengeLevel.MEDIUM,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.LOW,
            "social": ChallengeLevel.HARD,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "auctionvault_inventory_day",
                "It's inventory day — the vault log is open and staff are distracted.",
                "opportunity_with_cost",
                {"modifies": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "auctionvault_appraiser",
                "A senior appraiser works late and knows every consignment by sight.",
                "complication",
                {"adds": [("social", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "auctionvault_faberge",
                "The Fabergé egg is in a separate temperature case with its own alarm.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_600_000, 3_000_000),
                 "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
            ),
        ],
        reward_amounts=[
            ("Season consignments", 5_700_000),
            ("Plus the old masters", 7_400_000),
            ("Plus the Fabergé egg", 8_500_000),
        ],
        scene_loot={"physical": 4_000_000, "social": 2_500_000},
    ),
    Job(
        name="The Mountain Bunker",
        flavor=(
            "A reclusive billionaire's doomsday bunker, carved into a mountain, holds gold, "
            "art, and hard drives of secrets behind a blast door and a private security "
            "force. The approach is exposed and the air-handling is monitored. Beat the "
            "electronics, the guards, and the mountain itself."
        ),
        reward_range=(4_300_000, 9_100_000),
        profile={
            "electronic": ChallengeLevel.HARD,
            "physical": ChallengeLevel.HARD,
            "confrontation": ChallengeLevel.MEDIUM,
            "social": ChallengeLevel.LOW,
        },
        tier="hard",
        hidden_depth=[
            HiddenDepthElement(
                "bunker_resupply_convoy",
                "A resupply convoy props the blast door for an hour of loading.",
                "opportunity_with_cost",
                {"modifies": [("physical", ChallengeLevel.MEDIUM)]},
            ),
            HiddenDepthElement(
                "bunker_air_sensors",
                "Air-handling sensors detect extra bodies by CO2 rise.",
                "complication",
                {"modifies": [("electronic", ChallengeLevel.HARD)]},
            ),
            HiddenDepthElement(
                "bunker_secrets_drive",
                "A drive of the billionaire's secrets is worth a fortune to the right enemy.",
                "bonus_with_cost",
                {"bonus_amount_range": (1_800_000, 3_200_000),
                 "bonus_challenge": ("hacker", ChallengeLevel.HARD)},
            ),
            HiddenDepthElement(
                "bunker_generator_window",
                "A generator changeover blinks the cameras for a known thirty seconds.",
                "opportunity_with_cost",
                {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
            ),
        ],
        reward_amounts=[
            ("Gold and art", 6_000_000),
            ("Plus the wine vault", 7_800_000),
            ("Plus secrets drive", 9_000_000),
        ],
        scene_loot={"electronic": 3_800_000, "physical": 4_000_000},
    ),
]
