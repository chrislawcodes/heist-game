# Quickstart: Phase 4 — manual testing guide

## Prerequisites

- [ ] On `feat/phase4-scoring-scouting` (worktree under `.claude/worktrees/`, per CLAUDE.md — never on main).
- [ ] Preflight green: `python3 -m ruff check . && mypy heist/ agents.py demo.py && pytest -q`
- [ ] No-API path available: `python -m heist run --agent stub --out /tmp/p4.md`

## US1 — True-score resolution, pricing, collaboration (P1)

**Goal:** the engine runs on 1-10 scores without breaking existing play.

1. Run a stub single job: `python -m heist run --agent stub --out /tmp/p4.md`.
2. Run a stub campaign: `python -m heist run-campaign --agent stub` (3 rounds).
3. In a Python shell: `from heist.characters import ROSTER; from heist.mechanics import score_floor_cost` and print each `(c.name, score_floor_cost(c))`.

**Expected:**
- Both runs complete with no traceback and emit the usual events (`crew_known`, `job_known`, `scene_*`, `game_done`).
- Floor costs match: Rook $700k, Marcus $1,200k, Vance $425k, Pearl $275k, Eli $100k (full table in spec.md).
- Two same-skill members give effective `min(best+1, 10)`; a challenge passes iff `effective_score ≥ challenge_score`.
- Graded outcomes + heat still emit per the margin table (clean/squeak/fail/caught).

**Verification:** `pytest -q tests/test_mechanics.py tests/test_resolution.py` green with score-based assertions.

## US2 — Scout a location (P2)

**Goal:** scouting reveals fogged defenses bucket→exact, budget = crew + driver.

1. Run a stub campaign and inspect the round's `scouted` events (event log under `state/games/<id>.json`).
2. Confirm a crew with a Medium-driver gets `crew + 2` free probes; a High-driver crew gets `crew + 3`.
3. Confirm a 1st probe on `(job, category)` yields `reveal_level: BUCKET`; a 2nd yields `EXACT` with a `score`.
4. Force over-budget probes (small crew, no driver) and confirm $100k is deducted, and an unaffordable probe is skipped.

**Expected:** probe budget arithmetic correct; bucket-then-exact reveal order; reward range stays public; over-budget probes charge $100k or are refused.

**Verification:** `pytest -q tests/test_scouting.py`.

## US3 — Fog in the viewer (P2)

**Goal:** the UI shows public flavor/reward range, fogged defenses, and intel as scouted.

1. `python -m heist serve` (from the worktree); open the campaign replay for a stub game.
2. On the job/hiring tab, inspect a slate location before any scout event.
3. Step the replay past a `scouted` event.

**Expected:**
- Pre-scout: defense categories render as fogged/unknown; reward **range** shown.
- After a bucket `scouted` event: that category shows its bucket; after an exact event: shows the 1-10 score.
- No exact defense score or exact reward ever appears that wasn't scouted.

**Verification:** browser check (preview); confirm `job.profile[cat].reveal` drives rendering.

## US4 — Tiered ladder + edge jobs (P3)

**Goal:** difficulty ladder by tier; some jobs are mispriced (edge).

1. In a shell, roll challenge scores for a Tier-1 and a Tier-3 job many times (`roll_challenge_scores`).
2. Generate the pool's prizes via the slack model and look for a high-range/soft-defense job.

**Expected:** Tier-1 Hard rolls 8; Tier-3 gating Hards roll 9-10; each skill gates a fair share across the 15 jobs; at least one edge job exists.

**Verification:** `pytest -q tests/test_scenes.py` (band assertions) + a content sanity check.

## US5 — Second Medium Hacker (P3)

**Goal:** electronic has a collaboration fallback.

1. Load the roster; confirm 17 characters and ≥2 Medium-band hackers.
2. Pair the new hacker (7) with Sasha (6) on electronic → effective 8.

**Expected:** new character has full personality + portrait + curve-correct floor cost; two mediums reach an effective 8 (a Hard-8 collab path).

## Troubleshooting

- **Old game won't load / crashes loader:** confirm tolerant-load path (Decision C) — done games replay from stored events; pre-Phase-4 in-flight games should mark errored, not crash.
- **AI sees an unscouted exact score:** a prompt leak — check `_job_slate_summary`/`_scene_assign_prompt` consult `ScoutState`.
- **UI shows a defense it shouldn't:** a serialize leak — check `job_to_dict` gates on `ScoutState`.
- **Campaign wipes too fast / never loses crew:** retune the margin CAUGHT threshold (research.md Q1).
