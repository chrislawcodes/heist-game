# Contracts: Phase 4

No HTTP endpoints are added (Decision D — scouting is in-thread). The contracts here are the **AI↔system decision JSON** and the **event payload shapes** the viewer consumes. These are the wire formats that must stay stable across the two lanes.

## 1. Scouting decision (AI → system)

New decision turn, sibling to job-pick, issued once per round before commitment. The system prompt lists the slate (fogged), the crew, the free-probe budget, and the $100k overflow price. The AI replies with ONLY JSON:

```json
{
  "probes": [
    { "job": "The Museum Gala", "category": "physical" },
    { "job": "The Museum Gala", "category": "physical" },
    { "job": "The Armored Car", "category": "confrontation" },
    { "job": "The Museum Gala", "dimension": "reward" }
  ],
  "rationale": "Drill the Museum's physical to exact; survey the Armored Car; narrow Museum reward."
}
```

- Each probe targets `(job, category)` for a defense probe, or `(job, dimension:"reward")` for a reward probe.
- Probes resolve **in order**: 1st on a `(job, category)` → BUCKET, 2nd → EXACT (no-op at EXACT, not charged).
- The first `free_probes` probes are free; each beyond costs $100k (skipped silently if unaffordable).
- Empty `probes: []` is valid (decline to scout this round).

**System validation:** unknown job/category dropped with a logged warning; probe past EXACT dropped (no charge); a paid probe that can't be afforded is dropped.

## 2. `scouted` event (system → UI, on the SSE stream)

Emitted once per *applied* probe so the viewer can reveal incrementally.

```json
{
  "type": "scouted",
  "ai_idx": 0,
  "job": "The Museum Gala",
  "category": "physical",          // or "dimension":"reward"
  "reveal_level": "EXACT",          // HIDDEN | BUCKET | EXACT
  "bucket": "HARD",                 // present at BUCKET and EXACT
  "score": 9,                        // present only at EXACT (defense)
  "reward_range": [2000000, 3000000],// present for reward probes (narrowed/exact)
  "paid": false,
  "probes_remaining_free": 4
}
```

## 3. Fogged `job_known` / slate payload (changed)

`job_to_dict` now gates defense detail through `ScoutState`. Unscouted categories expose **no** bucket or score; the reward **range** is always public.

```json
{
  "name": "The Museum Gala",
  "flavor": "...",
  "reward_range": [1500000, 4000000],
  "tier": "3",
  "profile": {                       // per-category, gated by reveal level
    "physical":      { "reveal": "EXACT",  "bucket": "HARD", "score": 9 },
    "social":        { "reveal": "BUCKET", "bucket": "HARD" },
    "electronic":    { "reveal": "HIDDEN" },
    "confrontation": { "reveal": "HIDDEN" }
  }
}
```

Old shape was `"profile": {"physical": "HARD", ...}` (always full). The UI must read `profile[cat].reveal` and render fog/bucket/score accordingly. During the run (post-commit), scene cards may show the public bucket as scenes play, but never an exact `score` unless it was scouted.

## 4. `crew_known` / `character_to_dict` (changed — now public scores)

`skill_scores` is populated and public:

```json
{
  "id": 10, "name": "Rook",
  "skills": { "safecracker": "HIGH" },
  "skill_scores": { "safecracker": 9 },
  "floor_cost": 700000
}
```

UI may display the exact score (e.g. "Safecracker 9") since character scores are never fogged.

## Compatibility note

These are **additive/gating** changes. Consumers that ignore the new `score`/`reveal` fields still function; the only breaking change is `job.profile` values becoming objects instead of bucket strings — the viewer's job/hiring tabs must be updated in lockstep (P2). Done-game replays written under the old shape load tolerantly (Decision C, data-model.md).
