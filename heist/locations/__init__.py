"""Location/job content. The job slate lives here; content.py re-exports for back-compat."""

from heist.state import ChallengeLevel, HiddenDepthElement, Job

MUSEUM = Job(
    name="The Museum Gala",
    flavor=(
        "A black-tie charity gala at the city’s biggest art museum. The Renaissance wing is "
        "being feted with a one-night exhibition, and the centerpiece is a diamond on loan "
        "from a Saudi prince. The vault is state-of-the-art, and the gala is packed with "
        "guests, photographers, and event security. Blending in is the whole challenge — "
        "and prying the stone out from behind that vault wall is the other half."
    ),
    reward_range=(1_500_000, 4_000_000),
    profile={
        "electronic": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.HARD,
    },
    escape_modifier=1,
    tier="easy",
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
    scene_loot={"social": 500_000, "physical": 2_000_000},
)

ARMORED_CAR = Job(
    name="The Armored Car",
    flavor=(
        "A weekly cash transfer between bank branches. Two armed guards ride in the cab "
        "and one more in back, and the truck itself is a moving vault. There are no cameras "
        "and no witnesses on the right stretch of road — if you pick the spot well. The "
        "guards are trained, armed, and expecting trouble, so whoever takes them had better "
        "be ready to bring it."
    ),
    reward_range=(800_000, 2_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.HARD,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=2,
    tier="easy",
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
    scene_loot={"physical": 300_000, "confrontation": 1_100_000},
)

SERVER_FARM = Job(
    name="The Corporate Server Farm",
    flavor=(
        "A pharmaceutical company’s research server room, where the target is a formula "
        "worth a fortune to the right buyer. The building is layered with electronic security: "
        "biometric locks, face recognition, and network intrusion detection. The server room "
        "itself sits behind a serious physical lock, with two guards working the perimeter. "
        "Getting in is a hacker’s problem; getting out clean is everyone’s."
    ),
    reward_range=(3_000_000, 8_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.MEDIUM,
    },
    escape_modifier=1,
    tier="medium",
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
    scene_loot={"physical": 1_000_000, "electronic": 5_000_000},
)

PENTHOUSE = Job(
    name="The Penthouse Caper",
    flavor=(
        "A tech billionaire’s penthouse, empty for the week while the owner is overseas. "
        "Inside: cash, watches, and a wall of art insured for more than most people make in "
        "a lifetime. There are no guards to fight and no crowd to charm — just a smart "
        "lock, a building full of cameras, and the quiet problem of getting in and back out "
        "without anyone knowing you were there. This one rewards a light touch, not a heavy hand."
    ),
    reward_range=(400_000, 1_200_000),
    profile={
        "electronic": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.NONE,
        "social": ChallengeLevel.LOW,
    },
    escape_modifier=0,  # residential building, walk out the lobby
    tier="medium",
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
    scene_loot={"electronic": 200_000, "physical": 450_000},
)

CARGO_YARD = Job(
    name="The Cargo Yard",
    flavor=(
        "A working freight yard at the edge of the docks, acres of stacked steel containers "
        "under sodium lights. One of them holds smuggled goods worth millions — authenticated "
        "icons, if the manifest is honest, which it rarely is. The fences and locks are nothing "
        "special, but the container is heavy, buried in the stack, and the two night watchmen "
        "do real rounds. This is a job of muscle, machinery, and timing, with nobody to talk "
        "your way past."
    ),
    reward_range=(1_200_000, 3_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=0,  # open industrial yard, dark, multiple vehicle routes
    tier="easy",
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
    scene_loot={"confrontation": 300_000, "physical": 1_500_000},
)

DIPLOMATIC_RECEPTION = Job(
    name="The Diplomatic Reception",
    flavor=(
        "A farewell reception at a foreign embassy, all tuxedos, translators, and trays of "
        "champagne. On display under glass is a historic diamond the departing ambassador is "
        "taking home. The hard part isn’t the lock — it’s the room: every guest is somebody, "
        "every server is watched, and a wrong word in the wrong ear ends the night in a "
        "holding cell. You don’t break into this one; you get invited, and you behave "
        "until you don’t."
    ),
    reward_range=(1_500_000, 4_000_000),
    profile={
        "electronic": ChallengeLevel.LOW,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.LOW,
        "social": ChallengeLevel.HARD,
    },
    escape_modifier=1,
    tier="medium",
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
    scene_loot={"social": 700_000, "physical": 1_700_000},
)

CASINO_VAULT = Job(
    name="The Casino Vault",
    flavor=(
        "The count room beneath a major casino, where a working night’s cash is stacked "
        "and waiting for the armored pickup. Every layer of the place is the best money can "
        "buy — cameras that never blink, biometric doors, and a floor that never sleeps. "
        "Reaching the vault means beating the electronics, the locks, and the muscle all at "
        "once, with a casino’s whole security apparatus a button-press away. This is the "
        "score a crew retires on, or the one they vanish over."
    ),
    reward_range=(5_000_000, 12_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.MEDIUM,
    },
    escape_modifier=2,
    tier="hard",
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
    scene_loot={"electronic": 3_000_000, "physical": 4_000_000},
)

CORNER_PHARMACY = Job(
    name="Corner Pharmacy",
    flavor=(
        "A pill mill's back office is flush with cash and nobody's watching the door. "
        "Low stakes, low heat - a good warmup."
    ),
    reward_range=(150_000, 350_000),
    profile={
        "physical": ChallengeLevel.LOW,
        "confrontation": ChallengeLevel.NONE,
        "electronic": ChallengeLevel.NONE,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=0,
    tier="easy",
    hidden_depth=[
        HiddenDepthElement(
            "pharmacy_alarm_panel",
            "The back-room alarm panel has a loose wire that could trip at the worst time.",
            "complication",
            {"adds": [("electronic", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "pharmacy_night_clerk",
            "A tired night clerk is counting stock in the back office.",
            "complication",
            {"adds": [("social", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "pharmacy_painkiller_cache",
            "A locked cabinet holds a separate stash of high-value painkillers.",
            "bonus_with_cost",
            {"bonus_amount_range": (60_000, 140_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.LOW)},
        ),
    ],
    reward_amounts=[
        ("Cash drawer", 180_000),
        ("Inventory safe", 280_000),
        ("Back-room stash", 330_000),
    ],
    scene_loot={"physical": 280_000},
)

ART_FORGERY_RING = Job(
    name="Art Forgery Ring",
    flavor=(
        "A fence hired you to swap real paintings for fakes before the auction house notices. "
        "You have one evening."
    ),
    reward_range=(450_000, 750_000),
    profile={
        "social": ChallengeLevel.MEDIUM,
        "electronic": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.LOW,
        "confrontation": ChallengeLevel.NONE,
    },
    escape_modifier=1,
    tier="medium",
    hidden_depth=[
        HiddenDepthElement(
            "forgery_preview_party",
            "The preview party runs long, giving the crew extra cover in the gallery.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "forgery_security_grid",
            "A fresh security grid guards the staging room.",
            "complication",
            {"modifies": [("electronic", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "forgery_client_archive",
            "The client's payment archive sits in a locked office next door.",
            "bonus_with_cost",
            {"bonus_amount_range": (120_000, 250_000),
             "bonus_challenge": ("inside_man", ChallengeLevel.MEDIUM)},
        ),
    ],
    reward_amounts=[
        ("Single swap", 500_000),
        ("Full wall exchange", 680_000),
        ("Wall plus archive", 740_000),
    ],
    scene_loot={"social": 300_000, "electronic": 200_000},
)

PRIVATE_AIRFIELD = Job(
    name="Private Airfield",
    flavor=(
        "A shipment is wheels-up in four hours. Intercept it on the tarmac before it "
        "disappears into the night."
    ),
    reward_range=(400_000, 700_000),
    profile={
        "confrontation": ChallengeLevel.MEDIUM,
        "physical": ChallengeLevel.MEDIUM,
        "electronic": ChallengeLevel.LOW,
        "social": ChallengeLevel.NONE,
    },
    escape_modifier=2,
    tier="medium",
    hidden_depth=[
        HiddenDepthElement(
            "airfield_fuel_truck",
            "A fuel truck is parked where the crew wants to stage the intercept.",
            "complication",
            {"adds": [("physical", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "airfield_tower_blackout",
            "The control tower loses power for a short, exploitable window.",
            "opportunity_with_cost",
            {"modifies": [("confrontation", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "airfield_cargo_manifest",
            "A second cargo pallet is misfiled and easy to take if the crew moves fast.",
            "bonus_with_cost",
            {"bonus_amount_range": (150_000, 300_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.LOW)},
        ),
    ],
    reward_amounts=[
        ("Tarmac pickup", 450_000),
        ("Full shipment", 620_000),
        ("Shipment plus pallet", 690_000),
    ],
    scene_loot={"physical": 250_000, "confrontation": 200_000},
)

CITY_HALL_RECORDS = Job(
    name="City Hall Records",
    flavor=(
        "Evidence against your employer sits in a secured vault inside an active government "
        "building. Extract it cleanly - no one can know you were here."
    ),
    reward_range=(900_000, 1_400_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "social": ChallengeLevel.HARD,
        "physical": ChallengeLevel.MEDIUM,
        "confrontation": ChallengeLevel.LOW,
    },
    escape_modifier=2,
    tier="hard",
    hidden_depth=[
        HiddenDepthElement(
            "cityhall_clerk_shift",
            "Records clerks are changing shifts, leaving a brief gap in the floor traffic.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "cityhall_lockdown_drill",
            "A surprise lockdown drill starts in the building while the crew is inside.",
            "complication",
            {"adds": [("confrontation", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "cityhall_evidence_archive",
            "A sealed evidence archive holds blackmail material alongside the target file.",
            "bonus_with_cost",
            {"bonus_amount_range": (250_000, 600_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
    ],
    reward_amounts=[
        ("Target file only", 950_000),
        ("File and attachments", 1_200_000),
        ("Archive plus evidence", 1_360_000),
    ],
    scene_loot={"electronic": 550_000, "social": 400_000},
)

HARBOR_CONTAINER_SWAP = Job(
    name="Harbor Container Swap",
    flavor=(
        "Switch a sealed container at a busy port before customs scans it. Tight window. "
        "Wrong move and the whole yard lights up."
    ),
    reward_range=(850_000, 1_300_000),
    profile={
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "electronic": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.LOW,
    },
    escape_modifier=3,
    tier="hard",
    hidden_depth=[
        HiddenDepthElement(
            "harbor_scan_window",
            "Customs scanners cycle offline for a short maintenance window.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.LOW)]},
        ),
        HiddenDepthElement(
            "harbor_foreman_walk",
            "A foreman is walking the dock and asking questions about the container numbers.",
            "complication",
            {"adds": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "harbor_stowaway_box",
            "A second sealed box rides inside the same stack and can be swapped too.",
            "bonus_with_cost",
            {"bonus_amount_range": (200_000, 500_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.MEDIUM)},
        ),
    ],
    reward_amounts=[
        ("Single swap", 900_000),
        ("Stacked pallet", 1_150_000),
        ("Dockside double", 1_280_000),
    ],
    scene_loot={"physical": 550_000, "confrontation": 350_000},
)

FEDERAL_RESERVE_BRANCH = Job(
    name="Federal Reserve Branch",
    flavor=(
        "An old regional vault, decommissioned but not emptied. The security is dated but "
        "deep. The escape is anything but."
    ),
    reward_range=(1_600_000, 2_500_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.MEDIUM,
        "social": ChallengeLevel.LOW,
    },
    escape_modifier=3,
    tier="elite",
    hidden_depth=[
        HiddenDepthElement(
            "fed_old_alarm_rack",
            "The vault alarm rack is old enough to have a documented maintenance backdoor.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "fed_transfer_team",
            "A transfer team is inside moving boxes, raising the human traffic inside the branch.",
            "complication",
            {"adds": [("confrontation", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "fed_archived_notes",
            "Archived ledgers sit in a side archive with a separate lock.",
            "bonus_with_cost",
            {"bonus_amount_range": (400_000, 900_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
        ),
    ],
    reward_amounts=[
        ("Regional vault", 1_700_000),
        ("Vault plus cash trays", 2_150_000),
        ("Vault and archive", 2_450_000),
    ],
    scene_loot={"electronic": 900_000, "physical": 800_000},
)

BILLIONAIRES_COMPOUND = Job(
    name="Billionaire's Compound",
    flavor=(
        "Private island, biometric locks, rotating guards. Every skill on your roster gets "
        "tested tonight."
    ),
    reward_range=(2_000_000, 3_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "social": ChallengeLevel.HARD,
        "physical": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.HARD,
    },
    escape_modifier=4,
    tier="elite",
    hidden_depth=[
        HiddenDepthElement(
            "compound_guest_manifest",
            "The guest manifest is wrong, and the crew can use the gap to blend in.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "compound_roving_drone",
            "A drone patrol makes the outer grounds much harder to cross unseen.",
            "complication",
            {"adds": [("electronic", ChallengeLevel.HARD)]},
        ),
        HiddenDepthElement(
            "compound_art_bunker",
            "An art bunker under the east wing holds a second, smaller treasure.",
            "bonus_with_cost",
            {"bonus_amount_range": (500_000, 1_000_000),
             "bonus_challenge": ("inside_man", ChallengeLevel.HARD)},
        ),
    ],
    reward_amounts=[
        ("Private vault", 2_100_000),
        ("Compound safehouse", 2_600_000),
        ("Island treasury", 2_950_000),
    ],
    scene_loot={"physical": 1_100_000, "electronic": 1_000_000},
)

MINT = Job(
    name="The Mint",
    flavor=(
        "The crown jewel. No crew has ever walked out clean. You think yours is different."
    ),
    reward_range=(2_500_000, 3_000_000),
    profile={
        "electronic": ChallengeLevel.HARD,
        "physical": ChallengeLevel.HARD,
        "social": ChallengeLevel.HARD,
        "confrontation": ChallengeLevel.HARD,
    },
    escape_modifier=4,
    tier="elite",
    hidden_depth=[
        HiddenDepthElement(
            "mint_legacy_system",
            "A legacy monitoring system leaves one narrow maintenance corridor exposed.",
            "opportunity_with_cost",
            {"modifies": [("electronic", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "mint_parade_cover",
            "A ceremonial transport outside the building creates a brief distraction.",
            "opportunity_with_cost",
            {"modifies": [("social", ChallengeLevel.MEDIUM)]},
        ),
        HiddenDepthElement(
            "mint_master_archive",
            "The master stamp archive could be lifted with the bullion.",
            "bonus_with_cost",
            {"bonus_amount_range": (600_000, 1_200_000),
             "bonus_challenge": ("safecracker", ChallengeLevel.HARD)},
        ),
    ],
    reward_amounts=[
        ("Coin plates", 2_550_000),
        ("Bullion run", 2_850_000),
        ("Bullion plus archive", 3_000_000),
    ],
    scene_loot={"physical": 1_300_000, "electronic": 1_250_000},
)

JOBS: list[Job] = [
    MUSEUM,
    ARMORED_CAR,
    CARGO_YARD,
    CORNER_PHARMACY,
    PENTHOUSE,
    SERVER_FARM,
    DIPLOMATIC_RECEPTION,
    ART_FORGERY_RING,
    PRIVATE_AIRFIELD,
    CASINO_VAULT,
    CITY_HALL_RECORDS,
    HARBOR_CONTAINER_SWAP,
    FEDERAL_RESERVE_BRANCH,
    BILLIONAIRES_COMPOUND,
    MINT,
]
JOBS_BY_NAME: dict[str, Job] = {j.name: j for j in JOBS}
