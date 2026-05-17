"""Real Heist AI backends.

Each backend wraps one of the CLI invokers in the repo-root `agents.py` module
(`ask_codex`, `ask_gemini`) and threads its `session_id` across every call,
so a single heist run corresponds to a single CLI session. That continuity
is the design doc's "Use a single Heist AI instance throughout, maintaining
conversation context" requirement.
"""

from __future__ import annotations

from agents import Turn, ask_codex, ask_gemini
from heist.ai import AgentTurn


class CodexHeistAI:
    def __init__(self) -> None:
        self.session_id: str | None = None

    def ask(self, prompt: str) -> AgentTurn:
        result: Turn = ask_codex(prompt, session_id=self.session_id)
        self.session_id = result.session_id
        return AgentTurn(text=result.text, session_id=result.session_id)


class GeminiHeistAI:
    def __init__(self) -> None:
        self.session_id: str | None = None

    def ask(self, prompt: str) -> AgentTurn:
        result: Turn = ask_gemini(prompt, session_id=self.session_id)
        self.session_id = result.session_id
        return AgentTurn(text=result.text, session_id=result.session_id)
