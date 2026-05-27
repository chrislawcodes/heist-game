"""Character roster for the heist game.

This is the single source of truth for all character data.
Portraits (*.jpeg) live alongside this file in the same directory.

Exports
-------
ROSTER       list[Character]  — ordered by id
ROSTER_BY_ID dict[int, Character]
"""
from __future__ import annotations

from dataclasses import replace

from heist.mechanics import score_floor_cost, score_to_bucket
from heist.state import Character, SkillLevel

H = SkillLevel.HIGH
M = SkillLevel.MEDIUM
L = SkillLevel.LOW


def _with_derived(c: Character) -> Character:
    """skill_scores is the single source of truth: derive the public bucket map
    and the floor cost from the 1-10 scores so they can never drift."""
    return replace(
        c,
        skills={sk: score_to_bucket(v) for sk, v in c.skill_scores.items()},
        floor_cost=score_floor_cost(c),
    )


# Raw definitions carry skill_scores + personality; `skills`/`floor_cost` literals
# below are placeholders — _with_derived recomputes both from the scores.
_RAW_ROSTER: list[Character] = [
    Character(
        id=1,
        name='Marcus "Prodigy" Renault',
        skills={"hacker": H, "driver": L},
        skill_scores={"hacker": 10, "driver": 2},
        floor_cost=1_200_000,
        backstory=(
            "Got caught running a botnet at seventeen in Lyon, did three years in a French "
            "juvenile facility, came out at twenty already too well-known for legitimate work, "
            "fell into corporate espionage by twenty-two."
        ),
        voice=(
            "Switches between rapid French-accented English and dead silence. Doesn't joke, "
            "doesn't notice when other people do. Uses 'obviously' too much."
        ),
        motivation=(
            "Repaying his mother for the lawyer bills she's still working off. "
            "Has never told her what he does."
        ),
        quirk="Cracks his knuckles in sets of three before any keyboard work.",
        crew_dynamic=(
            "Treats people as either assets or obstacles. Polite to drivers because drivers "
            "save lives. Distant with everyone else."
        ),
        weakness="Falls apart if his hands are restrained — can't think without typing motions.",
        look=(
            "Young French-Algerian man in his mid-twenties: sharp cheekbones, slicked dark "
            "hair, cleft chin, dark sunken eyes. Black turtleneck under a charcoal blazer. "
            "Faintly mocking expression, one eyebrow slightly raised."
        ),
        signature_line='"Obviously, that won\'t work. Let me show you what does."',
    ),
    Character(
        id=2,
        name="Sasha Kuznetsova",
        skills={"hacker": M},
        skill_scores={"hacker": 6},
        floor_cost=200_000,
        backstory=(
            "Grew up in a Moscow apartment block; learned coding from her father's pirated "
            "copies of MSDN. Came to Toronto on a student visa, never went home; "
            "the visa expired five years ago."
        ),
        voice=(
            "Quiet and flat. Speaks with the cadence of someone translating in her head. "
            "Drops 'the' and 'a' before nouns."
        ),
        motivation=(
            "Saving for a Canadian passport on the open market. Knows exactly what it costs "
            "and has about a quarter of it."
        ),
        quirk="Eats apples down to the seeds — core and all — when she's nervous.",
        crew_dynamic=(
            "Listens more than she talks. Will execute any reasonable order; silently refuses "
            "unreasonable ones and lets the crew figure out why."
        ),
        weakness="Goes to pieces around uniformed police. Not cops in plainclothes — uniforms specifically.",
        look=(
            "Pale Slavic woman in her late twenties: mousy bobbed hair, thin lips, alert pale "
            "eyes, no makeup. Plain wool sweater, no jewelry. Completely still expression "
            "that gives nothing away."
        ),
        signature_line='"I have done it. Move."',
    ),
    Character(
        id=3,
        name='Eli "Owl" Park',
        skills={"hacker": L, "inside_man": L},
        skill_scores={"hacker": 3, "inside_man": 5},
        floor_cost=100_000,
        backstory=(
            "Bartended in Koreatown LA for a decade and watched every kind of grift come "
            "through the door. A regular taught her enough Linux to be dangerous, then died "
            "of a heart attack still owing her $1,400."
        ),
        voice=(
            "Quick, warm, slightly hoarse like she's just been laughing. Calls people "
            "'sweetheart' only when she wants something from them."
        ),
        motivation=(
            "Buying back the bar she used to work at. The family sold it during COVID and "
            "the new owners gutted it and put in a juice place."
        ),
        quirk=(
            "Counts everything visible in a room without realizing she's doing it. "
            "Will tell you afterwards there were 'eleven bottles, three glasses, and a chipped sink.'"
        ),
        crew_dynamic=(
            "The unofficial mom. Remembers everyone's allergies. Will fight anyone who picks "
            "on the youngest crew member."
        ),
        weakness="Can't lie to people who look like her grandmother. Will give the whole job away.",
        look=(
            "Korean-American woman in her late thirties: dark hair in a messy low ponytail, "
            "round wire-frame glasses, plain button-up with sleeves rolled, bar towel over "
            "one shoulder. Faint amused smile."
        ),
        signature_line='"Sweetheart, count again. There\'s eleven."',
    ),
    Character(
        id=4,
        name='Vance "The Wall" Tobin',
        skills={"muscle": H},
        skill_scores={"muscle": 8},
        floor_cost=425_000,
        backstory=(
            "Heavyweight boxer out of Detroit, ranked top twenty in the late 2000s. "
            "Got knocked out by a southpaw he should have beaten, took a head injury, "
            "never fought again. The pension stopped at $1,200 a month."
        ),
        voice=(
            "Slow and deliberate, like every word costs him a thought. Pronounces every "
            "consonant. Calls everyone 'boss' — even people he doesn't respect."
        ),
        motivation=(
            "His daughter has cerebral palsy. He's bought every piece of equipment "
            "in her room with this work."
        ),
        quirk="Finishes every sentence with a long, slow nod, even on the phone.",
        crew_dynamic=(
            "Gentle outside of the work, terrifying inside it. Apologizes to everyone he "
            "has to hurt, in a low voice they can hear but the cameras can't."
        ),
        weakness="His knees go cold in damp weather. He can hide it for about six minutes.",
        look=(
            "Heavy-set Black man in his mid-fifties: shaved head, broken nose, scar across "
            "one cheekbone. Plain dark crewneck stretched at the shoulders. Looking down and "
            "slightly to the side, calm — the stillness reads as controlled, not passive."
        ),
        signature_line='"Sorry about this, boss. Stay down."',
    ),
    Character(
        id=5,
        name="Carla Reyes",
        skills={"muscle": M, "driver": L},
        skill_scores={"muscle": 6, "driver": 5},
        floor_cost=200_000,
        backstory=(
            "Two tours as a Marine MP in Iraq, came home and couldn't sleep. Joined a private "
            "security firm in Houston, quit when she realized half the job was harassing day "
            "laborers. The work she does now pays better and bothers her less."
        ),
        voice=(
            "Direct, no wasted words. Uses military verbs ('clear,' 'secure,' 'negative'). "
            "When she swears in Spanish she sounds about ten years younger."
        ),
        motivation=(
            "Building her sister's repair shop into a real business. The sister doesn't know "
            "the money isn't from 'private security gigs.'"
        ),
        quirk="Reflexively scans every room she enters — top-down, left to right, takes about four seconds.",
        crew_dynamic="Earns trust from drivers fast. Doesn't like operators who treat the crew like NPCs.",
        weakness=(
            "Has a hard time on jobs that involve kids being present, even tangentially. "
            "Will adjust the plan to keep them clear."
        ),
        look=(
            "Mexican-American woman in her late thirties: dark hair in a tight braid, strong "
            "jaw, no makeup. Fitted dark T-shirt under an open denim jacket. Arms crossed, "
            "steady gaze."
        ),
        signature_line='"Negative. We\'re going around."',
    ),
    Character(
        id=6,
        name="Big Mike Donato",
        skills={"muscle": L, "driver": L, "inside_man": L},
        skill_scores={"driver": 5, "muscle": 3, "inside_man": 2},
        floor_cost=100_000,
        backstory=(
            "Worked the Newark docks for twenty years until the longshoremen's union got "
            "broken. Picked up driving for a chop shop, then for crews. Knows every back "
            "route between Trenton and the Bronx."
        ),
        voice=(
            "Loud, friendly, profane. Hugs hello. Has exactly two volumes: "
            "warm shouting and quiet menace."
        ),
        motivation=(
            "Pays alimony to two ex-wives and child support for four kids. "
            "Cheerfully calls himself 'the joke at his own family's holidays.'"
        ),
        quirk=(
            "Eats during every job. Pulls out a meatball sandwich during stakeouts. "
            "Crews who don't know him assume it's an act."
        ),
        crew_dynamic=(
            "Treats everyone like family. Will lend money he won't see again. "
            "Will defend the crew with disproportionate violence if pushed."
        ),
        weakness="Talks too much to attractive strangers. Has compromised himself this way before.",
        look=(
            "Heavy-set Italian-American man in his late fifties: balding with a horseshoe "
            "of close-cropped hair, thick mustache, big jowls. Stained Henley under an open "
            "work jacket. Wide grin showing a chipped tooth."
        ),
        signature_line='"Hey hey, what\'re we doin\'? Talk to me here."',
    ),
    Character(
        id=7,
        name='Lin "Closer" Chen',
        skills={"inside_man": H, "safecracker": L},
        skill_scores={"inside_man": 9, "safecracker": 2},
        floor_cost=700_000,
        backstory=(
            "Stanford MBA, second-generation Chinese-American, recruited into McKinsey out "
            "of school, washed out after refusing to falsify a client's quarterly report. "
            "The career was over either way; she chose the version that paid more."
        ),
        voice=(
            "Crystal-clear, mid-tempo, never raised. Uses business-school vocabulary on "
            "purpose — 'stakeholder alignment,' 'downside scenario.'"
        ),
        motivation=(
            "Not in it for money anymore. Wants to prove her judgment was right about that "
            "quarterly report, and the cleanest evidence is doing the work for fifteen years "
            "without getting caught."
        ),
        quirk=(
            "Touches her left earring with two fingers when she's about to ask the question "
            "that ends the conversation."
        ),
        crew_dynamic=(
            "Crew lead by default whether or not she's in charge. "
            "Doesn't tolerate sloppiness or pep talks."
        ),
        weakness="Believes she can talk her way out of anything. Has occasionally been wrong.",
        look=(
            "Chinese-American woman in her early forties: sleek black hair in a long blunt "
            "cut, perfect tailoring, single pearl earring. Charcoal suit jacket. "
            "Faintly knowing half-smile."
        ),
        signature_line='"Let\'s stress-test the downside scenario."',
    ),
    Character(
        id=8,
        name="Theo Kapoor",
        skills={"inside_man": M},
        skill_scores={"inside_man": 6},
        floor_cost=200_000,
        backstory=(
            "Second-generation Indian-American from New Jersey, trained at Juilliard on a "
            "scholarship, spent three years off-Broadway getting cast as 'terrorist #2' and "
            "'exotic friend.' A director he respected once told him he was 'always lying "
            "about the wrong thing.' He took it badly, then he took it as a job description."
        ),
        voice=(
            "Smooth and adaptable — BBC English, Jersey drawl, or a mid-Atlantic nothing, "
            "depending on the room. Has a default voice for the road and an actor's range "
            "underneath. Hums between sentences."
        ),
        motivation=(
            "Still wants to be on a stage playing a lead, not a prop. Tells himself the "
            "work funds the gap until his next callback, even though it has been the work "
            "for nine years now."
        ),
        quirk="Says 'well, well, well' before lying. Has not noticed this tell yet.",
        crew_dynamic=(
            "Charming, slightly performative. Reads the room well, gets a little resentful "
            "when the room reads him back."
        ),
        weakness=(
            "Can't take direction from people he thinks are less talented than he is. "
            "Which is most people."
        ),
        look=(
            "Indian-American man in his early forties: dark brown hair pushed back, small "
            "earring in the left ear, close-trimmed beard going grey at the chin. "
            "Open-collar shirt under a cardigan. Soft confident smile mid-sentence."
        ),
        signature_line='"Well, well, well — you must be the host."',
    ),
    Character(
        id=9,
        name="Pearl Sutton",
        skills={"inside_man": M, "muscle": L},
        skill_scores={"inside_man": 7, "muscle": 4},
        floor_cost=275_000,
        backstory=(
            "Catholic boarding-school girl who ran away at sixteen, joined a small-town "
            "hustler's two-person grift in West Virginia, and learned more in eighteen months "
            "than the convent taught in eight years. The hustler is in prison; Pearl is not."
        ),
        voice=(
            "Grandmotherly Appalachian accent that disarms people in seconds. "
            "Says 'darlin'' with at least three different meanings."
        ),
        motivation=(
            "Doesn't know. Hasn't asked herself in a decade. Tells the crew it's about a "
            "great-niece's tuition — and the great-niece is real, but the tuition is paid."
        ),
        quirk="Knits during planning sessions. Gives finished scarves to crew members at the end of jobs.",
        crew_dynamic=(
            "Maternal in the same way a wolf is maternal — the protectiveness is real, "
            "but so are the teeth."
        ),
        weakness="Underestimates anyone under thirty until they've proven her wrong twice.",
        look=(
            "White woman in her early sixties: silver hair in a low bun, weathered face with "
            "crow's-feet, half-moon reading glasses on a beaded chain. Cable-knit cardigan "
            "over a high-collar blouse, antique cameo brooch at the throat. Knitting needles "
            "in her hands. Gentle smile that doesn't quite reach her eyes."
        ),
        signature_line='"Sit down, darlin\'. Tell me how I can help."',
    ),
    Character(
        id=10,
        name="Rook Ferreira",
        skills={"safecracker": H},
        skill_scores={"safecracker": 9},
        floor_cost=700_000,
        backstory=(
            "Apprenticed under a Lisbon locksmith named Henriques for nine years; the old man "
            "taught her by tying her hands and making her feel the tumblers. Henriques was "
            "murdered for refusing a job in 2017. She didn't take that job either, but she "
            "has been picking it apart in her head ever since."
        ),
        voice=(
            "Soft, almost whispered, with the tail of a Portuguese accent on long vowels. "
            "Never repeats herself; will simply walk away if asked."
        ),
        motivation=(
            "Wants to be the person Henriques expected her to be. "
            "Doesn't believe she has gotten there yet."
        ),
        quirk=(
            "Carries an antique tuning fork. Strikes it against the side of a safe before "
            "she starts. Says she's not sure why anymore."
        ),
        crew_dynamic=(
            "Speaks rarely; when she does, the crew listens. Brings everyone coffee on the "
            "second day of any multi-day job; if she stops, something is wrong."
        ),
        weakness=(
            "Slow. The most consistent safecracker the crew will ever meet, and also the one "
            "most likely to be standing in front of the safe when the alarm hits eight minutes."
        ),
        look=(
            "Portuguese woman in her late forties: hair cut very short and silver-grey, lean "
            "angular face, bird-bone wrists. Old leather glove on one hand. Dark workshirt. "
            "Expression of absolute concentration."
        ),
        signature_line='"Quiet, please. I need to listen."',
    ),
    Character(
        id=11,
        name='Jolene "Jo" Hayes',
        skills={"safecracker": M, "hacker": L},
        skill_scores={"safecracker": 6, "hacker": 4},
        floor_cost=200_000,
        backstory=(
            "Grew up in Tulsa's Greenwood District, granddaughter of a man who rebuilt his "
            "hardware store after 1921 and never talked about it. Her father became a "
            "competitive locksmith champion — never paid for a hotel because he could open "
            "the room next door. Jolene picked up computer security in community college "
            "because the local jobs all wanted both."
        ),
        voice=(
            "Easy Oklahoma drawl, says 'y'all' without irony. Talks through her work out loud "
            "— sometimes to the lock, sometimes to no one."
        ),
        motivation=(
            "Wants to be invited to her father's annual locksmith convention as a guest of "
            "honor. Knows she can't tell him how she got that good."
        ),
        quirk="Names every safe she opens. Writes the names down in a notebook.",
        crew_dynamic=(
            "Easygoing, willing to grunt-work. Tolerates almost any personality except "
            "people who interrupt her mid-tumbler."
        ),
        weakness=(
            "Gets cocky on locks she's seen before. Has been wrong about how the manufacturer "
            "changed the spec."
        ),
        look=(
            "Black woman in her early thirties: natural hair pulled back in a puff, freckled "
            "nose and cheeks, faint smile. Plaid mechanic's shirt rolled to the elbows. "
            "Head tilted as if listening, one hand holding a lock pick."
        ),
        signature_line='"Hush now, darlin\', she\'s almost talkin\' to me."',
    ),
    Character(
        id=12,
        name="Nestor Bly",
        skills={"safecracker": M, "hacker": L},
        skill_scores={"safecracker": 5, "hacker": 4},
        floor_cost=150_000,
        backstory=(
            "Career safecracker out of Philadelphia who never quite made it to first chair, "
            "did time in '03 for a botched mall job, picked up enough hacking in the federal "
            "library to be useful again at fifty."
        ),
        voice="Wry, slow, with a Philly bite on the vowels. Loves a long story.",
        motivation=(
            "Stays in because the apartment costs $2,400 and his social security is $1,800. "
            "Tells the crew he stays for the company."
        ),
        quirk=(
            "Wears the same battered field watch every job. "
            "Resets it manually to the radio tower signal before each one."
        ),
        crew_dynamic=(
            "Plays the wise uncle. Underestimated by younger crew members until they need "
            "a story he's already lived."
        ),
        weakness="Tires fast on long jobs. Six hours is his limit; after that his hands shake.",
        look=(
            "White man in his early sixties: thinning grey hair combed back, deep crow's-feet, "
            "a few days of stubble. Worn flannel under a canvas jacket, battered field watch "
            "on his wrist. Wry half-grin."
        ),
        signature_line='"Used to be I could do this in my sleep. Now I just sleep through it."',
    ),
    Character(
        id=13,
        name='"Slim" Adesanya',
        skills={"driver": H},
        skill_scores={"driver": 9},
        floor_cost=700_000,
        backstory=(
            "Drove auto-rickshaws in Lagos until eighteen, came to London as a courier and "
            "discovered he could navigate the city without a GPS. Was scouted by a crew after "
            "he outran a panicked dispatcher who happened to be a getaway driver for a bigger crew."
        ),
        voice=(
            "London-Nigerian, fast, warm, never panicked. Counts out loud during chases "
            "('three seconds, four, five — we're clear')."
        ),
        motivation=(
            "Sending money home to his mother who runs a small fabric shop in Surulere. "
            "She thinks he's a 'private chauffeur.'"
        ),
        quirk=(
            "Refuses to drive any vehicle without first sitting in the driver's seat for "
            "sixty seconds, hands on the wheel, eyes closed."
        ),
        crew_dynamic=(
            "Steady, unflappable presence on the radio. Won't speak to anyone in the car "
            "for the first thirty seconds — 'the car's still introducing itself.'"
        ),
        weakness=(
            "Will not abandon a crew member to make an escape window. Has made this choice "
            "three times and gotten away with it twice."
        ),
        look=(
            "Tall lean Nigerian man in his late twenties: very short hair, thin gold chain, "
            "slightly amused expression. Dark hoodie under a fitted jacket. One hand resting "
            "on a steering wheel."
        ),
        signature_line='"Three seconds. Four. Five. Clear."',
    ),
    Character(
        id=14,
        name="Margot Vinter",
        skills={"driver": M, "inside_man": L},
        skill_scores={"driver": 6, "inside_man": 4},
        floor_cost=200_000,
        backstory=(
            "Daughter of an East German rally driver who defected with her in 1988. Grew up "
            "between Hamburg and Berlin, did club racing in her twenties, lost her license "
            "after the third DUI. Picked up freelance driving when no insurance company "
            "would take her."
        ),
        voice=(
            "Mid-Atlantic by way of West Berlin. Light, sardonic, never serious. "
            "Calls every traffic light a 'suggestion.'"
        ),
        motivation=(
            "Believes she is being punished by some larger force for the DUIs and that the "
            "only way out is enough money to make herself untouchable."
        ),
        quirk="Smokes a single clove cigarette before and after every drive. Never during.",
        crew_dynamic=(
            "Chatty on the way in, silent on the way out. "
            "The crew has learned not to interrupt the silence."
        ),
        weakness=(
            "Real intersections rattle her. Will refuse routes with more than six lights "
            "in the escape path."
        ),
        look=(
            "White woman in her late thirties: platinum-blonde hair in a short pixie cut, "
            "sharp cheekbones, thin scar through one eyebrow. Driving gloves, leather jacket. "
            "Unlit clove cigarette held loosely between two fingers. Half-smile, eyes amused."
        ),
        signature_line='"Lights are suggestions, darling. Brake lights especially."',
    ),
    Character(
        id=15,
        name="Dex Owusu",
        skills={"driver": M, "muscle": L},
        skill_scores={"driver": 5, "muscle": 4},
        floor_cost=125_000,
        backstory=(
            "Grew up in the Bronx, son of Ghanaian immigrants. Worked maintenance at a city "
            "bus depot for six years; learned mechanical work and pulled a couple of side gigs "
            "that got him noticed. Stayed in the work because the bus depot fired him."
        ),
        voice=(
            "Brooklyn-Ghanaian cadence, slow with sudden bursts. Doesn't curse. "
            "Says 'lord have mercy' when things go badly."
        ),
        motivation=(
            "Trying to save enough to start a small auto-repair shop with his cousin. "
            "Has been 'two more jobs away' for three years."
        ),
        quirk="Wears the same Mets cap on every job. Won't say where he got it.",
        crew_dynamic=(
            "Reliable, mid-tier presence. Doesn't volunteer for hero work; doesn't shirk "
            "grunt work. The crew tends to forget he's there until they need him to lift "
            "something heavy."
        ),
        weakness="Bad with computers, refuses to learn. Will hand off any tech task to whoever else is in the room.",
        look=(
            "Ghanaian-American man in his late thirties: short black hair, broad nose, "
            "full beard kept close-cropped. Mets cap pulled low, plain dark zip jacket. "
            "Work gloves tucked into a back pocket. Neutral expression, slight nod."
        ),
        signature_line='"Lord have mercy. Where do you want it?"',
    ),
    Character(
        id=16,
        name='Valentina "Val" Cruz',
        skills={"muscle": M, "inside_man": L},
        skill_scores={"muscle": 5, "inside_man": 5},
        floor_cost=200_000,
        backstory=(
            "Eight years as a Cook County corrections officer in Chicago — knew every shift "
            "pattern, every blind spot, every guard who'd look the other way for the right "
            "story. Left after a use-of-force review that went nowhere. Does asset recovery "
            "now, which is a polite way of saying she takes things back from people who "
            "don't want to give them."
        ),
        voice=(
            "Flat Chicago working-class. Short sentences. Doesn't explain herself twice. "
            "When she laughs it surprises people — loud and genuine, gone in a second."
        ),
        motivation=(
            "Supporting her mother and two younger sisters after her father's deportation. "
            "The repo work pays well. She doesn't think too hard about the rest."
        ),
        quirk=(
            "Scopes every room for the two exits and the one person who looks like trouble. "
            "Ranks them in her head before she's taken her coat off."
        ),
        crew_dynamic=(
            "Calm under pressure in a way that unnerves people who don't know her. "
            "The crew trusts her immediately. She takes longer to trust the crew."
        ),
        weakness=(
            "Corrections background means she reads people in authority as a known quantity "
            "— and occasionally underestimates the ones who don't fit the profile."
        ),
        look=(
            "Puerto Rican-American woman in her mid-thirties: dark hair pulled back tight, "
            "strong build, a small scar on her chin. Plain dark jacket over a fitted "
            "turtleneck. Arms at her sides, weight slightly forward. Still in the way "
            "that means she's about to move."
        ),
        signature_line='"I\'ve been on the other side of this door. Trust me."',
    ),
    Character(
        id=17,
        name='Priya "Patch" Iyer',
        skills={"hacker": M},
        skill_scores={"hacker": 7, "inside_man": 5},
        floor_cost=275_000,
        backstory=(
            "Ran security for a regional hospital network for nine years until she "
            "flagged a breach the board wanted buried. They fired her for 'policy "
            "violations' the week before her options vested. She's been freelancing "
            "ever since, and she keeps the termination letter laminated in her bag."
        ),
        voice=(
            "Precise and deadpan. Over-explains the thing she's about to do, then does "
            "it faster than anyone expects. Says 'noted' instead of 'okay.'"
        ),
        motivation=(
            "Paying for her father's memory-care facility, month to month. She prices "
            "every job against how many weeks it buys him."
        ),
        quirk="Labels everything — cables, drives, people. Narrates her keystrokes under her breath.",
        crew_dynamic=(
            "Reliable and a little preachy about opsec. Will redo a sloppy crew "
            "member's work without being asked and mention it exactly once."
        ),
        weakness=(
            "Rigid. Brilliant on a plan she's prepped; rattled when the job deviates "
            "and she has to improvise off-script."
        ),
        look=(
            "South Asian woman in her late thirties: dark hair in a practical bun, "
            "rectangular glasses, a worn field jacket over a hospital-lanyard habit of "
            "clipping things to her collar. Calm, slightly impatient expression."
        ),
        signature_line='"Give me four minutes and a clean port. Noted."',
    ),
    Character(
        id=18,
        name='Nadia "Relay" Sokolov',
        skills={},
        skill_scores={"hacker": 8, "driver": 6},
        floor_cost=0,
        backstory=(
            "Estonian e-residency fraudster who learned to drive the hard way — running her "
            "own exfil when a job soured and the wheelman never showed. Decided she'd rather "
            "be the one who can do both than trust a stranger with the last ten seconds."
        ),
        voice=(
            "Clipped and technical. Narrates latency and ETAs in the same breath. "
            "Calls every plan 'the relay.'"
        ),
        motivation=(
            "Building an off-grid cabin with a server rack she'll never have to leave. "
            "Counts jobs in months of solitude bought."
        ),
        quirk="Keeps a stopwatch running on every job and checks it mid-sentence.",
        crew_dynamic=(
            "Trusts the plan over the people. Cold until you hit your marks, then loyal."
        ),
        weakness="On a comms blackout she freezes for a beat — she can't act on a network she can't see.",
        look=(
            "Wiry woman in her early thirties: shaved-side undercut, fingerless gloves, an "
            "earpiece always in. Restless eyes that track exits and signal bars at once."
        ),
        signature_line='"Window\'s nine seconds. I\'m already in, and the car\'s already moving."',
    ),
    Character(
        id=19,
        name='Marko "Crowbar" Dvořák',
        skills={},
        skill_scores={"safecracker": 8, "muscle": 6},
        floor_cost=0,
        backstory=(
            "Czech demolition foreman who learned the fastest way through a wall is knowing "
            "exactly where it's weak. Did a stretch for an 'industrial accident' that the "
            "insurers, and only the insurers, believed was an accident."
        ),
        voice="Low and unhurried. Fond of construction metaphors. Rarely finishes a coffee.",
        motivation=(
            "A quiet retirement and a workshop. Resents that he's best known for the loud part."
        ),
        quirk="Taps a wall three times and listens before he ever touches a vault.",
        crew_dynamic=(
            "Gentle giant. Moves people out of the danger zone without being asked or thanked."
        ),
        weakness="Too patient — keeps working a lock well past the smart moment to walk away.",
        look=(
            "Broad Czech man in his fifties: grey stubble, scarred knuckles, a contractor's "
            "pencil tucked behind one ear. Moves slowly, like the floor might give."
        ),
        signature_line='"Everything\'s got a seam. Give me a minute to find it."',
    ),
    Character(
        id=20,
        name='Renata "Echo" Salazar',
        skills={},
        skill_scores={"inside_man": 9, "hacker": 5},
        floor_cost=0,
        backstory=(
            "Former corporate-intelligence interrogator who realized a forged badge and a warm "
            "smile got her more than any subpoena. Left the firm the day they tried to make "
            "her testify against the wrong people."
        ),
        voice=(
            "Warm and precise. Mirrors your cadence back at you within a sentence so you feel "
            "understood. Never raises her voice."
        ),
        motivation=(
            "Proving she was always the smartest person in rooms that were built to overlook her."
        ),
        quirk="Repeats your last two words back as a question to keep you talking.",
        crew_dynamic="Runs the human layer like a switchboard. The crew's default face.",
        weakness="Can't resist a genuinely clever mark — slows down to enjoy the duel.",
        look=(
            "Latina woman in her forties, impeccably ordinary — the most forgettable person in "
            "any lobby, entirely by design. Soft eyes that miss nothing."
        ),
        signature_line='"...by design? Tell me more about \'by design.\'"',
    ),
    Character(
        id=21,
        name='Tunde "Diesel" Bakare',
        skills={},
        skill_scores={"muscle": 9, "driver": 6},
        floor_cost=0,
        backstory=(
            "Ex-bouncer and amateur strongman, Lagos by way of Manchester. Drove armored "
            "transport for eight years before he worked out he understood the trucks better "
            "than the people paying to fill them."
        ),
        voice=(
            "Booming and cheerful. Defuses a room with a joke right up until the exact second "
            "he doesn't. Goes quiet when it's gone wrong."
        ),
        motivation=(
            "Bankrolling his little sister's haulage company — fully legit, his name nowhere on it."
        ),
        quirk="Hums highlife under his breath when a job's going well.",
        crew_dynamic="The morale engine. Will physically put himself between the crew and trouble.",
        weakness="Soft-hearted — hesitates a half-second before hurting anyone who reminds him of family.",
        look=(
            "Enormous Nigerian-British man in his late thirties: easy grin, a single gold tooth, "
            "hands like dinner plates resting on a steering wheel."
        ),
        signature_line='"Get in the van. I said get in the *van*."',
    ),
]

ROSTER: list[Character] = [_with_derived(c) for c in _RAW_ROSTER]
ROSTER_BY_ID: dict[int, Character] = {c.id: c for c in ROSTER}
