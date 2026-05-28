"""US6 — board state round-trips through serialize so replay/resume restore the
consumed set and per-round board without recomputation (SC-005, two-lane).

Feature 003 (scouting-depth-rotation) extended Campaign with carryover_board,
persistent_slate_scores, and per_ai_scout_state. Round-trip tests for those new
fields are at the bottom of this file."""
from heist.content import ROSTER
from heist.serialize import campaign_from_dict, campaign_to_dict
from heist.state import Campaign, RevealLevel, RoundResult, ScoutState


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


# ── Feature 003: carryover_board / persistent_slate_scores / per_ai_scout_state ──


def _campaign_with_feature003_state():
    """Build a Campaign that exercises every new field added in feature 003."""
    c = Campaign(
        rounds_total=3,
        bankroll=0,
        banked_loot=4_000_000,
        standing_crew=list(ROSTER[:4]),
        consumed_jobs={"Picked Last Round"},
        carryover_board=["The Wine Cellar", "The Repo Lot", "Riverside Data Center"],
        persistent_slate_scores={
            "The Wine Cellar": {"electronic": 2, "physical": 5, "confrontation": 1, "social": 4},
            "The Repo Lot": {"electronic": 3, "physical": 8, "confrontation": 7, "social": 2},
        },
    )
    ss = ScoutState(free_probes=10, probes_spent_free=4, rationale="case the cheap one")
    ss.reveals.setdefault("The Wine Cellar", {})["electronic"] = RevealLevel.EXACT
    ss.reveals.setdefault("The Wine Cellar", {})["physical"] = RevealLevel.BUCKET
    ss.exact_scores.setdefault("The Wine Cellar", {})["electronic"] = 2
    c.per_ai_scout_state[0] = ss
    return c


def test_carryover_board_round_trips():
    c = _campaign_with_feature003_state()
    restored = campaign_from_dict(campaign_to_dict(c))
    assert restored.carryover_board == ["The Wine Cellar", "The Repo Lot", "Riverside Data Center"]


def test_persistent_slate_scores_round_trip():
    c = _campaign_with_feature003_state()
    restored = campaign_from_dict(campaign_to_dict(c))
    assert restored.persistent_slate_scores["The Wine Cellar"]["physical"] == 5
    assert restored.persistent_slate_scores["The Repo Lot"]["confrontation"] == 7


def test_per_ai_scout_state_round_trip():
    c = _campaign_with_feature003_state()
    restored = campaign_from_dict(campaign_to_dict(c))
    ss = restored.per_ai_scout_state[0]
    assert ss.level("The Wine Cellar", "electronic") == RevealLevel.EXACT
    assert ss.level("The Wine Cellar", "physical") == RevealLevel.BUCKET
    assert ss.scouted_score("The Wine Cellar", "electronic") == 2
    assert ss.free_probes == 10
    assert ss.probes_spent_free == 4
    assert ss.rationale == "case the cheap one"


def test_legacy_campaign_loads_feature003_defaults():
    """A pre-feature campaign record loads with empty carryover/persistent/scout maps."""
    legacy = {
        "rounds_total": 3, "bankroll": 0, "banked_loot": 0,
        "standing_crew": [], "round_results": [],
    }
    c = campaign_from_dict(legacy)
    assert c.carryover_board == []
    assert c.persistent_slate_scores == {}
    assert c.per_ai_scout_state == {}
