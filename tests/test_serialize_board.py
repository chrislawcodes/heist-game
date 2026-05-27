"""US6 — board state round-trips through serialize so replay/resume restore the
consumed set and per-round board without recomputation (SC-005, two-lane)."""
from heist.content import ROSTER
from heist.serialize import campaign_from_dict, campaign_to_dict
from heist.state import Campaign, RoundResult


def _campaign_with_board():
    c = Campaign(
        rounds_total=10,
        bankroll=500_000,
        banked_loot=3_000_000,
        standing_crew=list(ROSTER[:4]),
        consumed_jobs={"The Cargo Yard", "The Mint", "Corner Pharmacy"},
    )
    c.round_results.append(RoundResult(
        round_idx=0, job_name="The Cargo Yard", take=2_600_000, aborted=False,
        escape_success=True, heat=1, banked_after=2_600_000,
        board=["The Cargo Yard", "Corner Pharmacy", "The Mint", "Art Forgery Ring"],
        contested=True,
    ))
    return c


def test_consumed_jobs_round_trips():
    c = _campaign_with_board()
    restored = campaign_from_dict(campaign_to_dict(c))
    assert restored.consumed_jobs == {"The Cargo Yard", "The Mint", "Corner Pharmacy"}


def test_round_result_board_round_trips():
    c = _campaign_with_board()
    restored = campaign_from_dict(campaign_to_dict(c))
    rr = restored.round_results[0]
    assert rr.board == ["The Cargo Yard", "Corner Pharmacy", "The Mint", "Art Forgery Ring"]
    assert rr.contested is True


def test_legacy_campaign_without_consumed_loads_empty():
    """A pre-feature campaign record (no consumed_jobs / board keys) loads with an
    empty consumed set and empty boards — tolerant, no crash."""
    legacy = {
        "rounds_total": 5, "bankroll": 0, "banked_loot": 0,
        "standing_crew": [], "round_results": [
            {"round_idx": 0, "job_name": "X", "take": 1, "aborted": False,
             "escape_success": True, "heat": 0},
        ],
    }
    c = campaign_from_dict(legacy)
    assert c.consumed_jobs == set()
    assert c.round_results[0].board == []
    assert c.round_results[0].contested is False
