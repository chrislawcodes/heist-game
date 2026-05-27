# Heist Game — Design Document

*Working draft*

## Concept

You're the boss of a heist crew. You set the strategy, then you watch your crew work.

You don't pick your crew member by member. You don't pick the job. You don't play the heist yourself. You write a strategy — what kind of heist you want, what kind of crew, what kind of approach — and the AI does everything else: hires the crew within your budget, picks the job, runs the heist scene by scene.

Your skill is in writing strategy that produces the heist you wanted. The game produces a watchable narrative — each heist plays out as a sequence of scenes you can read or share.

---

## Principles locked across all phases

These design commitments hold from Phase 1 through Phase 4.

**The human sets intent. The AI executes.** The player writes one input: a strategy prompt. The Heist AI handles every downstream decision: bidding for crew, picking the job, deciding which character handles each scene, making in-the-moment choices.

**The strategy prompt is the player's full expression of intent.** It describes the kind of heist they want, what kind of crew, what kind of approach, their risk tolerance, their priorities.

**Reasoning is visible.** Every Heist AI decision is accompanied by short reasoning. The player should trace each action back to their strategy and understand why it happened. The visible reasoning is the central spectator experience.

**Actions have concrete consequences.** Each beat is a real event with real stakes — a safe cracked, an alarm tripped, a guard bribed, a character caught. Nothing is abstract bookkeeping.

**Hidden depth generates drama.** Each location has visible information (defense profile, reward range) and hidden depth (specific complications, reward amount). The system rolls hidden depth at the start of each play; surprises emerge during execution.

**Every bonus comes with a test.** Hidden depth never offers pure upside. Every opportunity is paired with a cost: additional challenge, time pressure, exposure risk, or moral weight. The Heist AI decides whether to pursue, surfacing the strategy prompt at the moment.

**Jobs never obsolete each other.** Once a job is attempted, it's resolved.

**Missing a skill in a present challenge means failure.** No improvisation around skill gaps. Crew composition has real teeth.

**System and Heist AI have distinct roles.** The system handles all deterministic mechanics: bid validation, skill-vs-challenge resolution, hidden depth rolls, scene order, state tracking, reward calculation. The Heist AI makes creative and interpretive decisions: reading the prompt, picking the team, picking the job, assigning characters to scenes, making decisions at decision points, narrating.

---

## Core mechanics (all phases)

### Skills and challenges

Five skills, each matched to a challenge category:

| Skill | Challenge Category |
|-------|-------------------|
| Hacker | Electronic (cameras, alarms, locks, networks) |
| Safecracker | Physical (vaults, safes, structural barriers) |
| Muscle | Confrontation (guards, armed response) |
| Inside Man | Social (witnesses, bribery, blending in) |
| Driver | Escape (the final beat) |

Hacker, Safecracker, Muscle, and Inside Man are "active" skills exercised during the body of the heist. Driver determines the escape's outcome.

### Skill levels (1–10 scores under public buckets) — Phase 4+

Every skill and every challenge has a hidden **1–10 score**. The familiar
**bucket** is just a label derived from the score:

`0 = None, 1–3 = Low, 4–7 = Medium, 8–10 = High`.

**Character scores are public** (you see "Safecracker 9"). **Location challenge
scores are fogged** — you see the bucket as an estimate and scout to learn the
exact number (see Phase 4). *(Phases 1–3 used bare buckets; the 1–10 model
shipped in Phase 4 and supersedes them.)*

### Challenge levels

Each active challenge at a location has a hidden 1–10 score whose bucket is
**None / Low / Medium / Hard**. How high within the bucket it rolls depends on
the job's **tier** (tier-1 Hards roll ~8; tier-3 Hards roll 9–10).

### Skill vs. challenge interaction (computed by the system)

The crew's **effective score** in a category is the highest score any assigned
member has, **+1 if two or more members have the skill** (capped at 10). The
system grades by the **margin** = effective score − challenge score:

| Margin (eff − challenge) | Outcome |
|--------------------------|---------|
| No challenge (score 0) | Pass — clean |
| **≥ +2** | Pass — clean |
| **0 or +1** | Pass — but **+1 heat** (a squeak) |
| **−1 to −3** | **Fail** — objective missed, **+1 heat** |
| **≤ −4** | **Fail** — **+1 heat**, and a crew member is **caught** |

Heat rises by 1 on anything that isn't clean. Because effective score caps at
10, a **tier-3 Hard (9–10) can only ever be squeaked**, so the hardest jobs
always cost heat. A ≤−4 shortfall catches the member who led the attempt
(otherwise the lowest-cost assigned member), out for the rest of the run.

So a published "High" (true 7) can *lose* to a "Hard" (true 9): the bucket is
an estimate, not a contract — which is what makes scouting matter.

### Collaboration

Two or more characters with the same skill act at **the best member's score + 1
point**, capped at 10. (Two Medium specialists — say two 7s — reach an
effective 8, enough to *squeak* an easier Hard; they can't manufacture a 10.)

### Failure consequences

Failure is graded into the table above — there's no separate "core scene aborts the heist" rule. A challenge that isn't cleanly beaten always adds **+1 heat**; a 2+-level shortfall also **catches a crew member** (out for the rest of the run, weakening later scenes). Heat raises the escape difficulty (see below). After any failure — and in fact at **any scene** — the Heist AI may choose to **abort** and head straight for the escape rather than push on for the rest of the loot.

### The escape

Every heist ends with an escape scene. Escape difficulty = the job's escape modifier **+ accumulated heat**; the crew's best Driver skill (no Driver = treated as Low, so a driverless escape is viable only at low heat) must be **≥** that difficulty. A clean getaway means everyone still free leaves with the secured take. **If the escape fails, one random free crew member is caught** — the rest still get away with what they secured. The take is lost entirely only if the whole crew ends up caught.

### Characters

Each character has:

- Name (with optional nickname)
- One or more skills, each a **1–10 score** (public; bucket derived)
- Floor cost (derived from the scores — see pricing)
- Personality: a paragraph (80-150 words) describing voice, motivations, quirks, history

The roster is **21 characters**. Each is a unique person; in multi-player phases each character is on at most one crew per game.

### Character pricing — Phase 4+ (convex per-score curve)

A character's floor cost is derived from its scores, not a points bucket:

`floor_cost = $100,000 seat + Σ premium(score)`

The premium rises steeply at the top so buying a near-perfect specialist is a
real sacrifice:

| Score | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|-------|---|---|---|---|---|---|---|---|---|----|
| Premium | $10k | $15k | $20k | $25k | $50k | $100k | $175k | $325k | $600k | $1.1M |

So a lone Safecracker-8 ≈ $425k; a Safecracker-10 ≈ $1.2M; a Hacker-10 +
Driver-2 ≈ $1.215M. *(Phases 1–3 used a flat 2/3/4-point table; the curve
shipped in Phase 4.)*

### Locations (jobs)

Each location has:

- Name and flavor description
- Reward range
- Active challenge profile across Electronic, Physical, Confrontation, Social
- Escape difficulty modifier (most locations: None)
- Hidden depth pool

### Hidden depth

Each location has:

- **Complications and opportunities** (4-6 per location): surprises that surface during the heist. Per the "every bonus comes with a test" principle, opportunities are never pure upside.
- **Loot per scene:** loot is distributed across the heist's scenes — each loot-bearing scene banks its value when the crew clears it. The published reward range is the rough total on offer.

At the start of each play, the system rolls one complication-or-opportunity. Loot is then secured scene by scene as the heist plays out (see Reward calculation).

### The draft (Heist AI bidding)

The Heist AI receives the player's prompt and the published roster with floor costs. It produces a priority-ordered bid allocation totaling ≤ bankroll.

**Bid resolution (system):**

In Phase 1 single-player, all bids fire. Hired characters total the player's spend. If bids don't fill 4 slots, the Heist AI fills remaining slots from the unbid roster using the prompt's guidance — and the system validates affordability.

In Phase 2+ with contention, contested characters go to the highest bidder; the Heist AI's priorities determine which bids fire when crew slots are full.

### Heist execution architecture

A heist runs through a scene loop driven by the system. The system structures the heist; the Heist AI populates each scene.

**System responsibilities:**
- Roll hidden depth at heist start
- Determine scene order based on the job's profile and hidden depth
- For each scene: present to the Heist AI which scene this is, ask for character assignment
- Resolve challenges (skill vs. difficulty)
- Track state across the heist
- Present decision points to the Heist AI when they arise
- Resolve the escape
- Calculate final reward

**Heist AI responsibilities in the heist loop:**
- Assign characters to each scene as the system presents it
- Make decisions at decision points (e.g., pursue the bonus or skip)
- Narrate each scene with the system-determined outcome

**Scene structure:**
- Scene 1: Setup/approach (always)
- One scene per Medium or Hard challenge present (Low challenges may be folded in passing)
- One scene per hidden depth element when it triggers
- Penultimate scene: transition to exit
- Final scene: escape

This produces approximately 8 scenes for most jobs.

### Reward calculation

The take is the **loot the crew secured** during the run. Loot is spread across scenes, and each loot-bearing scene banks its value when the crew clears it (clean or squeak); pursued bonuses add their value too. The take is **realized only if at least one crew member escapes** — if the whole crew is caught, it's lost.

Because loot can sit mid-heist, the AI's choice to push on for more or **bail with what it's grabbed** is a real risk/reward decision: a clean partial run can beat a greedy bust that piles on heat and loses people at the escape.

---

## Phase 1 — Single player, single job

**Goal:** Validate that watching a Heist AI act on a player-written strategy produces engaging play.

### Phase 1 setup

- One human player
- Bankroll: **$2,000,000**
- A slate of 3 jobs
- A roster of 16 characters
- Player submits only a strategy prompt
- Heist AI selects crew (via bidding), selects job, runs the heist

### Phase 1 roster (locked)

| # | Name | Skills | Pts | Floor |
|---|------|--------|-----|-------|
| 1 | Marcus "Prodigy" Renault | Hacker H, Driver L | 4 | $1,100,000 |
| 2 | Sasha Kuznetsova | Hacker M | 2 | $200,000 |
| 3 | Eli "Owl" Park | Hacker L, Inside Man L | 2 | $200,000 |
| 4 | Vance "The Wall" Tobin | Muscle H | 3 | $700,000 |
| 5 | Carla Reyes | Muscle M, Driver L | 3 | $400,000 |
| 6 | Big Mike Donato | Muscle L, Driver L, Inside Man L | 3 | $400,000 |
| 7 | Lin "Closer" Chen | Inside Man H, Safecracker L | 4 | $1,100,000 |
| 8 | Theo Kapoor | Inside Man M | 2 | $200,000 |
| 9 | Pearl Sutton | Inside Man M, Muscle L | 3 | $400,000 |
| 10 | Rook Ferreira | Safecracker H | 3 | $700,000 |
| 11 | Jolene "Jo" Hayes | Safecracker M, Hacker L | 3 | $400,000 |
| 12 | Nestor Bly | Safecracker M, Hacker L | 3 | $400,000 |
| 13 | "Slim" Adesanya | Driver H | 3 | $700,000 |
| 14 | Margot Vinter | Driver M, Inside Man L | 3 | $400,000 |
| 15 | Dex Owusu | Driver M, Muscle L | 3 | $400,000 |
| 16 | Valentina "Val" Cruz | Muscle M, Inside Man L | 3 | $400,000 |

**Roster design notes:**
- One High specialist per skill: Marcus (Hacker), Vance (Muscle), Lin (Inside Man), Rook (Safecracker), Slim (Driver). Marcus and Lin are the two 4-point premiums at $1,100,000; Vance, Rook, and Slim are pure single-High hires at $700,000.
- The other eleven characters are Medium/Low generalists, so most crews pair one premium specialist with cheaper support.
- Two Medium Inside Men (Theo + Pearl) enable the collaboration substitution that makes the Museum doable.
- Inside Man is the deepest skill on the bench (7 characters across all levels); Safecracker the thinnest (4).
- Personalities fully authored — backstory, voice, motivation, quirk, look, and signature line for all 16.

### Phase 1 strategic landscape

With $2,000,000 budget and the pricing:
- Maximum 2 Highs per crew
- Two premium 4-point Highs (Marcus + Lin) = $2,200,000 base, impossible
- Standard premium crew is two pure-specialist Highs ($1,400,000) + supports

### Phase 1 job slate (locked)

#### The Museum Gala

**Reward:** $1.5M – $4M
**Profile:** Electronic Medium | Physical Hard | Confrontation Low | Social Hard
**Escape modifier:** 1 — event venue with cameras and security; 300 guests provide cover but exits are watched

A black-tie charity gala at the city's biggest art museum. The Renaissance wing is being feted with a one-night exhibition, and the centerpiece is a diamond on loan from a Saudi prince. The vault is state-of-the-art. The gala is packed with guests, photographers, and event security — blending in is the whole challenge.

**Strategic puzzle:** Requires High Safecracker AND High Inside Man. Lin + Rook + 2 supports = $2,200,000 (over budget). The Museum is doable through **collaboration**: Theo + Pearl (Medium + Medium = High effective Inside Man, $600K) + Rook ($700K) + 1 support = $1.5M–$1.7M. The Heist AI must recognize the collaboration substitute or fail to attempt the job.

**Hidden depth — complications/opportunities:**
1. Diamond in a temporary display case with backup proximity alarm. Physical drops to Medium, new Low Electronic challenge. *(Opportunity-with-cost.)*
2. Off-duty detective at the gala. New Medium Social challenge. *(Complication.)*
3. Prince's private security creates friction with museum guards. Confrontation rises to Medium. *(Complication.)*
4. Emerald necklace also stealable. Adds $1M-$2M but requires additional Physical challenge and time pressure. *(Bonus-with-cost.)*
5. Gala running long. More time, but extended presence raises Social to Hard if used. *(Opportunity-with-cost.)*
6. Undisclosed biometric locks. Electronic jumps to Hard. *(Complication.)*

**Reward amounts:**
- Standard valuation: $2.5M
- Minor piece: $1.8M
- Top-of-market centerpiece: $3.8M

#### The Armored Car

**Reward:** $800K – $2M
**Profile:** Electronic Low | Physical Medium | Confrontation Hard | Social None
**Escape modifier:** 2 — police pursuit is essentially guaranteed before the job is done

Weekly cash transfer between bank branches. Two armed guards in the cab, one in back. The truck is a moving vault. No cameras, no witnesses on the right stretch of road. Guards are trained, armed, and expect trouble.

**Strategic profile:** Requires High Muscle. Vance ($700,000) is the only High Muscle option.

**Hidden depth — complications/opportunities:**
1. Third guard in cargo compartment. *(Complication.)*
2. Truck ten minutes early. *(Complication.)*
3. School bus at ambush point. *(Complication.)*
4. Extra deposit. Bonus $500K-$1M, extended loading time. *(Bonus-with-cost.)*
5. Rookie guard. Confrontation drops to Medium but rookie panic unpredictable. *(Opportunity-with-cost.)*
6. Police cruiser on parallel street. *(Conditional complication.)*

**Reward amounts:**
- Standard: $1.4M
- Light load: $900K
- Heavy day: $1.9M

#### The Corporate Server Farm

**Reward:** $3M – $8M (industrial espionage)
**Profile:** Electronic Hard | Physical Medium | Confrontation Low | Social Medium
**Escape modifier:** 1 — corporate campus can lock down exits on alarm

A pharmaceutical company's research server room. The target is the formula on the servers. Building layered with electronic security: biometric locks, face recognition, network intrusion detection. The server room has a significant physical lock. Two perimeter guards.

**Strategic profile:** Requires High Hacker. Marcus ($1,100,000) is the only High Hacker.

**Hidden depth — complications/opportunities:**
1. Late-night research team in adjacent lab. Social jumps to Hard. *(Complication.)*
2. CEO's office wall safe. Bonus $1M-$3M but Medium Physical challenge and time exposure. *(Bonus-with-cost.)*
3. New network monitoring software. Electronic becomes very hard. *(Complication.)*
4. Janitor's keycard left in door. Skip one Electronic challenge but janitor notices soon. *(Opportunity-with-cost.)*
5. Earlier guard shift change. Window shorter. *(Complication.)*
6. Server moved to executive's office. *(Complication.)*

**Reward amounts:**
- Standard formula: $6M
- Early-stage research: $3.5M
- Late-stage with patents: $7.8M

---

## Phase 1 architecture: System and Heist AI

### Player input

Only the strategy prompt. Free-form text, target 250-500 words, covering crew preferences, job preferences, risk tolerance, behavioral guidance.

**Default test prompt for Phase 1:**

> "I want to run a clean, professional heist with a balanced crew. Pick whichever job fits the crew best — I trust your judgment. Build me a team that can handle whatever comes up: I want at least one specialist in each area we'll need, with backup capability through secondary skills. Risk tolerance: moderate. Pursue bonus opportunities only when they're clearly worth it. Don't take unnecessary chances. If something goes sideways, prioritize getting out clean over maximizing the take. I want a Driver — I don't want to be running on foot."

### Heist AI responsibilities

The Heist AI is a single agent serving multiple roles:

1. **Drafting:** Read the prompt and the roster. Produce a priority-ordered bid allocation totaling ≤ $2,000,000. Bids must be at or above floor costs.
2. **Job selection:** Read the prompt and the assembled crew. Pick the most appropriate job from the slate. Justify the choice.
3. **Casting summary:** Write a transparent summary explaining the bid logic, the crew assembled, and the job selected.
4. **In-scene decisions during execution:** As the system presents each scene, decide which crew member(s) act, and at decision points, decide what to do (e.g., pursue a bonus or skip).
5. **Narration:** Write each scene's prose with character voice, dialogue, and visible reasoning.

### System responsibilities

The system is deterministic logic:

1. **Bid validation:** Confirm bids fit budget and are at or above floor.
2. **Crew assembly:** Process bids, mark hired characters. If the Heist AI's bids leave the crew incomplete, prompt the AI to fill remaining slots from the unbid roster.
3. **Skill validation:** Check which jobs the assembled crew can credibly attempt (has needed Hard-challenge coverage).
4. **Hidden depth roll:** At heist start, roll one complication/opportunity and one reward amount from the selected location's pools.
5. **Scene structure:** Generate the scene order based on the job's profile and the hidden depth elements surfacing.
6. **Scene presentation:** Present each scene to the Heist AI in order, asking for character assignment.
7. **Challenge resolution:** Compute skill-vs-challenge outcomes (success / failure) and pass results back to the Heist AI for narration.
8. **State tracking:** Track failures, decisions made, hidden depth resolved.
9. **Decision presentation:** When the scene includes a decision point (e.g., bonus-with-cost), present the decision and parameters to the Heist AI.
10. **Escape resolution:** Compute escape difficulty from accumulated state, resolve Driver skill against it, return result.
11. **Reward calculation:** Multiply hidden-depth reward by escape success (0 or 1), add successful bonus pursuits.

### The scene loop

For each scene:

1. System tells Heist AI: scene number, scene type (setup / challenge / hidden depth / exit / escape), the challenge being addressed (if any), the challenge level, any context.
2. Heist AI: picks which crew member(s) act in this scene.
3. For decision scenes (hidden-depth bonus): system presents the decision. Heist AI decides whether to pursue before the outcome is resolved.
4. System: computes outcome using skill vs. challenge.
5. System tells Heist AI the outcome (success / failure / caught).
6. If the outcome is a failure: system asks the Heist AI — abort now (escape with what's secured) or push on? Heist AI decides and gives reasoning. `state.aborted` is only set if the AI chooses to abort.
7. Heist AI: narrates the scene incorporating the outcome and the abort decision (if any).

### Model and temperature

- Heist AI runs on a strong reasoning model
- Temperature: moderate (consistent enough for reliable interpretation, varied enough for creative narration)
- Same Heist AI instance handles all roles in a heist (drafting, job selection, scene decisions, narration), maintaining context throughout

---

## What's not in Phase 1

- Other human players
- Crew member contention
- Multi-job structure
- Character persistence beyond one heist
- Cops
- Scouting

### The question Phase 1 answers

Does the core loop — write strategy, Heist AI handles everything, watch heist unfold — produce engaging play? Can a player change their prompt and see meaningfully different play?

---

## Phase 2 — Multiplayer, single job

**Goal:** Validate the blind-bid draft with real contention.

- 2 players is the launching configuration (the auction supports more)
- "Players" are realized as competing strategy prompts, each driven by its own
  Heist AI. A **real multi-human lobby** (people joining a shared game) is **not**
  needed here — it's deferred to **Phase 8**.
- Shared roster — each character ends up on at most one crew
- Bids are contested; the casting reveal shows who fought over whom (the
  auction-floor UI)
- Each crew runs its heist in parallel (a different seed per crew). A formal
  "who won" score comparison is **not yet built** — takes are shown per crew.

### Phase 2 bid resolution (as built)

> Implemented in `heist/auction.py` (`run_auction`). This supersedes an earlier
> "two blind rounds + random fill" draft — the shipped design is iterative.

The auction runs up to **8 blind rounds**, all on the same **$2,000,000-per-player**
bankroll and a **crew size of 4**, drawing from one shared roster pool. Only
**winning** bids cost money; losing and tied bids are free.

**Each round**, every still-active player either submits a bid list
`[{character_id, bid, rationale}]` or **passes**. A bid must be ≥ the
character's floor cost, a player's bids must total ≤ their remaining bankroll,
and a player may bid on at most `4 − (characters already won)` characters.

**Resolution (per round):**
- For each character anyone bid on, take the highest bid.
- **Highest unique bid wins** — the winner pays that amount, the character joins
  their crew and leaves the pool.
- **Ties** (two or more players at the top amount) → no one wins the character,
  all tied bids are refunded, and the character **stays in the pool**, biddable
  again in later rounds.
- Outbid players who didn't pass stay active and may bid again next round.

**A player goes inactive** when their crew is full (4), they pass, their
bankroll falls below the cheapest floor cost, or the pool empties. The auction
ends when no active players remain.

**No random fill.** A player who never fills all four slots simply runs a
smaller crew (more gaps in the heist). Each round's outcome — winners, ties,
bankrolls, crews — is emitted as it resolves; that stream is the data behind the
casting reveal / auction-floor animation.

**Why no `priority` field in bids:** tie-breaking is handled by the
refund-on-tie + nobody-wins-on-tie rules, so bids are ordered by amount alone.

### Phase 2 algorithmic core lives in `heist/auction.py`

`run_auction(ais, strategies, …) → AuctionResult` orchestrates the round-by-round
bidding loop and returns each player's final crew, spend, and a per-round record
(`AuctionRoundRecord`). It drives the Heist AIs' bid turns directly and emits
per-AI and broadcast events so the UI can animate the auction floor. The pure
mechanics — validating bids, resolving winners/ties — are split into small
helper functions that are unit-tested independently.

---

## Phase 3 — Multi-job campaigns

**Goal:** Turn the game into a heist saga — a sequence of jobs where the crew
you build, the money you bank, and the heat you draw all carry forward.

**Status:** Designed, not built. Implementation is planned but deferred (see
"Phasing" below). The hidden-information / scouting layer that pairs with the
heat mechanic lands in **Phase 4**.

### The campaign loop

A campaign is **10 rounds**. Each round is one heist. Between rounds, state
persists:

- **Standing crew.** You draft a crew **once**, at the start of the campaign,
  and keep it across all 10 rounds. Crew are lost to capture (below) and
  re-hired from accumulated loot. This is what makes 10 rounds a *saga* and not
  10 disconnected heists. (Chose this over "re-draft fresh each round.")
- **Bankroll & loot.** Bankroll persists; successful takes accumulate. Loot
  funds re-hiring and, campaign-permitting, upgrading the crew between rounds.
- **Notoriety (campaign heat).** A slow-burn track, distinct from in-heist
  heat — see "Heat across a campaign" below.

**Player intent (MVP):** one campaign-level strategy prompt up front. The Heist
AI auto-pilots all 10 rounds — picking the job, assigning crew, making in-scene
calls — against that single prompt. A per-round "adjust orders" step is a
post-MVP option.

**Win condition:** survive 10 rounds; score by total loot banked. The campaign
can **end early** on a full crew wipe or bankruptcy (can't afford to field a
crew).

### Standing crew & attrition

The standing-crew model needs a crew-loss mechanic, which falls out of the
existing escape resolution — no new system required:

- **Failed escape → capture.** A failed escape (the per-heist knife edge —
  below) means the crew on the getaway are caught and removed from the standing
  crew. This finally gives a blown escape *lasting* teeth.
- **Re-hire from loot.** Between rounds, accumulated loot backfills losses and
  replaces specialists.
- The chain: messy job → notoriety ↑ and/or failed escape → crew captured →
  re-hire from loot → next round.

### Heat across a campaign

In-heist heat is a knife edge and must stay one. The escape math
(`escape difficulty = escape_modifier + heat`, against a Driver skill that caps
at 3) leaves almost no headroom:

| Best driver | Job mod 1 | Job mod 2 |
|---|---|---|
| High (3)       | survives heat ≤ 2 | survives heat ≤ 1 |
| Medium (2)     | survives heat ≤ 1 | only heat 0 |
| Low / none (1) | only heat 0 | fails even at heat 0 |

So **persistent heat must never touch the escape roll** — carrying even 1 heat
into the next round as a flat escape tax would death-spiral the campaign. (Do
not re-propose an escape tax; this table is why.)

Instead, campaign heat is **notoriety** — a threshold track that pressures the
*world around* the next heist, never the escape dice:

| Notoriety | Effect (none of it touches escape math) |
|---|---|
| Low (0-2)     | Normal. Full slate, normal crew prices. |
| Medium (3-5)  | High-value jobs pulled from the slate; crew floor costs rise. |
| High (6-8)    | Between rounds, a crew member is picked up — a second attrition source. |
| Critical (9+) | A raid: forced lie-low round or campaign over. |

- **Generation:** a round's in-heist heat (how loud the job was) rolls up into
  notoriety.
- **Bleed:** notoriety decays each quiet round. A clean job cools you off; a
  messy one spikes you.
- **Why it works with one prompt:** the Heist AI picks the job each round. Feed
  it current notoriety and a hot campaign naturally steers it toward quieter,
  lower-value jobs to cool down — the strategic loop emerges from per-round
  picks even though the player prompted once.

In-heist heat is unchanged from Phases 1-2 (accumulates from non-core failures,
affects only that heist's escape). Notoriety sits above it; the two tracks are
distinct.

Open tuning knobs (settle against a stub campaign): threshold boundaries
(3/6/9?), decay rate (−1 to −2 per quiet round?), and whether a *successful*
high-value heist also raises notoriety.

### Job slate over a campaign

Locked principle: jobs don't repeat once attempted. 10 rounds therefore needs a
**pool larger than the slate** (~12-15 jobs). Each round shows a rolling slate
(e.g. 3) drawn from the pool minus anything already attempted — so fresh jobs
"come up" each round. Notoriety gates the slate (high notoriety pulls the
high-value jobs). Job **tiers** (low-tier early, high-tier unlocked later) keep
round 10 from feeling like round 1 — tiers are a post-MVP polish.

### Forward-compatibility seam for Phase 4

When the campaign is built, **store a 1-10 score for every skill and challenge
in the data model and derive the Low/Med/High buckets from it.** Resolution in
Phases 1-3 keeps using the bucket (identical behavior today). This makes Phase
4's hidden-score / scouting layer a *reveal* feature on existing data rather
than a schema migration plus re-authoring of all 16 characters and the job
pool. Cheap now, saves real pain later. (See Phase 4.)

### Phasing (when we build it)

| Phase | Ships | Verified by |
|---|---|---|
| **3a — Campaign core** | `Campaign` state; settle-round (bank loot, notoriety gen/decay, capture, re-hire, early-end); split `run_heist` into draft-once + run-one-job; `run_campaign` loop; CLI `run-campaign --agent stub` | Unit tests + a full 10-round stub campaign in the terminal |
| **3b — Job pool** | Expand pool to ~12-15; per-round rolling slate; notoriety-gated availability | Stub campaign: no attempted-job repeats, real choice each round |
| **3c — Persistence/resume** | Round-aware snapshots; campaign-level game record; mid-campaign recovery | Kill server mid-round, restart, campaign continues |
| **3d — UI** | Persistent campaign HUD (round X/10, bankroll, loot, crew, notoriety); loop job→heist→round-summary ×10; round-aware nav/replay; round-summary + campaign-epilogue pages | Watch/replay a full campaign in the browser |
| **3e — Escalation (post-MVP)** | Job tiers; between-round re-prompt; notoriety-threshold polish; richer capture flavor | — |

Ordering de-risks the architecture before the UI/content spend: 3a is the
keystone (the campaign state object + the draft-once/run-many split). 3b can run
alongside 3a (content vs. plumbing). 3c precedes 3d because the UI consumes the
round-tagged event stream 3c finalizes. A 10-round run is ~30-90 min of wall
clock (15-20 sequential AI calls per round at ~10s pacing), so 3c (resume) and
the replay model are load-bearing, not optional.

---

## Phase 4 — Hidden location info & scouting

**Goal:** Give the player real intelligence work, and make the heat mechanic
bite. Today the whole slate is laid bare — profile, escape modifier, reward
range, hidden-depth pool. Phase 4 fogs the precise numbers and lets the player
pay to learn them. This is the planned counterweight to the steep heat cascade
(MEMORY): scouting is how a smart player de-risks before committing.

**Status: Built.** Score-based resolution, scouting, and the contested job
board shipped in Phase 4. The notes below are the design rationale; where this
section once said "to define," the **As built** subsection records what shipped.

### As built (what actually shipped)

- **1–10 scores under public buckets.** Boundaries `1–3/4–7/8–10`. Character
  scores are public; only **location** challenge scores are fogged.
- **Score-margin resolution** (clean ≥2 / squeak 0–1 / fail −1…−3 / caught ≤−4),
  not a binary contest. Collaboration = best score **+1 point**, capped at 10.
- **Convex pricing** (`$100k seat + Σ premium(score)`); see Character pricing.
- **Scouting** is a free, per-round, pre-commit intel phase: each crew gets
  `crew size + best-driver bonus` free probes; **one probe reveals a location
  challenge's exact 1–10 score**. (The planned narrowed-range middle tier and a
  $100k paid-overflow probe were *not* built — scouting is free-probes-only, and
  the reward range is public, not scouted.)
- **Tiered challenge bands.** Each job has a tier (easy/med/hard/elite → 1/2/3)
  that sets how high its Hards roll; tier-3 Hards roll 9–10 (squeak-only).
- **Contested job board.** A pool of ~50 jobs; each round shows a shared
  **board of 8** drawn from the pool minus globally-consumed jobs. Up to 4 teams
  pick **trailing-team-first** (lowest banked picks first — anti-snowball); a job
  is **consumed for everyone** once attempted. Board composition is gated by
  campaign progress (early boards skew cheap-to-mid, jackpots unlock late) plus
  random wild slots, with an affordable-minimum so no team is starved.
- **Reward climbs with difficulty,** decoupled-with-slack: floor ~$1M (every
  board job worth contesting), take rises with Hard-count then tier, and the two
  elite 4-Hard jobs are the **$15–18M jackpots** you bank across rounds to
  afford. 1–2 deliberate "edge" jobs sit off-trend (a bargain, a trap) for a
  scout to find.

### Hidden scores under public buckets

Every skill and every challenge has a true **1-10 score**; only its **bucket**
is published:

- Skills: `0 = None, 1-3 = Low, 4-6 = Med, 7-10 = High` (boundaries tunable).
- Challenges: `0 = None, 1-3 = Low, 4-6 = Medium, 7-10 = Hard`.

So a published "High" safecracker could be a 7 or a 10; a "Hard" vault could be
a 7 or a 9. **The bucket becomes an estimate, not a contract.**

### Resolution (option A — true scores decide)

Resolution reads the true scores and stays **fully deterministic**:

> `effective_skill_score ≥ challenge_score → success`

All the uncertainty is in the *inputs*, not in dice. The outcome is fixed the
moment scores are set; the player simply doesn't *know* it until they scout or
attempt. This preserves "the system owns deterministic mechanics" while
delivering the fog, and makes scouting a clean act of **buying down uncertainty
about a fixed answer**.

Consequence: a published "High" (true 7) can *lose* to a "Hard" (true 9), and a
"High" (10) beats a "Hard" (7). This **supersedes the Phase 1-3 model** — the
graded bucket comparison (clean / squeak / fail / caught) becomes a score-vs-score
contest, and "Hard requires High" now depends on the true numbers. Recorded here
deliberately; the locked list in "Core mechanics" remains true for Phases 1-3.

Balancing lever: a fully-scouted player has perfect information, so scouting
must cost enough (money / time / heat) that buying perfect info is rarely worth
it.

### The reveal ladder ("the more you scout, the more you get")

Scouting is a dial, not a switch:

| Tier | What you learn | Cost |
|---|---|---|
| **0 — published** | The bucket | free |
| **1 — light scout** | Narrowed range ("this Hard is 7-8") | cheap |
| **2 — deep scout** | The exact number | dear |
| **(optional)** | Which hidden-depth complication is loaded; the true reward amount | per-dimension |

The player chooses *which dimension* to probe and *how deep* — that choice is
itself the strategic act Phase 4 is built around.

### Why scoring & scouting ship together

The moment buckets can lie (option A), the player **must** have a way to buy
down the uncertainty, or failures feel arbitrary — violating the locked
"adversity must feel fair" principle. So score-based resolution cannot ship
without scouting, and scouting is pointless without scores that matter. One
package.

### Scouting as heat insurance

This is the loop that makes scouting worth paying for, and the reason the heat
mechanic and the hidden-info layer belong together:

```
scout → learn true scores → take jobs/crew with comfortable margins →
clean runs → low heat/notoriety → safe campaign

fly blind → trust the buckets → your "High" was a 7 → thin/failed run →
heat spike → notoriety climbs
```

Given in-heist heat is a knife edge (~1-2 points of escape headroom), scouting
is the disciplined player's edge: pay to find out *before* committing which
"doable" jobs are actually quiet and which buckets hide a bad matchup.

### To (re)define when Phase 4 is built

- **Collaboration on 1-10** (today: best bucket +1, capped High). Needs a
  points rule — e.g. best score + a fixed bonus, capped at 10 — so two Mediums
  *might* clear a Hard depending on the true numbers.
- **Viability heuristic** (`job_is_viable`): stays bucket-based as a "this looks
  attemptable" hint for the AI's job pick; true resolution uses scores.
- **When challenge scores roll:** character skill scores are fixed traits (a
  character *is* a Med-5 hacker); challenge scores roll per job-play, like
  hidden depth — fresh fog each attempt.
- **Scout cost model** (flat fee? per-dimension? crew-skill-gated?),
  **reliability** (do scouts ever return wrong info?), and how a scout's own
  heat interacts with the notoriety track.
- **UI affordances** on the lobby / setup screen for browsing the partially-
  known slate and queuing scouts.

---

## Phase 5 — Cops

**Goal:** Full adversarial structure.

- Human cop player
- Cops have full location info; robbers must scout (extends Phase 4's
  asymmetry: now there's a real opponent who knows what the player doesn't)
- Cops have defense budget
- Cops investigate, surveil, strike

---

## Phase 8 — Real multi-human lobby

**Goal:** Let separate people join one shared game, rather than competing
strategy prompts run as AIs in a single process.

Through Phase 2+, "multiplayer" means several strategy prompts, each played by
its own Heist AI. A genuine lobby — distinct humans connecting, claiming a seat,
submitting their own prompt, and watching the shared auction and their crew's
heist live — is deliberately deferred to here. (Phases 6–7 are left open for
other work.)

- Multiple humans join a session: seats, identity, ready-up
- Each submits their own strategy prompt
- The Phase 2 shared auction + parallel heists run across real players

---

## High-level flow (Phase 1)

1. Player submits a strategy prompt. (Just the prompt — nothing else.)
2. Heist AI reads the prompt and the roster, produces a priority-ordered bid allocation totaling ≤ $2,000,000.
3. System validates and processes bids, hires the crew. If incomplete, Heist AI fills remaining slots from unbid roster.
4. Heist AI selects a job from the slate (system validates skill viability).
5. Heist AI writes the casting summary.
6. System rolls hidden depth (one complication/opportunity); loot is secured scene by scene during the run.
7. System determines scene order based on job profile and hidden depth.
8. For each scene: system presents the scene to the Heist AI; Heist AI assigns character; system resolves outcome; Heist AI narrates. Decision points are surfaced by the system and answered by the Heist AI.
9. System resolves the escape from accumulated state; Heist AI narrates.
10. System tallies the secured take (realized only if at least one crew member escaped); Heist AI writes the epilogue.

---

## Open design questions

### Phase 1 — settled

- ✓ Roster: 16 characters, locked
- ✓ Skills, levels, challenge levels, interaction
- ✓ Pricing and bankroll ($2,000,000)
- ✓ Driver mechanic with no-Driver option
- ✓ Three Phase 1 locations with hidden depth
- ✓ Bonus-with-cost principle
- ✓ Player input: only the strategy prompt (no bids, no job selection)
- ✓ System / Heist AI responsibilities split
- ✓ Heist AI does drafting, job selection, in-scene decisions, narration
- ✓ System does all mechanical resolution, scene order, state tracking, calculations
- ✓ Scene loop architecture

### Phase 1 — complete

Phase 1 is feature-complete. Every previously-open item is built and shipped:

- ✓ Scene generation triggers and order details
- ✓ Output format / how the narrative is structured for display
- ✓ Failure consequence specifics
- ✓ Escape mechanic (accumulated-failures resolution)
- ✓ Character roster content (16 personality paragraphs)
- ✓ Location flavor text (all 7 jobs authored)
- ✓ What the player sees during execution (replay-driven event stream)

### Later phases

- Phase 2 player count, contention specifics
- Phase 3 campaign — **designed** (standing crew, notoriety, rolling slate, 10
  rounds; see Phase 3). Open tuning: notoriety thresholds/decay, slate size,
  whether a successful high-value heist also raises notoriety, job tiers.
- Phase 4 scouting — **designed** (1-10 scores under buckets, true-score
  resolution, reveal ladder; see Phase 4). Open: collaboration math on 1-10,
  scout cost model & reliability, scouting's heat interaction.
- Phase 5 cop budget, investigation mechanics

---

## The hard parts of building this

**Narrative coherence.** Each heist is generated as a sequence of scenes with consistent character voices and a satisfying arc. The scene-by-scene loop makes coherence harder than a single generation pass.

**Heist AI consistency across roles.** The same agent does drafting, job selection, in-scene decisions, and narration. Its interpretation of the prompt must stay consistent across all of these.

**Strategy prompt expression.** The Heist AI must make decisions that visibly reflect the player's prompt. Same Heist AI with different prompts should produce visibly different play.

**Character voice consistency.** Four crew members across eight scenes — voices need to stay distinct.

**Adversity that feels fair.** Hidden depth must feel like the world has depth, not arbitrary punishment.

**Content authoring.** 16 characters and 3 locations need deliberate creative writing.

---

## The first prototype

The smallest possible Phase 1:

- One player
- The 3 Phase 1 jobs
- The 16-character roster (with polished personalities and flavor)
- Player writes a strategy prompt
- Heist AI bids, selects job, writes casting summary
- System rolls hidden depth and structures scenes
- Heist AI executes the heist through the scene loop
- System resolves outcomes; Heist AI narrates
- Output: markdown narrative + casting summary

Build small, build fast, run many times. Tune the prompt across many runs.

---

## Change history

**Current revision** — Documented Phase 3 (multi-round campaign) and expanded
Phase 4 (scouting / hidden info). Design only — not built. Phase 3: a 10-round
saga with a standing crew (drafted once, lost to capture, re-hired from loot),
accumulating bankroll/loot, and **notoriety** — a campaign-heat track that
pressures the world (job slate, crew prices, between-round attrition) and never
touches the knife-edge escape roll. Rolling job slate from a larger pool; one
upfront strategy prompt for MVP; win = survive 10 rounds, score by loot banked.
Includes a 3a-3e phasing plan and the forward-compat seam (store 1-10 skill/
challenge scores in Phase 3, resolve on buckets). Phase 4: hidden 1-10 scores
under public Low/Med/High buckets, deterministic true-score resolution (option
A — buckets become estimates, not contracts), a graduated scouting reveal
ladder, scoring+scouting shipping as one package, and the scouting-as-heat-
insurance loop. Phase 4 supersedes the Phase 1-3 graded
bucket model (clean / squeak / fail / caught) and "Hard requires High".

**Earlier revision** — Single Heist AI agent handles all creative decisions (drafting, job selection, scene assignments, in-scene decisions, narration). System owns all deterministic logic (bid validation, skill resolution, hidden depth rolls, scene order, state tracking, reward calc). Scene loop architecture: system presents each scene; Heist AI assigns and narrates; system resolves. Player input simplified to strategy prompt only — no bid allocation.

**Earlier revision** — Two-AI architecture (casting + planning + execution). Player submitted prompt and bids.

**Earlier revision** — Substantial revision after design simulation: removed primary/secondary skill distinction, locked skill point system, nonlinear pricing, $2000 bankroll, simplified interaction to success/failure, Museum puzzle via collaboration rule. Three Phase 1 locations fully authored.

**Earlier revision** — Phased plan with 4 phases. Initial core mechanics.

**Original concept** — Heist crews competing in parallel with cops as opposition.
