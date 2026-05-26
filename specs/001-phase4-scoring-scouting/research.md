# Research: Phase 4

Decisions that required investigation/derivation rather than a straight read of the spec.

## Q1 — Graded-outcome margin thresholds

**Context:** The bucket model graded by `gap = challenge − skill` (gap<0 clean, 0 squeak, 1 fail, ≥2 caught). On a 1-10 scale, a literal translation catches crew on a 2-point near-miss, which would bleed a campaign dry (capture is permanent).

**Options:**
1. **Faithful translation** (clean ≥1, squeak 0, fail −1, caught ≤−2). Too brutal on a fine scale — a 7-vs-9 (a near-miss) catches a member.
2. **Binary** (success iff score ≥ score; design doc "option A" literal). Loses the heat/capture texture the campaign attrition loop runs on.
3. **Widened margin bands** (chosen).

**Decision:** `margin = effective_score − challenge_score`; CLEAN ≥2, SQUEAK 0..1 (+1 heat), FAIL −1..−3 (+1 heat), CAUGHT ≤−4 (+1 heat, lose lead member).

**Rationale:** Bands ~1.5 buckets wide match the old severity intent on a 10-point scale: CAUGHT requires bringing genuinely the wrong tool (4+ short), SQUEAK keeps "barely made it costs heat," and heat still rises on everything non-clean (cascade stays steep — project memory). **Tunable** against a stub campaign: target a capture rate in line with Phase 3's prior feel (validate the campaign doesn't wipe too fast or never lose anyone).

## Q2 — Escape rescaling to the 1-10 world

**Context:** `escape_resolves` uses driver bucket (1-3) vs `escape_modifier + heat`. Driver is now a 1-10 score. The escape cascade is deliberately steep and already tuned (project memory: do not soften).

**Options:**
1. **Full score-based escape** — driver_score vs a rescaled difficulty. Risks silently retuning the cascade; the difficulty scale (mod 0-3 + heat) doesn't map cleanly to 1-10.
2. **Bucket the driver score for the escape** (chosen) — `score_to_bucket(driver_score)` feeds the unchanged `escape_resolves`.

**Decision:** Option 2. The escape contest stays byte-for-byte as today; only the input changes (score→bucket). Preserves the tuned table exactly.

**Rationale:** Lowest-risk way to honor the "don't touch the cascade" memory. Driver *score* precision still matters — for **scouting** (the driver bonus), which is the second role we gave the skill. Revisit a finer escape only if play demands it.

## Q3 — Saved-game backward compatibility

**Context:** `state/games/*.json` records were written under the bucket model (no populated scores, old `job.profile` shape). The loader (`persist._recover_games`) must not crash.

**Options:**
1. **One-time migration** populating scores from buckets and rewriting records. Heavy; mutates history.
2. **Tolerant load** (chosen) — done games replay from their stored event logs (outcomes already baked in; no re-resolution); add a `schema_version`; in-flight games from before Phase 4 are marked **errored** on resume rather than resumed under mismatched mechanics.

**Decision:** Option 2. Replay is event-driven (ARCHITECTURE.md), so historical games render from their persisted events untouched. Only live in-thread resolution uses the new mechanics, and resuming a pre-Phase-4 in-flight game is rare and local.

**Rationale:** Minimal risk, no history rewrite, no migration script to get wrong. The schema tag makes the boundary explicit.

## Q4 — Reward decoupling: correlation-with-slack (P3)

**Context:** Today reward derives deterministically from difficulty, so "edge" jobs (high prize / soft defenses) can't exist. We want prize and defense **correlated but not identical** so scouting can find mispriced jobs (spec FR-016).

**Model (generative, P3):**
- Per cleared challenge, baseline loot `L(C) = round(2930 × 2^C)` → ~$100k@5, $200k@6, $375k@7, $750k@8, $1.5M@9, $3M@10.
- A job's **defense vector** rolls challenge scores from the tier fog bands (Q-independent).
- The job's **prize** = `Σ L(C_i)` over its challenges, then multiplied by a per-job **slack factor** `s ∈ [0.6, 1.5]` drawn from a distribution centered slightly above 1 (so most jobs are fairly priced, a tail is over- or under-priced). Published `reward_range` brackets the slack-perturbed prize; exact amount is the realized point (scoutable).
- An **edge** job is one where `s` is high while its defenses rolled low within their bands → high range over soft defenses. Scouting to exact reveals it.

**Decision:** Implement in P3 as a generation-time perturbation; the engine ships first with reward still `Σ L(C)` (s = 1). This keeps the resolution path unchanged and isolates the tuning change.

**Open tuning:** the slack distribution shape and `[0.6, 1.5]` bounds — settle against the stub campaign so edges occur but aren't the dominant strategy.

## Q5 — Where does the `skills` display bucket come from after scores exist?

**Context:** `Character.skills` (bucket) and `skill_scores` (1-10) would duplicate truth.

**Decision:** Keep `skills` but derive it from `skill_scores` via `score_to_bucket` (single source = the score). Authoring sets scores; buckets are computed. Avoids drift (a hand-set bucket disagreeing with its score). Validation in tests: `bucket(score) == published skills bucket` for all 16 locked entries.
