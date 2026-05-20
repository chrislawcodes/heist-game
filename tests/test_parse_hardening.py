"""Tests for the JSON parse hardening layer: deterministic repairs in
``parse_json_block`` and parse-failure retries in ``runner._call_json``."""

import pytest

from heist.ai import AgentTurn, parse_json_block
from heist.runner import _call_json

# --- Repair tests (parse_json_block directly) ---------------------------------


def test_repairs_trailing_escaped_quote_regression():
    # The exact production crash: the model escaped a trailing dialogue quote
    # but forgot the JSON string's own closing quote before the brace.
    # In a Python literal the malformed input is: {"narration":"hi there.\"}
    malformed = '{"narration":"hi there.\\"}'
    result = parse_json_block(malformed)
    assert isinstance(result, dict)
    # The recovered narration retains the escaped dialogue quote at the end.
    assert result["narration"].endswith('"')
    assert result["narration"] == 'hi there."'


def test_repairs_trailing_comma_object():
    assert parse_json_block('{"a": 1,}') == {"a": 1}


def test_repairs_trailing_comma_array():
    assert parse_json_block('{"a": [1, 2,]}') == {"a": [1, 2]}


def test_repairs_truncated_string_with_brace_inside():
    # Response cut off mid-string; the only `}` lands inside the unterminated
    # string. The closing-quote repair closes the string before the brace.
    assert parse_json_block('{"narration": "the end}') == {"narration": "the end"}


def test_valid_json_is_untouched():
    # Clean parse path: value comes back exactly, no repair needed.
    assert parse_json_block('{"a": "b"}') == {"a": "b"}


def test_markdown_fenced_valid_json_still_parses():
    text = '```json\n{"x": 1}\n```'
    assert parse_json_block(text) == {"x": 1}


def test_unfixable_garbage_raises_valueerror():
    with pytest.raises(ValueError):
        parse_json_block("no json here")


def test_unfixable_broken_json_raises_valueerror():
    # Has braces but is irreparably broken.
    with pytest.raises(ValueError):
        parse_json_block('{"a": [1, 2, , 3]}')


# --- Retry tests (_call_json) -------------------------------------------------


class _ScriptedAI:
    """Minimal HeistAI: returns canned responses in order, tracks call count."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def ask(self, prompt: str) -> AgentTurn:
        idx = self.calls
        self.calls += 1
        text = self._responses[-1] if idx >= len(self._responses) else self._responses[idx]
        return AgentTurn(text=text, session_id="scripted")


def test_call_json_recovers_on_retry():
    ai = _ScriptedAI(["this is not json", '{"ok": true}'])
    logs: list = []
    turn, parsed = _call_json(ai, "prompt", "label", logs)
    assert parsed == {"ok": True}
    assert ai.calls == 2  # first failed, second recovered


def test_call_json_raises_after_exhausting_retries():
    ai = _ScriptedAI(["nope"])  # always malformed
    logs: list = []
    with pytest.raises(ValueError):
        _call_json(ai, "prompt", "label", logs, retries=2)
    assert ai.calls == 3  # retries + 1 attempts


def test_call_json_no_wasted_retries_on_first_success():
    ai = _ScriptedAI(['{"x": 1}'])
    logs: list = []
    turn, parsed = _call_json(ai, "prompt", "label", logs)
    assert parsed == {"x": 1}
    assert ai.calls == 1  # exactly one call, no retries
