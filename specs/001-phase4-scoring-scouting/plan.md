# Implementation Plan: Phase 4 — Hidden Location Info & Scouting (Score-Based Resolution)

**Branch:** `feat/phase4-scoring-scouting` | **Date:** 2026-05-26 | **Spec:** [spec.md](spec.md)

## Summary

Move the engine from coarse buckets to hidden 1-10 scores. Character scores are public; location challenge scores are fogged and rolled per round. Resolution compares true scores at a single choke point (`resolution._resolve_challenge_scene`); pricing, collaboration, and graded outcomes are re-expressed on the 1-10 scale. Scouting is an in-thread, AI-driven phase (no new HTTP endpoint) that reveals fogged defenses bucket-then-exact. Sequenced P1 (engine) → P2 (scouting + fog UI) → P3 (tiers, reward decoupling, 17th character).

## Technical Context

**Language/Version:** Python 3.x (stdlib only; `dataclasses`, `enum`, `random`, `http.server`).
**Primary Dependencies:** none added. Tooling: `ruff`, `mypy`, `pytest` (preflight per CLAUDE.md).
**Storage:** JSON game records under `state/games/` (`heist/persist.py`); no DB.
**Testing:** `pytest` (`test_mechanics.py`, `test_resolution.py`, `test_scenes.py`, `test_runner_stub.py`).
**Target Platform:** local stdlib `ThreadingHTTPServer`; one runner thread per AI per game.
**Performance Goals:** N/A (turn latency dominated by AI CLI calls). Determinism of resolution is the real requirement (SC-003).
**Constraints:** two-lane architecture (engine emits events; UI only renders); heat cascade stays steep (project memory); existing `run_heist`/`run_campaign` must keep working (FR-007).
**Scale/Scope:** 16→17 characters, 15 jobs (pool already expanded), 5 skills/challenge categories.

## Constitution Check

**Status: SKIPPED.** No constitution file in repo (`CONSTITUTION.md`, `docs/constitution.md`, `.specify/memory/constitution.md` absent). `CLAUDE.md` conventions (two-lane architecture, staging rule, `/ship` merges, Codex-implements) are honored operationally at implement time, not as gates here.

---

## Architecture Decisions

### Decision A — Scores live on a per-round intel object, not on `Job`

**Chosen:** `Job` stays a frozen module-level constant with an **empty** `challenge_scores`. The *rolled* scores for a given play live on a new per-round structure carried by `HeistState` (and the campaign round), alongside the existing `HiddenDepthRoll`. A new `mechanics.roll_challenge_scores(profile, tier, rng)` produces them from the tier fog bands. `scenes.generate_scenes` stamps the true score onto each `Scene` (new field `Scene.challenge_score: int | None`), so resolution reads it directly.

**Rationale:** `Job` instances are shared, frozen, and reused every round; mutating per-round scores onto them is unsafe and non-deterministic across concurrent AIs. A per-round home matches how `HiddenDepthRoll` already works.

**Alternatives:** (1) Mutate `Job.challenge_scores` per round — rejected (frozen + shared). (2) Re-roll inside resolution — rejected (resolution must stay pure/deterministic given inputs).

**Tradeoffs:** + Clean determinism, parallel-AI safe. − One more field threaded through state/serialize/snapshot.

### Decision B — Escape stays bucket-resolved via score→bucket derivation

**Chosen:** Keep `escape_resolves` semantics exactly (driver **bucket** vs `escape_modifier + heat`, the tuned knife-edge in project memory). Derive the driver's bucket from its new 1-10 score via `score_to_bucket` (8-10→High/3, 4-7→Med/2, 1-3→Low/1, 0→None). Body-of-heist challenges move fully to scores; the escape contest does not.

**Rationale:** The escape cascade is deliberately steep and already tuned (project memory: *do not soften it*). Re-expressing it on a 1-10 difficulty scale risks silently changing that balance. Bucketing the driver score preserves the exact existing table with near-zero risk. This refines FR-006: "rescale" = "derive bucket from score," not "invent a 1-10 escape contest."

**Alternatives:** Full score-based escape (driver_score vs a rescaled difficulty) — rejected for v1 as a balance risk; revisitable later if the escape needs finer granularity.

**Tradeoffs:** + Zero balance risk, tiny change. − Driver score precision (Slim 9 vs a hypothetical 8) doesn't affect the escape — both are "High." Acceptable; scouting/recon is where driver score earns its keep.

### Decision C — Margin-based graded outcomes (widened bands for the 1-10 scale)

**Chosen:** Replace the bucket gap with `margin = effective_score − challenge_score`:

| Margin | Outcome | Effect |
|---|---|---|
| ≥ 2 | CLEAN | secure loot, no heat |
| 0 to 1 | SQUEAK | secure loot, **+1 heat** |
| −1 to −3 | FAIL | miss, **+1 heat** |
| ≤ −4 | CAUGHT | miss, **+1 heat**, lose the lead member |

**Rationale:** A 10-point scale needs wider bands than the 3-bucket model, or being 2 points short (a near-miss like 7-vs-9) would catch crew far too often and bleed the campaign dry. CAUGHT at ≤−4 (~1.5 buckets short) preserves the "you brought the wrong tool" severity without punishing near-misses. SQUEAK at 0-1 keeps "barely made it costs heat." Thresholds are tunable against a stub campaign (see research.md). Heat still rises on anything non-clean — the cascade stays steep.

**Alternatives:** Faithful bucket translation (clean ≥1, squeak 0, fail −1, caught ≤−2) — rejected: too punishing on a fine scale. Binary success/fail (design doc "option A" literal) — rejected: loses the heat/capture texture the campaign attrition loop needs.

**Tradeoffs:** + Preserves all four outcomes and the knife-edge. − Thresholds are a tuning surface, not derived; flagged for stub validation.

### Decision D — Scouting is in-thread and AI-driven; no new endpoint

**Chosen:** The scouting phase runs inside the runner/campaign thread, as a new AI decision turn before job commitment (a sibling to `_pick_job`). The system computes the free probe budget (`crew size + best-driver bonus`), validates probe targets, deducts $100k for over-budget probes, mutates a per-round `ScoutState`, and emits `scouted` events. The viewer renders from those events (two-lane: engine emits, UI renders). No HTTP endpoint is added.

**Rationale:** All game-state mutation already happens in the runner thread; SSE is read-only broadcast. A new endpoint would break the one-way event model and complicate replay/persistence.

**Alternatives:** Interactive HTTP scouting endpoint — rejected (breaks two-lane model, replay, snapshotting).

**Tradeoffs:** + Fits existing architecture, replayable, snapshot-friendly. − Scouting strategy is expressed by the AI from the prompt, not by direct player clicks (consistent with the game's "player writes intent, AI executes" principle).

### Decision E — A single `ScoutState` is the source of truth for fog

**Chosen:** Per-round `ScoutState` maps `(job_name → {category → RevealLevel})` where `RevealLevel ∈ {HIDDEN, BUCKET, EXACT}`, plus the reward-range reveal step and the probe budget/spend. Both **prompts** (`_job_slate_summary`, `_job_prompt`, `_scene_assign_prompt`) and **serialization** (`job_to_dict`, `scene_to_dict`) read it to decide what to expose. Character scores are always public (populate `skill_scores`; surface in `_roster_summary` and `character_to_dict`).

**Fog boundary:** Pre-commit (slate browsing + scouting) defenses are fogged per `ScoutState`. Post-commit (during the run) the scene structure reveals public buckets as scenes play; **exact challenge scores are never shown unless scouted**. This matches reality — once inside, you see the shape; precise difficulty stays implicit in outcomes.

**Rationale:** One authority for "what's known" prevents prompt/UI drift (a leak in either lane breaks the fog).

**Tradeoffs:** + No double-source bugs. − Every leak point (3 prompt sites + 3 serialize sites from the Explore map) must consult `ScoutState`.

---

## Project Structure

Monolithic Python package `heist/`. Touch map by phase:

```
heist/
├── state.py            P1: Scene.challenge_score; HeistState.challenge_scores;
│                           RevealLevel enum; ScoutState dataclass; score_to_bucket helper home
├── mechanics.py        P1: score_floor_cost (replaces base_cost/expected_floor_cost);
│                           effective_skill_score (+1 point, cap 10) + effective_skill_bucket;
│                           resolve_by_margin (replaces resolve_outcome); roll_challenge_scores;
│                           escape unchanged (consumes derived bucket)
├── resolution.py       P1: _resolve_challenge_scene reads effective_score vs Scene.challenge_score
├── scenes.py           P1: stamp Scene.challenge_score from rolled scores; structure still
│                           built from public buckets (is_core etc.)
├── characters/__init__ P1: populate skill_scores (16 locked); P3: add 17th medium hacker + portrait
├── locations/__init__  P1/P3: tier normalization (1/2/3); P3: reward decoupling generation
├── runner.py           P1: roll scores after job pick; P2: scouting decision turn in run_one_job/run_heist
├── campaign.py         P2: per-round scouting phase + free-probe budget
├── prompts.py          P1/P2: fog job slate + scene assign via ScoutState; public character scores;
│                           new scouting decision prompt
├── serialize.py        P1/P2: character_to_dict scores; job_to_dict/scene_to_dict fog via ScoutState;
│                           scout_state_to_dict; scouted event payload
├── server.py           P2: ensure scouted events broadcast/persist (no new route)
├── persist.py          P1/P2: schema version tag; ScoutState in round snapshot; tolerant legacy load
├── stub_responses.py   P2: scouting decision response (dispatch on prompt substring)
└── web/                P2: shell.js helpers (render scores, fogged buckets); tabs/job.html +
                            hiring.html fog + scout panel; tabs/heist.html unaffected
tests/
├── test_mechanics.py   P1: score pricing, +1-point collab, margin outcomes, roll bands
├── test_resolution.py  P1: score-vs-score table
├── test_scenes.py      P1: challenge_score stamped
├── test_runner_stub.py P1/P2: end-to-end stub heist + scouting phase
└── test_scouting.py    P2 (new): probe budget, bucket→exact, $100k overflow, fog in serialize
heist_game_design.md    P1: bucket boundaries, +1-point collab, score resolution, scouting-locations-only
```

**Structure Decision:** P1 is contained to engine + content + prompts/serialize and must leave the event stream shape backward-compatible (only *adds* populated `skill_scores`/`challenge_scores` and fogs defenses). P2 adds the scouting turn, `ScoutState`, the `scouted` event, and the fog UI. P3 is content/generation (tiers, reward slack, the new character).

## Open Decisions — resolved in [research.md](research.md)

- Margin thresholds (Decision C) — default set, flagged for stub-campaign tuning.
- Escape rescaling (Decision B) — resolved to score→bucket derivation.
- Saved-game backward-compat (Decision C in research) — tolerant load + schema version; legacy in-flight games error on resume.
- Reward correlation-with-slack model — generative formula in research.md (P3).
