from __future__ import annotations

from heist.campaign import run_campaign, settle_round
from heist.content import DEFAULT_PROMPT, JOBS, ROSTER
from heist.serialize import (
    _round_result_from_any,
    _round_result_to_dict,
    campaign_state_to_dict,
)
from heist.state import Campaign, Crew, HeistState, HiddenDepthRoll, RoundResult
from heist.stub_responses import build_stub_ai


def _make_state(crew, job=None, take=1_000_000, escape_success=True, heat=0):
    job = job or JOBS[0]
    hidden = HiddenDepthRoll(
        element=job.hidden_depth[0],
        reward_label="test",
        reward_amount=take,
    )
    state = HeistState(crew=crew, job=job, hidden_depth=hidden)
    state.final_take = take
    state.escape_success = escape_success
    state.heat = heat
    return state


def _make_campaign(crew_members=None, notoriety=0):
    from heist.content import BANKROLL

    members = crew_members or ROSTER[:4]
    return Campaign(
        rounds_total=10,
        bankroll=BANKROLL,
        banked_loot=0,
        standing_crew=list(members),
        notoriety=notoriety,
        attempted_job_names=set(),
        round_results=[],
    )


def test_settle_round_banks_take():
    campaign = _make_campaign()
    state = _make_state(Crew(list(campaign.standing_crew)))

    ended = settle_round(campaign, state)

    assert ended is False
    assert campaign.banked_loot == 1_000_000
    assert isinstance(campaign.round_results[0], RoundResult)


def test_settle_round_no_capture_on_success():
    campaign = _make_campaign()
    original_ids = [c.id for c in campaign.standing_crew]
    state = _make_state(Crew(list(campaign.standing_crew)), escape_success=True)

    settle_round(campaign, state)

    assert [c.id for c in campaign.standing_crew] == original_ids


def test_settle_round_capture_on_failed_escape():
    # Per design: a failed escape catches exactly one member; the rest escape with the loot.
    members = ROSTER[:2]
    campaign = _make_campaign(crew_members=members)
    state = _make_state(Crew(list(members)), escape_success=False)
    state.caught_member_ids = [members[0].id]  # one member is caught

    settle_round(campaign, state)

    assert len(campaign.standing_crew) == 1
    assert campaign.standing_crew[0].id == members[1].id


def test_settle_round_notoriety_accumulates_and_decays():
    campaign = _make_campaign()
    state1 = _make_state(Crew(list(campaign.standing_crew)), heat=3)

    settle_round(campaign, state1, notoriety_decay=1)
    assert campaign.notoriety == 2

    state2 = _make_state(Crew(list(campaign.standing_crew)), take=0, heat=0)
    settle_round(campaign, state2, notoriety_decay=1)
    assert campaign.notoriety == 1


def test_settle_round_records_notoriety_window_and_caught_ids():
    members = ROSTER[:2]
    campaign = _make_campaign(crew_members=members, notoriety=4)
    caught_id = members[0].id
    state = _make_state(Crew(list(members)), heat=3)
    state.caught_member_ids = [caught_id]

    settle_round(campaign, state, notoriety_decay=2)

    rr = campaign.round_results[0]
    assert rr.notoriety_before == 4
    assert rr.notoriety_after == 5
    assert rr.caught_member_ids == [caught_id]


def test_settle_round_crew_wipe_ends_campaign():
    # Crew wipe can happen when all members are caught across scenes + escape.
    members = ROSTER[:4]
    campaign = _make_campaign(crew_members=members)
    state = _make_state(Crew(list(members)), escape_success=False)
    state.caught_member_ids = [m.id for m in members]  # all caught

    ended = settle_round(campaign, state)

    assert ended is True
    assert campaign.standing_crew == []


def test_settle_round_critical_notoriety_ends_campaign():
    campaign = _make_campaign(notoriety=8)
    state = _make_state(Crew(list(campaign.standing_crew)), take=0, heat=2)

    ended = settle_round(campaign, state, notoriety_decay=1)

    assert campaign.notoriety == 9
    assert ended is True


def test_settle_round_marks_job_attempted():
    campaign = _make_campaign()
    state = _make_state(Crew(list(campaign.standing_crew)))

    settle_round(campaign, state)

    assert state.job.name in campaign.attempted_job_names


def test_settle_round_round_idx_increments():
    campaign = _make_campaign()
    state = _make_state(Crew(list(campaign.standing_crew)))

    assert campaign.round_idx == 0
    settle_round(campaign, state)
    assert campaign.round_idx == 1
    assert campaign.round_results[0].round_idx == 0


def test_round_result_crew_ids_round_trip():
    rr = RoundResult(
        round_idx=0,
        job_name="Test Job",
        take=123,
        aborted=False,
        escape_success=True,
        heat=1,
        crew_ids=[1, 2, 3],
    )

    restored = _round_result_from_any(_round_result_to_dict(rr))

    assert restored.crew_ids == [1, 2, 3]


def test_settle_round_records_crew_snapshot_before_removal():
    members = ROSTER[:3]
    campaign = _make_campaign(crew_members=members)
    state = _make_state(Crew(list(members)))
    state.caught_member_ids = [members[1].id]

    settle_round(campaign, state)

    rr = campaign.round_results[-1]
    assert rr.crew_ids == [m.id for m in members]
    assert [c.id for c in campaign.standing_crew] == [members[0].id, members[2].id]


def test_campaign_state_to_dict_emits_round_crew_snapshot():
    members = ROSTER[:3]
    campaign = _make_campaign(crew_members=members)
    caught_id = members[1].id
    round_result = RoundResult(
        round_idx=0,
        job_name="Test Job",
        take=500,
        aborted=False,
        escape_success=True,
        heat=0,
        caught_member_ids=[caught_id],
        crew_ids=[m.id for m in members],
    )
    game_states = [{
        "ai_idx": 0,
        "ai_name": "AI 1",
        "banked_loot": 0,
        "standing_crew": list(campaign.standing_crew),
        "round_results": [round_result],
    }]

    state = campaign_state_to_dict(campaign, game_states, list(ROSTER))
    round_rows = state["standings"][0]["round_results"]

    assert len(round_rows) == 1
    crew = round_rows[0]["crew"]
    assert crew
    captured_member = next(member for member in crew if member["id"] == caught_id)
    safe_member = next(member for member in crew if member["id"] != caught_id)
    assert captured_member["captured"] is True
    assert safe_member["captured"] is False


def test_run_campaign_stub_completes():
    campaign, extras = run_campaign(DEFAULT_PROMPT, build_stub_ai(), rounds=3)

    assert len(campaign.round_results) >= 1
    assert campaign.banked_loot >= 0
    assert len(extras) == len(campaign.round_results)
    job_names = [r.job_name for r in campaign.round_results]
    assert len(job_names) == len(set(job_names))
