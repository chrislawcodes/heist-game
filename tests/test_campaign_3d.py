from __future__ import annotations

from types import SimpleNamespace

from heist.campaign import _opening_wire_call
from heist.content import ROSTER, ROSTER_BY_ID
from heist.serialize import (
    _coverage_from_crew,
    campaign_from_dict,
    campaign_state_to_dict,
    campaign_to_dict,
)
from heist.state import Campaign, RoundResult
from heist.stub_responses import build_stub_ai


def _campaign() -> Campaign:
    camp = Campaign(
        rounds_total=10,
        bankroll=2_000_000,
        banked_loot=0,
        standing_crew=list(ROSTER[:4]),
        notoriety=0,
        attempted_job_names=set(),
        round_results=[],
        between_round_log=[],
    )
    camp.game_id = 77
    return camp


def _entry(
    ai_idx: int,
    ai_name: str,
    banked: int,
    crew_ids: list[int],
    *,
    status: str = "waiting",
    round_results: list[dict] | None = None,
    round_game_ids: list[int | None] | None = None,
    caught: list[int] | None = None,
) -> dict:
    crew = []
    for cid in crew_ids:
        char = ROSTER_BY_ID[cid]
        crew.append({
            "id": char.id,
            "char_id": char.id,
            "name": char.name,
            "skills": {k: v.name for k, v in char.skills.items()},
            "captured": bool(caught and cid in caught),
        })
    return {
        "ai_idx": ai_idx,
        "ai_name": ai_name,
        "ai_game_id": 1000 + ai_idx,
        "banked_loot": banked,
        "notoriety": ai_idx,
        "status": status,
        "crew": crew,
        "round_results": round_results or [],
        "round_game_ids": round_game_ids or [],
        "caught_member_ids": caught or [],
        "reflection": {"learned": f"{ai_name} learned", "plan": f"{ai_name} plans"},
    }


def test_campaign_state_to_dict_sorts_standings_by_banked_desc():
    camp = _campaign()
    state = campaign_state_to_dict(
        camp,
        [
            _entry(0, "Aegis", 200, [1, 4, 7, 13], status="done"),
            _entry(1, "Ghost", 500, [2, 5, 8, 14], status="running"),
            _entry(2, "Nova", 300, [3, 6, 9, 16], status="waiting"),
        ],
        ROSTER,
    )

    assert [row["ai_name"] for row in state["standings"]] == ["Ghost", "Nova", "Aegis"]
    assert [row["rank"] for row in state["standings"]] == [1, 2, 3]
    assert state["standings"][0]["ai_game_id"] == 1001


def test_campaign_state_to_dict_marks_captured_crew_members():
    camp = _campaign()
    state = campaign_state_to_dict(
        camp,
        [
            _entry(0, "Aegis", 200, [1, 4, 7, 13], status="done", caught=[4, 13]),
        ],
        ROSTER,
    )

    crew = state["standings"][0]["crew"]
    captured = {member["char_id"] for member in crew if member["captured"]}
    assert captured == {4, 13}


def test_campaign_state_to_dict_coverage_uses_active_crew_only():
    camp = _campaign()
    state = campaign_state_to_dict(
        camp,
        [
            _entry(0, "Aegis", 200, [1, 9, 10, 13], status="done", caught=[10, 13]),
        ],
        ROSTER,
    )

    crew = state["standings"][0]["crew"]
    coverage = _coverage_from_crew(crew)
    assert coverage["hack"] == 3  # Marcus "Prodigy" Renault
    assert coverage["safe"] == 0  # captured Rook is ignored
    assert coverage["soc"] == 2   # Pearl Sutton
    assert coverage["musc"] == 1  # Pearl Sutton's low muscle support
    assert coverage["drive"] == 1  # Marcus' low driver support


def test_between_round_log_roundtrip_preserves_data():
    camp = _campaign()
    camp.between_round_log.append({
        "round": 3,
        "ai_idx": 1,
        "ai_name": "Ghost",
        "reflection": {"learned": "A", "plan": "B"},
        "trash_talk": {
            "speaker_char_id": 4,
            "target_ai_name": "Aegis",
            "text": "Run it back.",
        },
    })
    camp.round_results.append(RoundResult(0, "Museum Gala", 1200000, False, True, 1))

    restored = campaign_from_dict(campaign_to_dict(camp))
    assert restored.between_round_log == camp.between_round_log
    assert restored.round_results == camp.round_results
    assert getattr(restored, "game_id", None) == 77


def test_opening_wire_call_falls_back_to_active_speaker():
    camp = _campaign()
    ai = build_stub_ai()
    game_states = [
        {
            "ai_idx": 0,
            "ai_name": "Aegis",
            "ai_game_id": 501,
            "ai": ai,
            "banked_loot": 3_200_000,
            "notoriety": 4,
            "status": "done",
            "crew": [
                {
                    "id": 4,
                    "char_id": 4,
                    "name": ROSTER_BY_ID[4].name,
                    "skills": {k: v.name for k, v in ROSTER_BY_ID[4].skills.items()},
                    "captured": False,
                },
                {
                    "id": 10,
                    "char_id": 10,
                    "name": ROSTER_BY_ID[10].name,
                    "skills": {k: v.name for k, v in ROSTER_BY_ID[10].skills.items()},
                    "captured": False,
                },
            ],
            "job_name": "City Hall Records",
            "take": 1_100_000,
            "escape_success": True,
            "caught_member_ids": [],
        },
        {
            "ai_idx": 1,
            "ai_name": "Ghost",
            "ai_game_id": 502,
            "banked_loot": 2_900_000,
            "notoriety": 3,
            "status": "running",
            "crew": [
                {
                    "id": 1,
                    "char_id": 1,
                    "name": ROSTER_BY_ID[1].name,
                    "skills": {k: v.name for k, v in ROSTER_BY_ID[1].skills.items()},
                    "captured": False,
                },
            ],
            "job_name": "Armored Car",
            "take": 750_000,
            "escape_success": False,
            "caught_member_ids": [1],
        },
    ]

    def fake_call_json(ai_obj, prompt, label, logs, emit):
        return (
            SimpleNamespace(text='{"ok": true}', session_id="stub"),
            {
                "speaker_char_id": 999,
                "target_ai_name": "Nope",
                "text": "You missed your shot.",
            },
        )

    from heist import campaign as campaign_mod

    original = campaign_mod._call_json
    campaign_mod._call_json = fake_call_json
    try:
        # round_idx=3 > 0 triggers trash-talk variant
        result = _opening_wire_call(camp, 0, 3, ai, game_states, [], lambda evt: None)
    finally:
        campaign_mod._call_json = original

    assert result["trash_talk"]["speaker_char_id"] == 4
    assert result["trash_talk"]["target_ai_name"] == "Ghost"
    assert camp.between_round_log[-1]["trash_talk"]["speaker_char_id"] == 4
    assert camp.between_round_log[-1]["stage"] == "trash_talk"


def test_campaign_state_to_dict_includes_round_results():
    campaign = _campaign()
    campaign.round_results.append(
        RoundResult(0, "Museum Gala", 500_000, False, True, 1)
    )
    game_states = [
        _entry(
            0,
            "Aegis",
            200,
            [1, 4, 7, 13],
            status="done",
            round_results=[
                {
                    "round_idx": 0,
                    "job_name": "Museum Gala",
                    "take": 500_000,
                    "aborted": False,
                    "escape_success": True,
                    "heat": 1,
                }
            ],
            round_game_ids=[42],
        )
    ]

    state = campaign_state_to_dict(campaign, game_states, ROSTER)
    rr = state["standings"][0]["round_results"]
    assert len(rr) == 1
    assert rr[0]["job_name"] == "Museum Gala"
    assert rr[0]["take"] == 500_000
    assert rr[0]["escape"] == "clean"
    assert rr[0]["round_idx"] == 0
    assert rr[0]["game_id"] == 42


def test_campaign_state_to_dict_round_game_ids_zip():
    """round_game_ids are zipped correctly into per-round result dicts."""
    from heist.state import RoundResult

    campaign = _campaign()
    campaign.round_results.append(
        RoundResult(0, "Museum Gala", 500_000, False, True, 1)
    )
    campaign.round_results.append(
        RoundResult(1, "Armored Car", 300_000, False, False, 2)
    )
    game_states = [
        _entry(
            0,
            "Aegis",
            200,
            [1, 4, 7, 13],
            round_results=[
                {
                    "round_idx": 0,
                    "job_name": "Museum Gala",
                    "take": 500_000,
                    "aborted": False,
                    "escape_success": True,
                    "heat": 1,
                },
                {
                    "round_idx": 1,
                    "job_name": "Armored Car",
                    "take": 300_000,
                    "aborted": False,
                    "escape_success": False,
                    "heat": 2,
                },
            ],
            round_game_ids=[101, 102],
        )
    ]
    state = campaign_state_to_dict(campaign, game_states, ROSTER)
    rr = state["standings"][0]["round_results"]
    assert rr[0]["game_id"] == 101
    assert rr[1]["game_id"] == 102
