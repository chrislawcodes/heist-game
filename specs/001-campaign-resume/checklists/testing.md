# Testing Quality Checklist

**Purpose**: Validate test coverage and quality
**Feature**: [tasks.md](../tasks.md)

(No formal constitution; references CLAUDE.md preflight + smoke-test conventions.)

## Preflight (CLAUDE.md — run before every push / in /ship)
- [ ] `python3 -m ruff check .` clean
- [ ] `mypy heist/ agents.py demo.py` clean (no new ignores)
- [ ] `pytest -q` green

## New coverage (tests/test_campaign_resume.py)
- [ ] `campaign_from_dict` round-trips a `game_states[i]` snapshot (standing_crew, banked_loot, round_results)
- [ ] Stage-skip idempotency: reconstructed at `heist` stage does not re-run hiring (banked_loot unchanged) nor double-append a `RoundResult`
- [ ] `settle_round` exactly once across a settle/round-advance boundary
- [ ] `recover_games`: running campaign WITH `checkpoint_version` → resumed; WITHOUT → `interrupted`; `done` → untouched
- [ ] Manual resume guard: 409-equivalent when id in `active_campaigns`; proceeds otherwise; 422 for non-resumable
- [ ] No-duplication: a resumed run finishes with exactly `num_rounds` round_results per team and no duplicate sub-game ids

## Smoke (CLAUDE.md /ship Step 4.5 — required, touches runner/server)
- [ ] Isolated `HEIST_STATE_DIR`, spare port; stub quick-game reaches `status=done` (server boots with the new route + recovery branch)

## Edge cases (from spec)
- [ ] Interrupted before any round completed (round-0 auction) resumes cleanly
- [ ] Repeated interrupt→resume→interrupt still resumes
