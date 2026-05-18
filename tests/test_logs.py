"""Tests for heist.logs — the structured JSON-Lines logger."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from heist.logs import log


@pytest.fixture(autouse=True)
def isolate_log(tmp_path, monkeypatch):
    """Point the logger at a fresh file under tmp_path for every test."""
    target = tmp_path / "heist.jsonl"
    monkeypatch.setenv("HEIST_LOG_PATH", str(target))
    log._reset_for_tests()
    yield target
    log._reset_for_tests()


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_info_writes_one_valid_json_line(isolate_log):
    log.info("foo", x=1)
    records = _read_lines(isolate_log)
    assert len(records) == 1
    rec = records[0]
    assert rec["event"] == "foo"
    assert rec["level"] == "info"
    assert rec["x"] == 1
    assert "ts" in rec and "T" in rec["ts"]  # ISO-8601 with time component
    assert rec["source"]  # caller module name resolved


def test_warn_and_error_levels(isolate_log):
    log.warn("slow", elapsed_ms=5000)
    log.error("boom", error="kaboom")
    records = _read_lines(isolate_log)
    assert [r["level"] for r in records] == ["warn", "error"]
    assert records[0]["elapsed_ms"] == 5000
    assert records[1]["error"] == "kaboom"


def test_env_var_redirects_output(tmp_path, monkeypatch):
    # Override with a second distinct path mid-test
    redirected = tmp_path / "subdir" / "other.jsonl"
    monkeypatch.setenv("HEIST_LOG_PATH", str(redirected))
    log._reset_for_tests()
    log.info("hello")
    assert redirected.exists()
    records = _read_lines(redirected)
    assert records[0]["event"] == "hello"


def test_log_path_returns_absolute_string(isolate_log):
    p = log.log_path()
    assert os.path.isabs(p)
    assert p.endswith("heist.jsonl")


def test_concurrent_writes_dont_interleave(isolate_log):
    """Smoke test: 8 threads each writing 50 lines produce 400 valid JSON lines."""
    n_threads = 8
    n_writes = 50

    def worker(tid: int) -> None:
        for i in range(n_writes):
            log.info("concurrent", thread=tid, i=i, payload="x" * 50)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = _read_lines(isolate_log)
    assert len(records) == n_threads * n_writes
    # Every line parsed cleanly — i.e. no interleaving corrupted any record.
    for rec in records:
        assert rec["event"] == "concurrent"
        assert isinstance(rec["thread"], int)
        assert isinstance(rec["i"], int)


def test_non_serializable_field_falls_back_to_str(isolate_log):
    class Custom:
        def __repr__(self) -> str:
            return "<Custom obj>"

    log.info("weird", obj=Custom())
    records = _read_lines(isolate_log)
    assert records[0]["obj"] == "<Custom obj>"


def test_creates_parent_dir(tmp_path, monkeypatch):
    nested = tmp_path / "a" / "b" / "c" / "heist.jsonl"
    monkeypatch.setenv("HEIST_LOG_PATH", str(nested))
    log._reset_for_tests()
    log.info("dirs")
    assert nested.exists()
