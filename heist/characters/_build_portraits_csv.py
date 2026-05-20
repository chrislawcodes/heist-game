"""One-shot script: dump every character's profile + an assembled portrait
prompt to a CSV the user can work through (one row per character, one
portrait per row).

Run:  python -m heist.characters._build_portraits_csv

Output: heist/characters/portraits.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

# ── character data ────────────────────────────────────────────────────────────
# Source of truth for the portrait round. Profile data is drafted here and
# will be copied into the cNN_*.py character files once you're happy with it.

CHARACTERS: list[dict] = [
    {
        "id": 1, "file": "c01_marcus", "name": 'Marcus "Prodigy" Renault',
        "skills": "Hacker H, Driver L", "floor_cost": 1_100_000,
        "backstory": "Got caught running a botnet at seventeen in Lyon, did three years in a French juvenile facility, came out at twenty already too well-known for legitimate work, fell into corporate espionage by twenty-two.",
        "voice": "Switches between rapid French-accented English and dead silence. Doesn't joke, doesn't notice when other people do. Uses 'obviously' too much.",
        "motivation": "Repaying his mother for the lawyer bills she's still working off. Has never told her what he does.",
        "quirk": "Cracks his knuckles in sets of three before any keyboard work.",
        "crew_dynamic": "Treats people as either assets or obstacles. Polite to drivers because drivers save lives. Distant with everyone else.",
        "weakness": "Falls apart if his hands are restrained — can't think without typing motions.",
        # SUBJECT for portrait (no style prefix — that goes in STYLE block)
        "look": (
            "Bust shot, slight three-quarter angle. "
            "A French-Algerian man in his mid-twenties — sharp cheekbones, slicked dark hair, "
            "cleft chin, dark sunken eyes that rarely blink. He wears a black turtleneck under "
            "a charcoal blazer. Fingers half-raised, mid-keystroke. A faintly mocking "
            "expression, one eyebrow slightly raised, as though he already knows your password."
        ),
        # SETTING: the environment behind him
        "setting": (
            "A cramped basement server room — rows of rack-mounted hardware behind him "
            "with blinking indicator lights rendered as stark black dots, bundled ethernet "
            "cables looping overhead. The glow of multiple monitors casts harsh cross-hatched "
            "light across one side of his face. On the desk edge: a French transit card and a "
            "small RAID drive. The room reads as functional and inhabited, not decorative."
        ),
        "signature_line": '"Obviously, that won\'t work. Let me show you what does."',
    },
    {
        "id": 2, "file": "c02_sasha", "name": "Sasha Kuznetsova",
        "skills": "Hacker M", "floor_cost": 200_000,
        "backstory": "Grew up in a Moscow apartment block; learned coding from her father's pirated copies of MSDN. Came to Toronto on a student visa, never went home; the visa expired five years ago.",
        "voice": "Quiet and flat. Speaks with the cadence of someone translating in her head. Drops 'the' and 'a' before nouns.",
        "motivation": "Saving for a Canadian passport on the open market. Knows exactly what it costs and has about a quarter of it.",
        "quirk": "Eats apples down to the seeds — core and all — when she's nervous.",
        "crew_dynamic": "Listens more than she talks. Will execute any reasonable order; silently refuses unreasonable ones and lets the crew figure out why.",
        "weakness": "Goes to pieces around uniformed police. Not cops in plainclothes — uniforms specifically.",
        "look": (
            "Head-and-shoulders, looking directly at the viewer. "
            "A pale Slavic woman in her late twenties — mousy bobbed hair, thin lips, alert "
            "pale eyes rendered as dark shading, no makeup. She wears a plain wool sweater. "
            "No jewelry. Completely still expression, the kind that gives nothing away. "
            "The directness of her gaze is slightly unsettling."
        ),
        "setting": (
            "A sparse immigrant kitchen at night — a laptop open on the table in front of "
            "her, its screen filling the frame with a terminal window and scrolling lines of "
            "code, the harsh glow casting deep cross-hatched shadows across her face and "
            "wool sweater. A tangle of USB drives and ethernet cables beside the laptop, "
            "an empty instant-noodle cup pushed to the edge. A snow-dusted fire escape "
            "visible through the window behind her. The kitchen has almost nothing in it "
            "except the machine and her."
        ),
        "signature_line": '"I have done it. Move."',
    },
    {
        "id": 3, "file": "c03_eli", "name": 'Eli "Owl" Park',
        "skills": "Hacker L, Inside Man L", "floor_cost": 200_000,
        "backstory": "Bartended in Koreatown LA for a decade and watched every kind of grift come through the door. A regular taught her enough Linux to be dangerous, then died of a heart attack still owing her $1,400.",
        "voice": "Quick, warm, slightly hoarse like she's just been laughing. Calls people 'sweetheart' only when she wants something from them.",
        "motivation": "Buying back the bar she used to work at. The family sold it during COVID and the new owners gutted it and put in a juice place.",
        "quirk": "Counts everything visible in a room without realizing she's doing it. Will tell you afterwards there were 'eleven bottles, three glasses, and a chipped sink.'",
        "crew_dynamic": "The unofficial mom. Remembers everyone's allergies. Will fight anyone who picks on the youngest crew member.",
        "weakness": "Can't lie to people who look like her grandmother. Will give the whole job away.",
        "look": (
            "Half-body, looking slightly off-camera as if hearing something. "
            "A Korean-American woman in her late thirties — dark hair in a messy low ponytail, "
            "round wire-frame glasses, plain button-up with sleeves rolled, a bar towel draped "
            "over one shoulder. Faint amused smile, the kind that means she's already two "
            "steps ahead of the room. Heavy ink shadows behind her."
        ),
        "setting": (
            "Behind a closed bar — but on the counter in front of her, half-hidden under a "
            "bar towel, a slim laptop sits open showing a network topology diagram. A short "
            "ethernet cable runs from the laptop to a router tucked behind the bottle shelf. "
            "Rows of bottles behind her, a cracked mirror, the worn bar rail. She looks like "
            "she's tending bar; the laptop says otherwise."
        ),
        "signature_line": '"Sweetheart, count again. There\'s eleven."',
    },
    {
        "id": 4, "file": "c04_vance", "name": 'Vance "The Wall" Tobin',
        "skills": "Muscle H", "floor_cost": 700_000,
        "backstory": "Heavyweight boxer out of Detroit, ranked top twenty in the late 2000s. Got knocked out by a southpaw he should have beaten, took a head injury, never fought again. The pension stopped at $1,200 a month.",
        "voice": "Slow and deliberate, like every word costs him a thought. Pronounces every consonant. Calls everyone 'boss' — even people he doesn't respect.",
        "motivation": "His daughter has cerebral palsy. He's bought every piece of equipment in her room with this work.",
        "quirk": "Finishes every sentence with a long, slow nod, even on the phone.",
        "crew_dynamic": "Gentle outside of the work, terrifying inside it. Apologizes to everyone he has to hurt, in a low voice they can hear but the cameras can't.",
        "weakness": "His knees go cold in damp weather. He can hide it for about six minutes.",
        "look": (
            "Broad-shouldered bust shot. Looking down and slightly to the side, calm and "
            "contemplative. A heavy-set Black man in his mid-fifties — shaved head, broken "
            "nose, a scar across one cheekbone. He wears a plain dark crewneck stretched "
            "at the shoulders. Hands just out of frame but the size of them implied. "
            "Deep ink shadows along his jaw. The stillness reads as controlled, not passive."
        ),
        "setting": (
            "A boxing gym after hours — a heavy bag hanging at the edge of the frame, "
            "a chalked and scuffed floor, the ropes of an empty ring visible in the "
            "background, a row of worn equipment on wall hooks. Vintage fight posters on "
            "the wall rendered as silhouettes — one shows a figure with his hand raised. "
            "The gym feels paused mid-session, like he stepped out and hasn't come back."
        ),
        "signature_line": '"Sorry about this, boss. Stay down."',
    },
    {
        "id": 5, "file": "c05_carla", "name": "Carla Reyes",
        "skills": "Muscle M, Driver L", "floor_cost": 400_000,
        "backstory": "Two tours as a Marine MP in Iraq, came home and couldn't sleep. Joined a private security firm in Houston, quit when she realized half the job was harassing day laborers. The work she does now pays better and bothers her less.",
        "voice": "Direct, no wasted words. Uses military verbs ('clear,' 'secure,' 'negative'). When she swears in Spanish she sounds about ten years younger.",
        "motivation": "Building her sister's repair shop into a real business. The sister doesn't know the money isn't from 'private security gigs.'",
        "quirk": "Reflexively scans every room she enters — top-down, left to right, takes about four seconds.",
        "crew_dynamic": "Earns trust from drivers fast. Doesn't like operators who treat the crew like NPCs.",
        "weakness": "Has a hard time on jobs that involve kids being present, even tangentially. Will adjust the plan to keep them clear.",
        "look": (
            "Bust shot, three-quarter angle. Arms crossed, head tilted slightly, "
            "steady direct gaze. A Mexican-American woman in her late thirties — "
            "dark hair in a tight braid, strong jaw, no makeup. She wears a fitted dark "
            "T-shirt under an open denim jacket. Crisp linework, light cross-hatching. "
            "She reads the room in the time it takes most people to find a seat."
        ),
        "setting": (
            "A loading bay — a chain-link fence behind her, a rolling metal door half-raised, "
            "a security camera mounted on the wall at an angle (she's standing where the "
            "camera can't see her). A clipboard with a checklist on the floor near her boot. "
            "Clean sightlines in every direction. The space is utilitarian and she owns it."
        ),
        "signature_line": '"Negative. We\'re going around."',
    },
    {
        "id": 6, "file": "c06_big_mike", "name": "Big Mike Donato",
        "skills": "Muscle L, Driver L, Inside Man L", "floor_cost": 200_000,
        "backstory": "Worked the Newark docks for twenty years until the longshoremen's union got broken. Picked up driving for a chop shop, then for crews. Knows every back route between Trenton and the Bronx.",
        "voice": "Loud, friendly, profane. Hugs hello. Has exactly two volumes: warm shouting and quiet menace.",
        "motivation": "Pays alimony to two ex-wives and child support for four kids. Cheerfully calls himself 'the joke at his own family's holidays.'",
        "quirk": "Eats during every job. Pulls out a meatball sandwich during stakeouts. Crews who don't know him assume it's an act.",
        "crew_dynamic": "Treats everyone like family. Will lend money he won't see again. Will defend the crew with disproportionate violence if pushed.",
        "weakness": "Talks too much to attractive strangers. Has compromised himself this way before.",
        "look": (
            "Broad bust shot. Wide grin showing a chipped tooth. "
            "A heavy-set Italian-American man in his late fifties — balding with a horseshoe "
            "of close-cropped hair, thick mustache, big jowls that crease when he smiles. "
            "A stained Henley under an open work jacket. He holds a half-unwrapped meatball "
            "sub in one hand, mid-bite interrupted by a grin. Soft shading."
        ),
        "setting": (
            "A loading dock at night — a massive shipping container looms behind him, its "
            "heavy steel door hanging open. A dock hook and chain are visible to one side, "
            "a pallet of stacked crates behind that. He's got the meatball sub in one hand "
            "and a crowbar resting across his knee. The scale of the container makes most "
            "people look small; it doesn't do that to him."
        ),
        "signature_line": '"Hey hey, what\'re we doin\'? Talk to me here."',
    },
    {
        "id": 7, "file": "c07_lin", "name": 'Lin "Closer" Chen',
        "skills": "Inside Man H, Safecracker L", "floor_cost": 1_100_000,
        "backstory": "Stanford MBA, recruited into McKinsey out of school, washed out after refusing to falsify a client's quarterly report. The career was over either way; she chose the version that paid more.",
        "voice": "Crystal-clear, mid-tempo, never raised. Uses business-school vocabulary on purpose — 'stakeholder alignment,' 'downside scenario.'",
        "motivation": "Not in it for money anymore. Wants to prove her judgment was right about that quarterly report, and the cleanest evidence is doing the work for fifteen years without getting caught.",
        "quirk": "Touches her left earring with two fingers when she's about to ask the question that ends the conversation.",
        "crew_dynamic": "Crew lead by default whether or not she's in charge. Doesn't tolerate sloppiness or pep talks.",
        "weakness": "Believes she can talk her way out of anything. Has occasionally been wrong.",
        "look": (
            "Bust shot, slight three-quarter angle. Two fingers raised to touch her left "
            "pearl earring — the tell she hasn't noticed. A Chinese-American woman in her "
            "early forties — sleek black hair in a long blunt cut, perfect tailoring, "
            "a single pearl earring. Charcoal suit jacket. Faintly knowing half-smile. "
            "Sharp clean linework, minimal shading, the kind of precision that mirrors her mind."
        ),
        "setting": (
            "A corporate boardroom corner — a glass wall behind her with a city skyline "
            "visible through cross-hatched glass panes, a leather portfolio on the table "
            "edge, an untouched coffee service. A whiteboard shows a single erased column "
            "of figures. The room is expensive and empty, and she has already won whatever "
            "meeting just ended in it."
        ),
        "signature_line": '"Let\'s stress-test the downside scenario."',
    },
    {
        "id": 8, "file": "c08_theo", "name": "Theo Kapoor",
        "skills": "Inside Man M", "floor_cost": 200_000,
        "backstory": "Failed actor — three years off-Broadway, then a long slide into voiceover work and stand-in gigs. A director he respected once told him he was 'always lying about the wrong thing.' He took it badly, then he took it as a job description.",
        "voice": "Smooth and adaptable. Has a default voice for the road and an actor's range underneath. Hums between sentences.",
        "motivation": "Still wants to be on a stage. Tells himself the work funds the gap until his next callback, even though it has been the work for nine years now.",
        "quirk": "Says 'well, well, well' before lying. Has not noticed this tell yet.",
        "crew_dynamic": "Charming, slightly performative. Reads the room well, gets a little resentful when the room reads him back.",
        "weakness": "Can't take direction from people he thinks are less talented than he is. Which is most people.",
        "look": (
            "Three-quarter angle, soft confident smile mid-sentence. "
            "An Indian-American man in his early forties — dark brown hair pushed back, a small "
            "earring in the left ear, a close-trimmed beard going grey at the chin. Open-collar "
            "shirt under a cardigan. One hand gesturing slightly. Light hatching, expressive "
            "eyes that are performing sincerity and doing a good job of it."
        ),
        "setting": (
            "A theater dressing room — a mirror ringed with bare bulbs behind him (rendered "
            "as bright hatched circles), a counter scattered with makeup, rolled scripts, and "
            "a half-empty coffee cup. A costume rack at the edge of frame shows suit jackets "
            "on hangers. His own headshot photograph is tucked in the corner of the mirror, "
            "slightly curled at the edges. The room smells like ambition and cold coffee."
        ),
        "signature_line": '"Well, well, well — you must be the host."',
    },
    {
        "id": 9, "file": "c09_pearl", "name": "Pearl Sutton",
        "skills": "Inside Man M, Muscle L", "floor_cost": 400_000,
        "backstory": "Catholic boarding-school girl who ran away at sixteen, joined a small-town hustler's two-person grift in West Virginia, and learned more in eighteen months than the convent taught in eight years. The hustler is in prison; Pearl is not.",
        "voice": "Grandmotherly Appalachian accent that disarms people in seconds. Says 'darlin'' with at least three different meanings.",
        "motivation": "Doesn't know. Hasn't asked herself in a decade. Tells the crew it's about a great-niece's tuition — and the great-niece is real, but the tuition is paid.",
        "quirk": "Knits during planning sessions. Gives finished scarves to crew members at the end of jobs.",
        "crew_dynamic": "Maternal in the same way a wolf is maternal — the protectiveness is real, but so are the teeth.",
        "weakness": "Underestimates anyone under thirty until they've proven her wrong twice.",
        "look": (
            "Bust shot, slight three-quarter angle. "
            "A white woman in her early sixties — silver hair in a low bun, deeply "
            "weathered face with crow's-feet, half-moon reading glasses perched on "
            "the tip of her nose, a beaded chain looping behind her neck. She wears "
            "a thick cable-knit cardigan over a high-collar blouse with a small "
            "antique cameo brooch at the throat. In her hands: long wooden knitting "
            "needles mid-stitch, a half-finished scarf trailing into her lap. A "
            "gentle, slightly sly smile that doesn't quite reach her eyes."
        ),
        "setting": (
            "A cozy Victorian parlor — patterned floral wallpaper behind her with "
            "cross-hatched depth, a small framed family photograph hung on the wall "
            "above her shoulder, a doily-covered side table with a leather Bible "
            "and a porcelain teacup, the edge of a wing-back armchair. The room "
            "reads as lived-in but nothing competes with the figure for focus."
        ),
        "signature_line": '"Sit down, darlin\'. Tell me how I can help."',
    },
    {
        "id": 10, "file": "c10_rook", "name": "Rook Ferreira",
        "skills": "Safecracker H", "floor_cost": 700_000,
        "backstory": "Apprenticed under a Lisbon locksmith named Henriques for nine years; the old man taught her by tying her hands and making her feel the tumblers. Henriques was murdered for refusing a job in 2017. She didn't take that job either, but she has been picking it apart in her head ever since.",
        "voice": "Soft, almost whispered, with the tail of a Portuguese accent on long vowels. Never repeats herself; will simply walk away if asked.",
        "motivation": "Wants to be the person Henriques expected her to be. Doesn't believe she has gotten there yet.",
        "quirk": "Carries an antique tuning fork. Strikes it against the side of a safe before she starts. Says she's not sure why anymore.",
        "crew_dynamic": "Speaks rarely; when she does, the crew listens. Brings everyone coffee on the second day of any multi-day job; if she stops, something is wrong.",
        "weakness": "Slow. The most consistent safecracker the crew will ever meet, and also the one most likely to be standing in front of the safe when the alarm hits the eight-minute mark.",
        "look": (
            "Near-profile angle, looking down at something just below frame. "
            "A Portuguese woman in her late forties — hair cut very short and silver-grey, "
            "a lean angular face, bird-bone wrists. An old leather glove on her right hand, "
            "the other bare. Dark workshirt with the collar open. Her expression is "
            "absolute concentration, like the world has narrowed to the thing she can hear. "
            "Tight linework, heavy ink in the background corners."
        ),
        "setting": (
            "A vault antechamber — the massive circular edge of a safe dial visible at the "
            "lower-right of the frame, the heavy riveted vault door cracked open behind her. "
            "A single penlight on the floor illuminates the dial. On the concrete beside "
            "her foot: an antique tuning fork. The room is all metal and shadow except "
            "for that narrow beam of light. Henriques taught her in a room exactly like this."
        ),
        "signature_line": '"Quiet, please. I need to listen."',
    },
    {
        "id": 11, "file": "c11_jolene", "name": 'Jolene "Jo" Hayes',
        "skills": "Safecracker M, Hacker L", "floor_cost": 400_000,
        "backstory": "Grew up in Tulsa, daughter of a competitive locksmith champion who never paid for a hotel because he could open the door of the room next to his. Picked up some computer security in community college because the local jobs all wanted both.",
        "voice": "Easy Oklahoma drawl, says 'y'all' without irony. Talks through her work out loud — sometimes to the lock, sometimes to no one.",
        "motivation": "Wants to be invited to her father's annual locksmith convention as a guest of honor. Knows she can't tell him how she got that good.",
        "quirk": "Names every safe she opens. Writes the names down in a notebook.",
        "crew_dynamic": "Easygoing, willing to grunt-work. Tolerates almost any personality except people who interrupt her mid-tumbler.",
        "weakness": "Gets cocky on locks she's seen before. Has been wrong about how the manufacturer changed the spec.",
        "look": (
            "Framed chest-up, head tilted as if listening, one hand holding a lock pick. "
            "A Black woman in her early thirties — natural hair pulled back in a puff, "
            "freckled nose and cheeks, a faint smile. Plaid mechanic's shirt rolled to the "
            "elbows. She's mid-conversation with whatever she's about to open. "
            "Light cross-hatching."
        ),
        "setting": (
            "A small locksmith workshop — a wooden workbench covered in small mechanical "
            "parts and springs, a row of padlocks lined up by size on a shelf above, a jar "
            "of picks and tension wrenches in the foreground, a spiral notebook open to a "
            "handwritten list of names (the safes she's opened). On a high shelf in the "
            "background: a slightly dented trophy. Her dad won it. She borrowed his technique."
        ),
        "signature_line": '"Hush now, darlin\', she\'s almost talkin\' to me."',
    },
    {
        "id": 12, "file": "c12_nestor", "name": "Nestor Bly",
        "skills": "Safecracker M, Hacker L", "floor_cost": 400_000,
        "backstory": "Career safecracker out of Philadelphia who never quite made it to first chair, did time in '03 for a botched mall job, picked up enough hacking in the federal library to be useful again at fifty.",
        "voice": "Wry, slow, with a Philly bite on the vowels. Loves a long story.",
        "motivation": "Stays in because the apartment costs $2,400 and his social security is $1,800. Tells the crew he stays for the company.",
        "quirk": "Wears the same battered field watch every job. Resets it manually to the radio tower signal before each one.",
        "crew_dynamic": "Plays the wise uncle. Underestimated by younger crew members until they need a story he's already lived.",
        "weakness": "Tires fast on long jobs. Six hours is his limit; after that his hands shake.",
        "look": (
            "Casual bust shot. Wry half-grin, one eye slightly squinted. "
            "A white man in his early sixties — thinning grey hair combed back with old "
            "habit, deep crow's-feet, several days of stubble. Worn flannel shirt under a "
            "canvas jacket. A battered field watch on his wrist, face turned toward the "
            "viewer. Hatched shadows around the eyes, the lived-in face of someone who's "
            "heard worse news and had better coffee."
        ),
        "setting": (
            "A diner booth — but on the Formica table beside his coffee mug: a small "
            "combination padlock with its shackle open, a stethoscope coiled next to it, "
            "and a folded paper diagram of a safe mechanism with handwritten margin notes. "
            "The newspaper crossword is there too, half-finished. He does both for the same "
            "reason — something to keep the hands working."
        ),
        "signature_line": '"Used to be I could do this in my sleep. Now I just sleep through it."',
    },
    {
        "id": 13, "file": "c13_slim", "name": '"Slim" Adesanya',
        "skills": "Driver H", "floor_cost": 700_000,
        "backstory": "Drove auto-rickshaws in Lagos until eighteen, came to London as a courier and discovered he could navigate the city without a GPS. Was scouted by a crew after he outran a panicked dispatcher who happened to be a getaway driver for a bigger crew.",
        "voice": "London-Nigerian, fast, warm, never panicked. Counts out loud during chases ('three seconds, four, five — we're clear').",
        "motivation": "Sending money home to his mother who runs a small fabric shop in Surulere. She thinks he's a 'private chauffeur.'",
        "quirk": "Refuses to drive any vehicle without first sitting in the driver's seat for sixty seconds, hands on the wheel, eyes closed.",
        "crew_dynamic": "Steady, unflappable presence on the radio. Won't speak to anyone in the car for the first thirty seconds — 'the car's still introducing itself.'",
        "weakness": "Will not abandon a crew member to make an escape window. Has made this choice three times and gotten away with it twice.",
        "look": (
            "Three-quarter angle from slightly below, eyes off to one side counting "
            "something only he can see. A tall lean Nigerian man in his late twenties — "
            "very short hair, a thin gold chain at his collar, slightly amused expression "
            "that never tips into smug. Dark hoodie under a fitted jacket. One hand "
            "resting on the top arc of an unseen steering wheel. Bold confident linework."
        ),
        "setting": (
            "A car interior at night — the dashboard of a sleek sedan, gauges visible, "
            "the edge of a rain-spattered windscreen with a dark wet street beyond it. "
            "A rear-view mirror reflects blurred lights. A small St. Christopher medallion "
            "on a cord from the mirror. The seat leather is immaculate. The car is "
            "completely still and about to move very fast."
        ),
        "signature_line": '"Three seconds. Four. Five. Clear."',
    },
    {
        "id": 14, "file": "c14_margot", "name": "Margot Vinter",
        "skills": "Driver M, Inside Man L", "floor_cost": 400_000,
        "backstory": "Daughter of an East German rally driver who defected with her in 1988. Grew up between Hamburg and Berlin, did club racing in her twenties, lost her license after the third DUI. Picked up freelance driving when no insurance company would take her.",
        "voice": "Mid-Atlantic by way of West Berlin. Light, sardonic, never serious. Calls every traffic light a 'suggestion.'",
        "motivation": "Believes she is being punished by some larger force for the DUIs and that the only way out is enough money to make herself untouchable.",
        "quirk": "Smokes a single clove cigarette before and after every drive. Never during.",
        "crew_dynamic": "Chatty on the way in, silent on the way out. The crew has learned not to interrupt the silence.",
        "weakness": "Real intersections rattle her. Will refuse routes with more than six lights in the escape path.",
        "look": (
            "Half-body, leaning against an unseen surface with studied ease. "
            "A white woman in her late thirties — platinum-blonde hair in a short pixie cut, "
            "sharp cheekbones, a thin scar through one eyebrow. Driving gloves, a leather "
            "jacket. An unlit clove cigarette held loosely between two fingers. "
            "Half-smile, eyes amused, the expression of someone who knows exactly how "
            "much faster she can go. Crisp linework."
        ),
        "setting": (
            "A parking garage at night — raw concrete pillars behind her, oil-stained "
            "floor, the edge of a low-slung car's rear bumper at one corner of the frame. "
            "A faded rally sticker on the pillar behind her — a silhouette of a racing car "
            "mid-corner. Dim fluorescent tubes casting hard industrial shadows. "
            "The East German sticker is the only decoration. It's been here longer than she has."
        ),
        "signature_line": '"Lights are suggestions, darling. Brake lights especially."',
    },
    {
        "id": 15, "file": "c15_dex", "name": "Dex Owusu",
        "skills": "Driver M, Muscle L", "floor_cost": 400_000,
        "backstory": "Grew up in the Bronx, son of Ghanaian immigrants. Worked maintenance at a city bus depot for six years; learned mechanical work and pulled a couple of side gigs that got him noticed. Stayed in the work because the bus depot fired him.",
        "voice": "Brooklyn-Ghanaian cadence, slow with sudden bursts. Doesn't curse. Says 'lord have mercy' when things go badly.",
        "motivation": "Trying to save enough to start a small auto-repair shop with his cousin. Has been 'two more jobs away' for three years.",
        "quirk": "Wears the same Mets cap on every job. Won't say where he got it.",
        "crew_dynamic": "Reliable, mid-tier presence. Doesn't volunteer for hero work; doesn't shirk grunt work. The crew tends to forget he's there until they need him to lift something heavy.",
        "weakness": "Bad with computers, refuses to learn. Will hand off any tech task to whoever else is in the room.",
        "look": (
            "Casual half-body angle, neutral expression, the slightest nod. "
            "A Ghanaian-American man in his late thirties — short black hair, broad nose, "
            "a full beard kept close-cropped. A Mets cap pulled low, a plain dark zip jacket. "
            "Work gloves tucked into a back pocket, visible at his hip. Heavy shading on "
            "one side. He doesn't try to be memorable and it doesn't work — you remember him."
        ),
        "setting": (
            "Inside the cab of a city bus — he's in the driver's seat, door open, one foot "
            "on the step. The wide steering wheel dominates the foreground, the long "
            "empty aisle stretching behind him into the dark. A set of keys hangs from the "
            "ignition. Through the windscreen: the depot's fluorescent-lit yard. Taped to "
            "the dashboard: a small photograph, too small to read. His cousin's shop. "
            "Not yet."
        ),
        "signature_line": '"Lord have mercy. Where do you want it?"',
    },
    {
        "id": 16, "file": "c16_val", "name": 'Valentina "Val" Cruz',
        "skills": "Muscle M, Inside Man L", "floor_cost": 400_000,
        "backstory": "Eight years as a Cook County corrections officer in Chicago — knew every shift pattern, every blind spot, every guard who'd look the other way for the right story. Left after a use-of-force review that went nowhere. Does asset recovery now.",
        "voice": "Flat Chicago working-class. Short sentences. Doesn't explain herself twice. When she laughs it surprises people — loud and genuine, gone in a second.",
        "motivation": "Supporting her mother and two younger sisters after her father's deportation. The repo work pays well. She doesn't think too hard about the rest.",
        "quirk": "Scopes every room for the two exits and the one person who looks like trouble. Ranks them in her head before she's taken her coat off.",
        "crew_dynamic": "Calm under pressure in a way that unnerves people who don't know her. The crew trusts her immediately. She takes longer to trust the crew.",
        "weakness": "Reads people in authority as a known quantity — occasionally underestimates the ones who don't fit the profile.",
        "look": (
            "Bust shot, weight slightly forward, arms at her sides — still in the way that "
            "means she's about to move. A Puerto Rican-American woman in her mid-thirties: "
            "dark hair pulled back tight, strong build, a small scar on her chin. Plain dark "
            "jacket over a fitted turtleneck. Expression neutral, eyes tracking."
        ),
        "setting": (
            "A institutional corridor at night — almost entirely in darkness. A single "
            "fluorescent tube overhead throws a hard strip of light down onto her, the rest "
            "cross-hatched into near-black. A heavy security door visible behind her, its "
            "window reinforced with wire mesh. A keycard reader on the wall, light glowing. "
            "She's on the right side of the door. She's been on both sides."
        ),
        "signature_line": '"I\'ve been on the other side of this door. Trust me."',
    },
]


# ── prompt template ───────────────────────────────────────────────────────────
# Three-block structure: STYLE (constant), SUBJECT (figure), SETTING (place).
# Gemini responds better to structure than to a wall of prose.

STYLE_BLOCK = """\
STYLE & FORMAT
Codenames-style black-and-white pen-and-ink illustration. Square 1:1 \
aspect ratio. High-contrast cross-hatched shading throughout. Single \
figure dominant in frame. No text, no watermark.\
"""


def build_prompt(c: dict) -> str:
    return (
        f"{STYLE_BLOCK}\n"
        "\n"
        f"SUBJECT\n{c['look']}\n"
        "\n"
        f"SETTING\n{c['setting']}"
    )


# ── main ──────────────────────────────────────────────────────────────────────

COLUMNS = [
    "id", "file", "name", "skills", "floor_cost",
    "backstory", "voice", "motivation", "quirk",
    "crew_dynamic", "weakness", "look", "setting", "signature_line",
    "portrait_prompt", "portrait_filename", "portrait_done",
]


def _portrait_filename(file_stem: str, base_dir: Path) -> str:
    """Return the filename that actually exists on disk (.jpeg preferred over .jpg).
    Falls back to .jpg if neither exists yet."""
    for ext in (".jpeg", ".jpg"):
        if (base_dir / f"{file_stem}{ext}").exists():
            return f"{file_stem}{ext}"
    return f"{file_stem}.jpg"  # not yet saved — placeholder


def main() -> None:
    out_path = Path(__file__).parent / "portraits.csv"
    base_dir = out_path.parent
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for c in CHARACTERS:
            row = dict(c)
            row["portrait_prompt"] = build_prompt(c)
            row["portrait_filename"] = _portrait_filename(c["file"], base_dir)
            row["portrait_done"] = ""  # mark "yes" or "x" as you go
            writer.writerow(row)
    print(f"Wrote {out_path} ({len(CHARACTERS)} rows)")


if __name__ == "__main__":
    main()
