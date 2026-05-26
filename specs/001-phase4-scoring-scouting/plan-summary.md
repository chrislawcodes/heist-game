# Plan Summary: Phase 4 — Hidden Location Info & Scouting

## Files In Scope

| File | Change | Notes |
|------|--------|-------|
| `heist/state.py` | modify | `Scene.challenge_score`; `HeistState.challenge_scores` + `scout_state`; `RevealLevel` enum; `ScoutState` dataclass |
| `heist/mechanics.py` | modify | `score_floor_cost` (replaces `base_cost`/`expected_floor_cost`); `effective_skill_score` (+1 point, cap 10) + `effective_skill_bucket`; `score_to_bucket`; `resolve_by_margin` (replaces `resolve_outcome`); `roll_challenge_scores`; `driver_scout_bonus`/`free_probe_budget`; `escape_resolves` unchanged body |
| `heist/resolution.py` | modify | `_resolve_challenge_scene`: `effective_skill_score` vs `Scene.challenge_score` |
| `heist/scenes.py` | modify | stamp `Scene.challenge_score` from rolled scores; structure still built from public buckets |
| `heist/characters/__init__.py` | modify | populate `skill_scores` (16 locked); P3: add 17th Medium Hacker + portrait |
| `heist/locations/__init__.py` | modify | normalize `tier` → "1"/"2"/"3"; P3: reward correlation-with-slack generation |
| `heist/runner.py` | modify | roll challenge scores after job pick; P2: scouting decision turn (sibling to `_pick_job`) in `run_one_job`/`run_heist` |
| `heist/campaign.py` | modify | P2: per-round scouting phase; compute free-probe budget |
| `heist/prompts.py` | modify | fog `_job_slate_summary`/`_job_prompt`/`_scene_assign_prompt` via `ScoutState`; public scores in `_roster_summary`; new scouting decision prompt |
| `heist/serialize.py` | modify | `character_to_dict` scores; gate `job_to_dict`/`scene_to_dict` via `ScoutState`; `scout_state_to_dict`; `scouted` payload |
| `heist/server.py` | modify | P2: ensure `scouted` events broadcast/persist (no new route) |
| `heist/persist.py` | modify | `schema_version` tag; `ScoutState` in round snapshot; tolerant legacy load |
| `heist/stub_responses.py` | modify | P2: scouting decision response (dispatch on prompt substring) |
| `heist/web/shell.js` | modify | P2: helpers to render scores + fogged buckets |
| `heist/web/tabs/job.html`, `tabs/hiring.html` | modify | P2: fog defenses + scout panel; consume `profile[cat].reveal` |
| `tests/test_mechanics.py`, `test_resolution.py`, `test_scenes.py`, `test_runner_stub.py` | modify | score-based assertions |
| `tests/test_scouting.py` | create | probe budget, bucket→exact, $100k overflow, serialize fog |
| `heist_game_design.md` | modify | bucket boundaries (4-7/8-10), +1-point collab, score resolution, scouting-locations-only |

## Migration Steps

1. Add `schema_version` to game records in `heist/persist.py`.
2. Tolerant load: done games replay from stored events (no re-resolution); pre-Phase-4 in-flight games marked errored on resume (not resumed under mismatched mechanics).
3. No data backfill — character/job scores are code constants, not stored state.

## Data Model

- **Character**: populate `skill_scores: dict[str,int]` (public; bucket derived).
- **Job**: `challenge_scores` stays empty on the frozen constant; `tier` → "1"/"2"/"3".
- **Scene**: add `challenge_score: int | None` (stamped at generation).
- **HeistState**: add `challenge_scores: dict[str,int]` (rolled per round) + `scout_state: ScoutState`.
- **ScoutState** (new): `reveals[job][category] → RevealLevel{HIDDEN,BUCKET,EXACT}`, `reward_reveal[job]`, `free_probes`, `probes_spent_free`, `probes_paid`.

## Key Constraints

- **Two-lane architecture**: engine emits all events; UI only renders — *Why: a missing UI value is fixed by emitting it from the engine, never by reconstructing it in the browser.*
- **`ScoutState` is the single fog authority**: both prompts and serialize gate on it — *Why: two sources of "what's known" drift and leak the fog in one lane.*
- **`Job` is a frozen, shared constant**: rolled scores live per-round on `HeistState`, never mutated onto the Job — *Why: jobs are reused every round across parallel AIs; per-round mutation breaks determinism.*
- **Escape stays bucket-resolved** via `score_to_bucket(driver_score)`; `escape_resolves` body unchanged — *Why: the escape cascade is deliberately steep and already tuned (project memory) — re-expressing it on 1-10 risks retuning it silently.*
- **Heat cascade stays steep**: margin bands CLEAN ≥2 / SQUEAK 0..1 / FAIL −1..−3 / CAUGHT ≤−4, heat on all non-clean — *Why: project memory; scouting is the counterweight, not a softer cascade.*
- **Character scores public; location scores fogged**: scouting is locations-only — *Why: locked design; pricing on public character scores leaks nothing.*
- **Existing flows keep working**: `run_heist`/`run_campaign` end-to-end — *Why: FR-007.*
- **P1 event stream stays backward-compatible**: only adds populated scores + gates defenses; the one breaking shape change (`job.profile` values become objects) lands with the P2 UI in lockstep.
