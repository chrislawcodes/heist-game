import json
from subprocess import CompletedProcess
from unittest.mock import patch

from agents import Turn, ask_codex, ask_gemini

CODEX_JSONL = "\n".join([
    json.dumps({"type": "thread.started", "thread_id": "abc-123"}),
    json.dumps({"type": "turn.started"}),
    json.dumps({
        "type": "item.completed",
        "item": {"id": "item_0", "type": "agent_message", "text": "pong"},
    }),
    json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}),
])

GEMINI_JSON = json.dumps({
    "session_id": "gem-555",
    "response": "pong",
    "stats": {"models": {}},
})


def _mock_run(stdout: str) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_codex_first_turn_captures_session_and_message():
    with patch("agents.subprocess.run", return_value=_mock_run(CODEX_JSONL)) as m:
        result = ask_codex("hello")
    assert result == Turn(text="pong", session_id="abc-123")
    cmd = m.call_args.args[0]
    assert cmd[:2] == ["codex", "exec"]
    assert "resume" not in cmd
    assert "--sandbox" in cmd and "read-only" in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--json" in cmd
    assert cmd[-1] == "hello"


def test_codex_resume_uses_session_id_and_skips_sandbox():
    with patch("agents.subprocess.run", return_value=_mock_run(CODEX_JSONL)) as m:
        result = ask_codex("hello again", session_id="xyz-789")
    assert result == Turn(text="pong", session_id="xyz-789")
    cmd = m.call_args.args[0]
    assert cmd[:3] == ["codex", "exec", "resume"]
    assert cmd[3] == "xyz-789"
    assert "--sandbox" not in cmd
    assert cmd[-1] == "hello again"


def test_codex_picks_agent_message_among_multiple_items():
    reasoning = {"type": "item.completed", "item": {"type": "reasoning", "text": "thinking..."}}
    message = {"type": "item.completed", "item": {"type": "agent_message", "text": "answer"}}
    jsonl = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "abc"}),
        json.dumps(reasoning),
        json.dumps(message),
        json.dumps({"type": "turn.completed", "usage": {}}),
    ])
    with patch("agents.subprocess.run", return_value=_mock_run(jsonl)):
        result = ask_codex("q")
    assert result.text == "answer"


def test_gemini_strips_warning_prefix_before_json():
    noisy = "MCP issues detected. Run /mcp list for status." + GEMINI_JSON
    with patch("agents.subprocess.run", return_value=_mock_run(noisy)):
        result = ask_gemini("hello")
    assert result == Turn(text="pong", session_id="gem-555")


def test_gemini_first_turn_command_shape():
    with patch("agents.subprocess.run", return_value=_mock_run(GEMINI_JSON)) as m:
        ask_gemini("hello")
    cmd = m.call_args.args[0]
    assert cmd[:3] == ["gemini", "-o", "json"]
    assert "--resume" not in cmd
    assert cmd[-2:] == ["-p", "hello"]


def test_gemini_resume_command_shape():
    with patch("agents.subprocess.run", return_value=_mock_run(GEMINI_JSON)) as m:
        ask_gemini("hello again", session_id="gem-555")
    cmd = m.call_args.args[0]
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "gem-555"
    assert cmd[-2:] == ["-p", "hello again"]
