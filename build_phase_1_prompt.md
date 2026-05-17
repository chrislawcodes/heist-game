# Prompt for building Phase 1

I'm building a single-player AI heist game. The design is fully specified in the attached document (heist_game_design.md). Your job is to build Phase 1 as a working prototype.

Read the design doc thoroughly before starting. The "Phase 1" sections and the "Phase 1 architecture: System and Heist AI" section are the most important. The high-level flow at the bottom gives you the loop you're implementing.

## What to build

A command-line Python program that:

1. Reads a strategy prompt from the user (stdin or a file)
2. Runs the full Phase 1 flow: Heist AI drafts a crew via bidding, selects a job, the system rolls hidden depth, the scene loop executes, the escape resolves, the reward is calculated
3. Outputs a markdown file containing the casting summary and the full heist narrative

That's the whole product for v1. No web UI, no multiplayer, no persistence.

## Architecture

Two main pieces, kept strictly separate:

**System (deterministic Python code):**
- Owns the roster, the job slate, and all hidden depth pools
- Validates bids against the bankroll
- Computes skill-vs-challenge outcomes
- Rolls hidden depth
- Generates scene order from the job profile and hidden depth
- Tracks state across the heist
- Resolves the escape and calculates the reward

**Heist AI (calls to Claude via the Anthropic API):**
- Drafts the crew given prompt + roster
- Selects the job given prompt + crew
- Writes the casting summary
- Assigns characters to each scene as the system presents them
- Makes decisions at decision points (bonus-with-cost, abort vs. push)
- Narrates each scene given the system's outcome

Use a single Claude instance for the Heist AI throughout, maintaining conversation context so it remembers the prompt, the crew, and what's happened. This is important — a fresh Claude call per scene loses character voice and strategic consistency.

## Content to author

The design doc has the roster's names and skill profiles but the personality paragraphs are sketched and need polishing. Same for location flavor text. Before running anything, write:

- 15 character personality paragraphs (80-150 words each). Each character needs a distinct voice the AI can act on. Use the sketched personalities in the doc as starting points.
- 3 location flavor descriptions, polished beyond what's in the doc.

Put these in separate Python files or JSON files that the system can load.

## What's "done"

You're done when:

1. A user can submit the default prompt (in the doc, in the "Phase 1 architecture" section) and the system produces a complete heist narrative.
2. The narrative reads like a heist movie — scenes have texture, characters have voice, the strategy prompt visibly drives at least one decision.
3. Changing the prompt produces visibly different play (different crew, different job, different decisions).
4. The mechanical resolution is correct — failures happen when skill < challenge, escapes resolve correctly, reward is calculated correctly.

## Open items to use your judgment on

A few things in the doc are unsettled. Pick reasonable defaults and add a short note at the top of your README explaining what you chose:

- Exact rules for scene order (the doc gives the general pattern; you'll need concrete rules)
- How failure cascades (the doc says "system determines based on context"; pick a clear rule)
- Escape difficulty calculation (the doc says "from accumulated state"; define accumulated state concretely)
- Output format details (how scenes are delimited, where reasoning appears in the narrative)
- Bid format the Heist AI uses (just structured output is fine; ask for JSON from Claude)

If you hit something the doc genuinely doesn't address and you can't pick a reasonable default, stop and ask.

## How to work

Start small. Get the system framework running with a stub Heist AI (returns hardcoded responses) before integrating real Claude calls. Get one scene working end-to-end before scaling to the full loop. Run the default prompt end-to-end as soon as it might work, even if it's rough — that's the fastest way to find what's broken.

Don't over-engineer. No databases, no microservices, no fancy logging. Just clean Python with sensible structure: separate files for system logic, AI prompts, content (roster, jobs), and the main flow. A 500-1000 line program is plenty.

When in doubt, the design doc wins.
