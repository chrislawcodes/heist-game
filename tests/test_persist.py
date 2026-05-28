"""Tests for the on-disk persistence layer (heist.persist)."""
from __future__ import annotations

import os

import pytest

from heist import persist


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """Point persist.py at a per-test temp dir."""
    monkeypatch.setenv("HEIST_STATE_DIR", str(tmp_path / "state"))
    yield


def _sample_game(gid: int = 1) -> dict:
    return {
        "id": gid,
        "created_at": 12345.6,
        "status": "running",
        "ais": [{"prompt": "test", "agent": "stub"}],
        "ai_results": [None],
        "ais_remaining": 1,
        "job": None,
        "take": None,
        "aborted": None,
        "escape_success": None,
        "events": [
            {"type": "crew_known", "ai_idx": 0, "crew": {"members": [], "total_cost": 0}},
            {"type": "scene_done", "ai_idx": 0, "scene_num": 1},
        ],
    }


def test_save_load_game_record_roundtrip():
    game = _sample_game(7)
    persist.save_game_record(game)
    loaded = persist.load_game_records()
    assert 7 in loaded
    assert loaded[7] == game


def test_load_game_records_empty_returns_empty_dict():
    assert persist.load_game_records() == {}


def test_load_game_records_ignores_unparseable_and_tmp_files(tmp_path):
    persist.save_game_record(_sample_game(1))
    games_dir = tmp_path / "state" / "games"

    # Corrupt JSON file → ignored.
    (games_dir / "2.json").write_text("{not json")
    # A tmp file from an interrupted atomic write → ignored.
    (games_dir / "3.json.tmp.99999.1").write_text("{}")
    # A non-numeric stem → ignored.
    (games_dir / "weird.json").write_text("{}")

    loaded = persist.load_game_records()
    assert set(loaded.keys()) == {1}


def test_delete_game_record_idempotent():
    persist.save_game_record(_sample_game(4))
    assert 4 in persist.load_game_records()
    persist.delete_game_record(4)
    assert 4 not in persist.load_game_records()
    # Second delete: no error.
    persist.delete_game_record(4)


def test_runner_snapshot_roundtrip_preserves_nested_data():
    snap = {
        "game_id": 1,
        "ai_idx": 2,
        "agent": "codex-mini",
        "session_id": "abc123",
        "stage": "in_scene",
        "scene_idx": 3,
        "rng_state": "deadbeef",
        "state": {
            "crew": {"members": [{"id": 1, "name": "x"}], "total_cost": 100},
            "scene_results": [{"scene": {"number": 1}}],
            "nested": {"deep": [1, 2, {"k": "v"}]},
        },
        "extras": {"casting_summary": "...", "epilogue": ""},
    }
    persist.save_runner_snapshot(1, 2, snap)
    loaded = persist.load_runner_snapshot(1, 2)
    assert loaded == snap


def test_load_runner_snapshot_missing_returns_none():
    assert persist.load_runner_snapshot(99, 0) is None


def test_delete_runner_snapshot_idempotent_and_prunes_dir(tmp_path):
    persist.save_runner_snapshot(5, 0, {"x": 1})
    snap_dir = tmp_path / "state" / "games" / "5"
    assert snap_dir.is_dir()
    persist.delete_runner_snapshot(5, 0)
    # Dir is auto-pruned when empty.
    assert not snap_dir.exists()
    # Idempotent.
    persist.delete_runner_snapshot(5, 0)


def test_list_pending_snapshots_multi_ai():
    persist.save_runner_snapshot(10, 0, {"ai_idx": 0})
    persist.save_runner_snapshot(10, 1, {"ai_idx": 1})
    persist.save_runner_snapshot(10, 5, {"ai_idx": 5})
    snaps = persist.list_pending_snapshots(10)
    assert set(snaps.keys()) == {0, 1, 5}
    assert snaps[1] == {"ai_idx": 1}


def test_list_pending_snapshots_ignores_tmp_files(tmp_path):
    persist.save_runner_snapshot(11, 0, {"x": 1})
    snap_dir = tmp_path / "state" / "games" / "11"
    (snap_dir / "ai-2.json.tmp.99999.1").write_text("{}")
    (snap_dir / "ai-bad.json").write_text("{}")  # non-numeric idx
    snaps = persist.list_pending_snapshots(11)
    assert set(snaps.keys()) == {0}


def test_atomic_write_leaves_no_tmp_on_success(tmp_path):
    persist.save_game_record(_sample_game(1))
    games_dir = tmp_path / "state" / "games"
    tmps = [p for p in games_dir.iterdir() if ".tmp." in p.name]
    assert tmps == []


def test_atomic_write_survives_concurrent_writers(tmp_path):
    """Two threads writing the same file shouldn't corrupt it."""
    import threading

    def writer(n: int) -> None:
        for _ in range(20):
            persist.save_game_record({**_sample_game(42), "marker": n})

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    loaded = persist.load_game_records()
    assert 42 in loaded
    assert loaded[42]["marker"] in (0, 1, 2, 3)
    # No leftover tmp files.
    games_dir = tmp_path / "state" / "games"
    assert [p for p in games_dir.iterdir() if ".tmp." in p.name] == []


def test_state_dir_respects_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("HEIST_STATE_DIR", str(custom))
    persist.save_game_record(_sample_game(1))
    assert (custom / "games" / "1.json").is_file()


def test_rng_state_roundtrip():
    import random
    rng1 = random.Random(42)
    rng1.random()  # consume one value so state diverges from a fresh seed
    encoded = persist._serialize_rng(rng1)
    rng2 = random.Random()
    persist._deserialize_rng_into(rng2, encoded)
    # Same sequence after restore.
    assert [rng1.random() for _ in range(5)] == [rng2.random() for _ in range(5)]


def test_save_game_record_overwrites_existing():
    persist.save_game_record(_sample_game(1))
    g = _sample_game(1)
    g["status"] = "done"
    persist.save_game_record(g)
    loaded = persist.load_game_records()
    assert loaded[1]["status"] == "done"


def test_load_uses_filename_as_authoritative_id(tmp_path):
    # Even if the record's "id" disagrees with the filename, the filename wins.
    games_dir = tmp_path / "state" / "games"
    games_dir.mkdir(parents=True)
    (games_dir / "9.json").write_text('{"id": 999, "status": "done"}')
    loaded = persist.load_game_records()
    assert 9 in loaded
    assert loaded[9]["id"] == 9


def test_fsync_path_does_not_leak_tmp(tmp_path, monkeypatch):
    """If os.replace fails (simulate via permission), tmp file should still
    be cleaned up."""
    persist.save_game_record(_sample_game(1))
    games_dir = tmp_path / "state" / "games"

    real_replace = os.replace
    calls = {"n": 0}

    def boom(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated rename failure")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        persist.save_game_record(_sample_game(2))
    # No tmp files left behind.
    assert [p for p in games_dir.iterdir() if ".tmp." in p.name] == []


# ── premade crews ─────────────────────────────────────────────────────────────


def _sample_crew(name: str = "The Operators") -> dict:
    return {"name": name, "agent": "codex-mini", "prompt": "Run a quiet, surgical heist."}


def test_add_and_load_crew_roundtrip():
    stored = persist.add_crew(_sample_crew())
    assert stored["id"]
    assert stored["created_at"] > 0
    crews = persist.load_crews()
    assert len(crews) == 1
    assert crews[0]["name"] == "The Operators"
    assert crews[0]["agent"] == "codex-mini"
    assert crews[0]["prompt"] == "Run a quiet, surgical heist."
    assert crews[0]["id"] == stored["id"]


def test_delete_crew_removes_only_target():
    a = persist.add_crew(_sample_crew("A"))
    b = persist.add_crew(_sample_crew("B"))
    assert persist.delete_crew(a["id"]) is True
    remaining = persist.load_crews()
    assert [c["id"] for c in remaining] == [b["id"]]
    # Deleting an unknown id is a no-op returning False.
    assert persist.delete_crew("does-not-exist") is False
    assert len(persist.load_crews()) == 1


def test_load_crews_missing_file_returns_empty():
    assert persist.load_crews() == []


def test_load_crews_corrupt_file_returns_empty():
    path = persist._crews_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert persist.load_crews() == []


def test_load_crews_non_list_payload_returns_empty():
    persist._atomic_write(persist._crews_path(), {"crews": "nope"})
    assert persist.load_crews() == []


def test_load_crews_skips_malformed_entries():
    persist._atomic_write(
        persist._crews_path(),
        {"crews": [
            {"id": "x", "name": "Good", "prompt": "p", "agent": "stub"},
            {"id": "y", "name": "No prompt", "agent": "stub"},  # dropped
            {"name": "No id", "prompt": "p"},                    # dropped
        ]},
    )
    crews = persist.load_crews()
    assert [c["name"] for c in crews] == ["Good"]


def test_duplicate_names_keep_distinct_ids():
    a = persist.add_crew(_sample_crew("Twins"))
    b = persist.add_crew(_sample_crew("Twins"))
    assert a["id"] != b["id"]
    names = [c["name"] for c in persist.load_crews()]
    assert names == ["Twins", "Twins"]
