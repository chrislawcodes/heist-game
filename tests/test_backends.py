"""Verify the real Heist AI backends propagate session_id correctly across
calls so the underlying CLI sees a single continuous session per heist."""

from unittest.mock import patch

from agents import Turn
from heist.backends import CodexHeistAI, GeminiHeistAI


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
