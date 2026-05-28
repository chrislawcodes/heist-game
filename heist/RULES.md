# Heist AI Rulebook

This is the rulebook handed to the Heist AI before every game. It is the single
source of truth for in-game mechanics — when this file disagrees with anything
else, this file wins. Update it whenever the engine's rules change; the
prompt-builder loads it at module init.

Voice: second-person, talking to the AI playing the game.

---

What you know about this work:

## Skills and challenges

- Every job is a profile of four challenge types — **Electronic** (cameras,
  networks, electronic locks), **Physical** (vaults, safes, structural),
  **Confrontation** (guards, armed response), and **Social** (blending in,
  talking your way through). Each has a hidden true difficulty from **1 to 10**.
- Public buckets are derived from the true score: **1-3 Low, 4-7 Medium,
  8-10 Hard** (0 = no challenge of that type). The bucket is published, the
  exact number is fogged until you scout it.
- Crew skills are shown as exact 1-10 scores (these are **public**). Same
  bucket boundaries: 1-3 Low, 4-7 Medium, 8-10 High.

## Collaboration adds one point

Put two crew on the same challenge and the effective score is the **higher of
the two PLUS 1**, capped at 10. So a 7 pairs up to 8 (High), but two ordinary
Mediums (say 5 and 6) only reach 7, still Medium. Do **not** assume two Mediums
can cover a Hard; most of the time they cannot.

## Scouting — before you commit

Scouting comes first in every round. Use it to buy down location uncertainty.

- Each round you get a budget of **free probes = crew size + best driver's
  bonus**. There is no paid over-budget probing on top of that.
- A probe targets one job's one challenge category (electronic / physical /
  confrontation / social).
- **First** probe on a challenge → reveals its bucket (Low / Med / Hard).
  **Second** probe on the same challenge → reveals its exact 1-10 score.
- Even a revealed bucket is only an estimate: a "Hard" could be 8 or 10. Bring
  margin or spend a second probe to nail down the number.
- Character scores are public; **only locations are fogged** — never spend
  probes on crew.

Strategy: learn the buckets broadly across the jobs you're weighing, then nail
down the exact number on the Hard cells you plan to attempt. Probing the
escape is often the highest-value probe.

## Picking from the contested job board

You do **not** see every job in the game. Each round, a shared **board of 8**
jobs is drawn from a pool of ~50, minus any job already consumed.

- Up to 4 teams share the same board.
- Picking order is **trailing-team-first**: the team with the lowest banked
  loot picks first. This is anti-snowball — being behind is its own advantage.
- A job is **consumed for everyone** once any team attempts it. If you wait
  too long, your preferred target may disappear.
- Board composition is gated by campaign progress: early rounds skew
  cheap-to-mid, jackpots unlock in later rounds, plus some random wild slots.
- Reward generally climbs with difficulty — the **elite 4-Hard jobs are the
  $15-18M jackpots** you bank across rounds to afford. But the market has
  slack: 1-2 "edge" jobs sit off-trend per board (a bargain whose true scores
  are softer than the reward implies, or a trap where the reward overstates
  what you can clear). Scouting is how you tell them apart.

## Hiring the crew

After you've picked a job, you draft the crew.

- Starting bankroll: **$2,000,000**. Banked loot from previous rounds becomes
  the next round's bankroll.
- Character pricing is **convex** — `$100k seat + Σ premium(score)`, with the
  premium rising steeply at the top of the curve. A score-8 specialist is
  significantly cheaper than a score-10 one.
- A strong **Driver** covers the escape; no driver means running on foot,
  which limits which jobs you'll survive (see escape rules below).

## How a scene resolves

Each scene: your crew's effective score for that challenge vs the challenge's
true score. The **margin** = your score minus the challenge's score:

- **Margin ≥ +2** → **CLEAN** — you pass, no heat.
- **Margin 0 or +1** → **SQUEAK** — you pass, but heat +1.
- **Margin −1 to −3** → **FAIL** — the scene fails, heat +1.
- **Margin ≤ −4** → **CAUGHT** — the scene fails AND a crew member is taken
  away, heat +1.
- A challenge with no defense (score 0) always comes up clean.

Since you can't see the exact challenge number, **margin is your safety net**.
A score that only matches the published bucket can squeak (costing heat) or,
if the hidden number runs high, fail outright. **Bring more than you think
you need on a Hard.**

## Heat and the getaway

Heat is your alarm level. It rises by 1 for every scene that isn't clean
(squeak, fail, or caught). **Heat resets each round** — it only affects
that round's own escape.

The escape is a getaway check. Every job has an escape difficulty from **0 to 6** — more heavily-defended
jobs are higher.

- Your **total heat is added to the escape difficulty**.
- Your **best Driver's score** must be at least that combined number (escape
  difficulty + heat) to get out.
- Pair two Drivers and they collaborate (best + 1 point, same as any other
  challenge).
- **No driver = score 0** — you're on foot. Often fatal.
- A failed escape: one more crew member is caught.

The escape is why heat management matters. Three squeaks in a row can turn a
soft job into an unwinnable getaway.

## The take

- You only secure loot from scenes you pass (clean or squeak).
- You **keep** the take only if at least one crew member escapes uncaught. If
  the whole crew is taken, you leave with nothing.
- You can **abort at any scene** — skip the rest, run the escape immediately
  with whatever you've secured so far.

## Bonus opportunities

Some scenes turn up a **score within a score** — a bonus opportunity. Pursuing
it has its own challenge resolution, so it can squeak/fail/catch like any
scene. Pursue or decline based on your strategy: more take vs more heat.

## Across a campaign

- You draft your crew once and keep it across rounds — this is the **standing
  crew**.
- **Banked loot carries forward** as the next round's bankroll. Heat does not.
- Crew taken (a CAUGHT scene or a failed escape) are **gone for the rest of
  the campaign**. If your whole standing crew is taken, the campaign ends.
- Trailing teams pick first each round (see board rules), so banking a big
  jackpot is a mixed blessing — it lets you afford expensive crew, but it
  pushes you to the back of the next round's pick order.
