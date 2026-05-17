"""Heist AI abstraction. Iteration 1 uses a stub that returns canned responses.
Iteration 3 will wire up the real codex/gemini backends via the existing
agents.py module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass
class AgentTurn:
    text: str
    session_id: str | None = None


class HeistAI(Protocol):
    def ask(self, prompt: str) -> AgentTurn: ...


class StubHeistAI:
    """Returns scripted responses in order. Useful for tests and iteration 1
    smoke-runs while real backends aren't wired yet."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._idx = 0
        self._asked: list[str] = []

    def ask(self, prompt: str) -> AgentTurn:
        self._asked.append(prompt)
        if self._idx >= len(self._responses):
            raise RuntimeError(
                f"StubHeistAI exhausted after {self._idx} turns; "
                f"latest prompt started with: {prompt[:120]!r}"
            )
        text = self._responses[self._idx]
        self._idx += 1
        return AgentTurn(text=text, session_id="stub-session")

    @property
    def prompts_seen(self) -> list[str]:
        return list(self._asked)


def parse_json_block(text: str) -> dict:
    """Parse a JSON object embedded in agent text. Strips common chatter."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"No JSON object found in agent response: {text[:200]!r}")
    snippet = text[start : end + 1]
    return json.loads(snippet)
