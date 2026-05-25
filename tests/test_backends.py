"""Verify the real Heist AI backends propagate session_id correctly across
calls so the underlying CLI sees a single continuous session per heist."""

from unittest.mock import patch

import pytest

import heist.backends as backends
from agents import Turn
from heist.backends import AI_MAX_ATTEMPTS, CodexHeistAI, GeminiHeistAI, _ask_with_retries


def test_codex_first_call_passes_none_session_id():
    with patch("heist.backends.ask_codex") as mock:
        mock.return_value = Turn(text='{"x": 1}', session_id="sess-1")
        ai = CodexHeistAI()
        ai.ask("first")
    assert mock.call_args.kwargs.get("session_id") is None


def test_codex_subsequent_calls_reuse_session_id():
    with patch("heist.backends.ask_codex") as mock:
        mock.side_effect = [
            Turn(text='{"a": 1}', session_id="sess-abc"),
            Turn(text='{"b": 2}', session_id="sess-abc"),
            Turn(text='{"c": 3}', session_id="sess-abc"),
        ]
        ai = CodexHeistAI()
        ai.ask("turn 1")
        ai.ask("turn 2")
        ai.ask("turn 3")
    # First call: no session_id. Subsequent: session_id from prior turn.
    assert mock.call_args_list[0].kwargs.get("session_id") is None
    assert mock.call_args_list[1].kwargs.get("session_id") == "sess-abc"
    assert mock.call_args_list[2].kwargs.get("session_id") == "sess-abc"


def test_codex_returns_agent_turn_with_text_and_session():
    with patch("heist.backends.ask_codex") as mock:
        mock.return_value = Turn(text="hello", session_id="sess-xyz")
        result = CodexHeistAI().ask("p")
    assert result.text == "hello"
    assert result.session_id == "sess-xyz"


def test_gemini_first_call_passes_none_session_id():
    with patch("heist.backends.ask_gemini") as mock:
        mock.return_value = Turn(text='{"x": 1}', session_id="gem-1")
        ai = GeminiHeistAI()
        ai.ask("first")
    assert mock.call_args.kwargs.get("session_id") is None


def test_gemini_subsequent_calls_reuse_session_id():
    with patch("heist.backends.ask_gemini") as mock:
        mock.side_effect = [
            Turn(text='{"x": 1}', session_id="gem-555"),
            Turn(text='{"y": 2}', session_id="gem-555"),
        ]
        ai = GeminiHeistAI()
        ai.ask("turn 1")
        ai.ask("turn 2")
    assert mock.call_args_list[0].kwargs.get("session_id") is None
    assert mock.call_args_list[1].kwargs.get("session_id") == "gem-555"


# ── Retry policy: every in-game AI call gets AI_MAX_ATTEMPTS tries ────────────

@pytest.fixture
def _no_retry_delay(monkeypatch):
    # Keep retry tests instant.
    monkeypatch.setattr(backends, "AI_RETRY_DELAY_SECONDS", 0)


def test_ask_with_retries_succeeds_after_transient_failures(_no_retry_delay):
    """Fails the first attempts but succeeds on the last — the retries recover
    the transient failure rather than skipping. Returns the winning attempt's
    number and a clean per-attempt latency."""
    calls = {"n": 0}

    def call() -> Turn:
        calls["n"] += 1
        if calls["n"] < AI_MAX_ATTEMPTS:
            raise TimeoutError("transient hang")
        return Turn(text="ok", session_id="s")

    result, attempts, attempt_ms = _ask_with_retries(call)
    assert result.text == "ok"
    assert calls["n"] == AI_MAX_ATTEMPTS
    assert attempts == AI_MAX_ATTEMPTS
    assert isinstance(attempt_ms, int) and attempt_ms >= 0


def test_ask_with_retries_raises_only_after_all_attempts_fail(_no_retry_delay):
    """A call that fails every time is attempted exactly AI_MAX_ATTEMPTS times
    before the exception propagates — we never skip on the first blip."""
    calls = {"n": 0}

    def call() -> Turn:
        calls["n"] += 1
        raise TimeoutError("still hung")

    with pytest.raises(TimeoutError):
        _ask_with_retries(call)
    assert calls["n"] == AI_MAX_ATTEMPTS


def test_ask_with_retries_no_retry_on_first_success(_no_retry_delay):
    """A call that succeeds immediately is made exactly once and reports
    attempts == 1 — the clean, common case."""
    calls = {"n": 0}

    def call() -> Turn:
        calls["n"] += 1
        return Turn(text="fast", session_id="s")

    result, attempts, attempt_ms = _ask_with_retries(call)
    assert result.text == "fast"
    assert calls["n"] == 1
    assert attempts == 1
    assert isinstance(attempt_ms, int) and attempt_ms >= 0


def test_ask_with_retries_calls_on_attempt_for_each_try(_no_retry_delay):
    calls = {"n": 0}
    attempts_seen: list[tuple[int, int]] = []

    def call() -> Turn:
        calls["n"] += 1
        if calls["n"] < AI_MAX_ATTEMPTS:
            raise TimeoutError("transient hang")
        return Turn(text="ok", session_id="s")

    def on_attempt(attempt: int, max_attempts: int) -> None:
        attempts_seen.append((attempt, max_attempts))

    result, attempts, attempt_ms = _ask_with_retries(call, on_attempt=on_attempt)
    assert result.text == "ok"
    assert calls["n"] == AI_MAX_ATTEMPTS
    assert attempts == AI_MAX_ATTEMPTS
    assert attempts_seen == [(1, AI_MAX_ATTEMPTS), (2, AI_MAX_ATTEMPTS), (3, AI_MAX_ATTEMPTS)]
    assert isinstance(attempt_ms, int) and attempt_ms >= 0


def test_ask_with_retries_ignores_bad_on_attempt_callback(_no_retry_delay):
    def call() -> Turn:
        return Turn(text="ok", session_id="s")

    def on_attempt(attempt: int, max_attempts: int) -> None:
        raise RuntimeError(f"bad callback on attempt {attempt}/{max_attempts}")

    result, attempts, attempt_ms = _ask_with_retries(call, on_attempt=on_attempt)
    assert result.text == "ok"
    assert attempts == 1
    assert isinstance(attempt_ms, int) and attempt_ms >= 0


def test_codex_ask_records_clean_attempt_stats(_no_retry_delay):
    """Through the real CodexHeistAI.ask path: a backend that times out twice
    then returns is retried, succeeds, and records the winning attempt number
    plus a clean per-attempt latency for the ai_call log to surface."""
    ai = CodexHeistAI()
    with patch("heist.backends.ask_codex") as mock:
        mock.side_effect = [
            TimeoutError("hang 1"),
            TimeoutError("hang 2"),
            Turn(text="recovered", session_id="sess-r"),
        ]
        result = ai.ask("p")
    assert result.text == "recovered"
    assert mock.call_count == AI_MAX_ATTEMPTS
    assert ai.last_attempts == AI_MAX_ATTEMPTS
    assert isinstance(ai.last_attempt_ms, int) and ai.last_attempt_ms >= 0


def test_codex_ask_clean_stats_on_first_try():
    """A call that succeeds first try records attempts == 1."""
    ai = CodexHeistAI()
    with patch("heist.backends.ask_codex") as mock:
        mock.return_value = Turn(text="ok", session_id="s")
        ai.ask("p")
    assert ai.last_attempts == 1
