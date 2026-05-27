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
        "id": 1, "file": "c01_marcus", "name": 'Marcus "Prodigy"',
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
        "id": 4, "file": "c04_vance", "name": 'Vance "The Wall"',
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
        "id": 7, "file": "c07_lin", "name": 'Lin "Closer"',
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
        "skills": "Inside Man 8", "floor_cost": 425_000,
        "backstory": "Second-generation Indian-American from New Jersey, trained at Juilliard, then three years off-Broadway cast as 'terrorist #2' and 'exotic friend.' A director he respected told him he was 'always lying about the wrong thing.' He took it badly, then took it as a job description.",
        "voice": "Smooth and adaptable. Has a default voice for the road and an actor's range underneath. Hums between sentences.",
        "motivation": "Still wants to be on a stage. Tells himself the work funds the gap until his next callback, even though it has been the work for nine years now.",
        "quirk": "Says 'well, well, well' before lying. Has not noticed this tell yet.",
        "crew_dynamic": "Charming, slightly performative. Reads the room well, gets a little resentful when the room reads him back.",
        "weakness": "Can't take direction from people he thinks are less talented than he is. Which is most people.",
        "look": (
            "Three-quarter angle, half his attention on you and half on the mirror. An "
            "Indian-American man in his early forties: dark hair swept back, a small left "
            "earring, a close-trimmed greying beard. A sharp jacket half-on over an open "
            "collar. A practiced, magnetic half-smile that's quietly selling you something."
        ),
        "setting": (
            "A theater dressing room — a mirror ringed with bare bulbs throwing hard "
            "cross-hatched light, costume pieces and a wig block in the shadows behind him, a "
            "scatter of fake IDs and event lanyards among the greasepaint on the counter. The "
            "bright mirror and the black room read like two of him."
        ),
        "signature_line": '"Well, well, well — you must be the host."',
    },
    {
        "id": 9, "file": "c09_pearl", "name": "Pearl Sutton",
        "skills": "Inside Man 7, Muscle 4", "floor_cost": 275_000,
        "backstory": "Twenty years in hospitality — banquet halls, hotel front-of-house, a stint running a hospital cafeteria — the kind of work where a woman with a lanyard and something in her hands is invisible. She figured out she could walk into any building that hires staff, and started getting paid far better to walk back out with something.",
        "voice": "Friendly and fast, endlessly accommodating — the practiced warmth of someone who's de-escalated a thousand complaints. Drops it the instant the door closes.",
        "motivation": "Put three foster kids through the same system she aged out of herself. Now she's saving for the day she never has to clock in for anyone again.",
        "quirk": "Always carrying something — a tray, a clipboard, a stack of linens. Nobody stops a woman with her hands full.",
        "crew_dynamic": "Mother-hen energy that's half real, half tool: mends the crew's nerves and their shirt buttons, and keeps a quiet tally of who owes her.",
        "weakness": "Can't help fixing things — squares a crooked tray, straightens a stranger's collar — and the help who's too attentive is the help that gets noticed.",
        "look": (
            "Three-quarter angle, caught mid-step carrying a loaded tray. A plain, sturdy "
            "woman in her late forties: sandy hair in a practical ponytail, no jewelry, an "
            "utterly unremarkable face you forget while you're still looking at it. Catering "
            "blacks and a venue lanyard, a warm, busy half-smile — staff, not guest."
        ),
        "setting": (
            "A catering staging area behind a gala — stacked banquet chairs and chafing dishes "
            "cross-hatched into shadow, a service door spilling warm light into a dark "
            "back-of-house corridor. She's framed in the doorway between the bright event and "
            "the shadows she actually works in."
        ),
        "signature_line": '"You look like you could use a hand. Right this way."',
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
        "id": 11, "file": "c11_jolene", "name": 'Jolene "Jo"',
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
        "id": 16, "file": "c16_val", "name": 'Valentina "Val"',
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
    {
        "id": 17, "file": "c17_priya", "name": 'Priya "Patch"',
        "skills": "Hacker 7, Inside 5", "floor_cost": 325_000,
        "backstory": "Ran security for a regional hospital network until she flagged a breach the board wanted buried; fired the week before her options vested. Freelances now, and keeps the termination letter laminated in her bag.",
        "voice": "Precise and deadpan. Over-explains the thing she's about to do, then does it faster than anyone expects. Says 'noted' instead of 'okay.'",
        "motivation": "Paying for her father's memory-care facility, month to month. Prices every job in weeks of care bought.",
        "quirk": "Labels everything — cables, drives, people. Narrates her keystrokes under her breath.",
        "crew_dynamic": "Reliable and a little preachy about opsec. Redoes sloppy work without being asked and mentions it exactly once.",
        "weakness": "Rigid — brilliant on a prepped plan, rattled when the job goes off-script.",
        "look": (
            "Close crop, slight high angle looking down at her hands over a keyboard. "
            "A South Asian woman in her late thirties: dark hair in a tight practical bun, "
            "rectangular glasses catching the light, a faint permanent line between her brows. "
            "Deadpan and precise, lips just parted mid-explanation."
        ),
        "setting": (
            "A tidy server closet lit by a single warm task lamp, the rest of the room "
            "swallowed in black. Every cable and drive neatly labeled with a handwritten strip; "
            "a label-maker in frame. Pinned to the dark wall: a laminated letter and a small "
            "creased photo of an older man."
        ),
        "signature_line": '"Give me four minutes and a clean port. Noted."',
    },
    {
        "id": 18, "file": "c18_nadia", "name": 'Nadia "Relay"',
        "skills": "Hacker 8, Driver 6", "floor_cost": 525_000,
        "backstory": "Manila-raised; ran traffic-cam and toll-system intrusions for a rideshare syndicate before going independent, and learned to drive in EDSA gridlock. She'd rather own the last ten seconds than trust a stranger with them.",
        "voice": "Clipped and technical. Narrates latency and ETAs in the same breath. Calls every plan 'the relay.'",
        "motivation": "Building an off-grid cabin with a server rack she'll never have to leave. Counts jobs in months of solitude bought.",
        "quirk": "Keeps a stopwatch running on every job and checks it mid-sentence.",
        "crew_dynamic": "Trusts the plan over the people. Cold until you hit your marks, then loyal.",
        "weakness": "On a comms blackout she freezes for a beat — can't act on a network she can't see.",
        "look": (
            "Three-quarter angle, hands poised over a keyboard. A Filipina woman in her early "
            "thirties: warm brown skin, a shaved-side undercut, an earpiece always in, "
            "fingerless gloves. Restless, alert eyes and a faint focused half-smile."
        ),
        "setting": (
            "A dim loft lit warm from a side window, the far side sinking into deep shadow. "
            "Behind her, a wall of city maps with escape routes traced in marker; a police "
            "scanner and a set of car keys on the desk, a stopwatch beside the keyboard."
        ),
        "signature_line": '"Window\'s nine seconds. I\'m already in, and the car\'s already moving."',
    },
    {
        "id": 19, "file": "c19_tavita", "name": 'Tavita "Crowbar"',
        "skills": "Safecracker 8, Muscle 6", "floor_cost": 525_000,
        "backstory": "Samoan-New Zealander who ran demolition crews in Auckland and learned the fastest way through a wall is knowing where it's weak. Did a stretch for an 'industrial accident' that only the insurers believed was an accident.",
        "voice": "Low and unhurried. Fond of construction metaphors. Rarely finishes a coffee.",
        "motivation": "A quiet retirement and a workshop. Resents that he's best known for the loud part.",
        "quirk": "Taps a wall three times and listens before he ever touches a vault.",
        "crew_dynamic": "Gentle giant. Moves people out of the danger zone without being asked or thanked.",
        "weakness": "Too patient — keeps working a lock well past the smart moment to walk away.",
        "look": (
            "Broad bust shot from a slightly low angle, looming. A big Samoan man in his fifties: "
            "broad-shouldered, greying hair, a traditional pe'a tattoo just visible below one "
            "rolled sleeve, scarred knuckles, a contractor's pencil behind one ear. Calm and "
            "patient, one large hand raised flat as if listening to a wall."
        ),
        "setting": (
            "A stripped utility room in front of a heavy vault door, its hinges and seams "
            "catching a hard work-lamp beam; everything else cross-hatched into black. "
            "Demolition tools and a contractor's level lean against exposed concrete, fine dust "
            "hanging in the light."
        ),
        "signature_line": '"Everything\'s got a seam. Give me a minute to find it."',
    },
    {
        "id": 20, "file": "c20_rafael", "name": 'Rafael "Echo"',
        "skills": "Inside Man 9, Hacker 5", "floor_cost": 750_000,
        "backstory": "Former corporate-intelligence interrogator who realized a forged badge and a warm smile got him more than any subpoena. Left the firm the day they tried to make him testify against the wrong people.",
        "voice": "Warm and precise. Mirrors your cadence back within a sentence so you feel understood. Never raises his voice.",
        "motivation": "Proving he was always the smartest person in rooms built to overlook him.",
        "quirk": "Repeats your last two words back as a question to keep you talking.",
        "crew_dynamic": "Runs the human layer like a switchboard. The crew's default face.",
        "weakness": "Can't resist a genuinely clever mark — slows down to enjoy the duel.",
        "look": (
            "Straight-on, eye-level, composed. A Latino man in his forties, deliberately "
            "ordinary — neat blazer, simple haircut, the most forgettable person in any room by "
            "design. Soft, attentive eyes that miss nothing and a warm, disarming half-smile. "
            "A visitor badge clipped to his lapel."
        ),
        "setting": (
            "A polished public lobby at night, mostly dark: a reception desk and turnstiles "
            "softly cross-hatched behind him, a wall clock, a potted plant. A single overhead "
            "light pools on him; he holds a phone loosely, mid-conversation with someone just "
            "out of frame."
        ),
        "signature_line": '"...by design? Tell me more about \'by design.\'"',
    },
    {
        "id": 21, "file": "c21_soojin", "name": 'Soo-jin "Anvil"',
        "skills": "Muscle 9, Driver 6", "floor_cost": 800_000,
        "backstory": "Korean former Olympic weightlifter who lost her medal and her funding to a doping test she still swears was sabotage. Spent two angry years driving forklifts and box trucks in a Busan port before someone offered her work where the strength and the steering both mattered.",
        "voice": "Spare and even — answers in as few words as the question allows. Lets a long silence do the work a threat would; when she finally jokes, it lands hard.",
        "motivation": "Clearing her name is impossible, so she'll settle for never needing anyone's permission again — and a gym of her own.",
        "quirk": "Chalks her hands before anything physical, even when there's nothing to grip.",
        "crew_dynamic": "The steady center of the crew — says little, but the room organizes around where she stands.",
        "weakness": "The shoulder that ended her career still gives out under a sudden full load.",
        "look": (
            "Low-angle bust shot looking up, emphasizing her power. A powerfully built Korean "
            "woman in her late thirties: close-cropped hair, broad shoulders, a lifter's thick "
            "wrists and forearms, a calm flat gaze. Chalked hands, sleeves pushed up, arms crossed."
        ),
        "setting": (
            "A freight loading bay at night — a roll-up door half-raised behind her, stacked "
            "pallets and chain-link cross-hatched into deep shadow, a single overhead lamp hard "
            "on her shoulders. A worn weight plate props a side door open; a hand truck nearby."
        ),
        "signature_line": '"Stay behind me. It\'s simpler for everyone."',
    },
]


# ── prompt template ───────────────────────────────────────────────────────────
# Three-block structure: STYLE (constant), SUBJECT (figure), SETTING (place).
# Gemini responds better to structure than to a wall of prose.

STYLE_BLOCK = """\
STYLE & FORMAT
Codenames-style black-and-white pen-and-ink illustration, low-key and \
shadow-heavy. Square 1:1 aspect ratio. Dense cross-hatching with deep blacks \
and dramatic single-source lighting (chiaroscuro) — the figure emerges from a \
near-black background. Single figure dominant in frame. No text, no watermark.\
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
