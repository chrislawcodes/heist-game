"""Heist AI abstraction. Iteration 1 uses a stub that returns canned responses.
Iteration 3 will wire up the real codex/gemini backends via the existing
agents.py module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from heist.logs import log


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


def _repair_json(snippet: str) -> tuple[dict, str] | None:
    """Try a sequence of conservative, deterministic repairs on a JSON snippet
    that failed a clean ``json.loads``. Returns ``(parsed, repair_name)`` on the
    first repair that parses, or ``None`` if every repair fails.

    Repairs only ever run AFTER a clean parse has failed, so valid JSON is never
    altered. Each repair is re-parsed independently; we never stack them.
    """
    # 1. Trailing escaped quote ate the terminator (the observed crash):
    #    a string ends on a line of dialogue serialized as `...\"}` — the model
    #    escaped the dialogue quote but forgot the string's own closing quote.
    #    Insert a real `"` immediately before the final `}`.
    if snippet.endswith("}"):
        candidate = snippet[:-1] + '"' + "}"
        try:
            return json.loads(candidate), "closing_quote"
        except json.JSONDecodeError:
            pass

    # 2. Trailing commas: `,}` → `}` and `,]` → `]` (a common LLM tic).
    candidate = snippet.replace(",}", "}").replace(",]", "]")
    if candidate != snippet:
        try:
            return json.loads(candidate), "trailing_comma"
        except json.JSONDecodeError:
            pass

    # 3. Truncation: snippet doesn't end with `}` at all. Try closing an open
    #    string then the object, then just the object.
    if not snippet.endswith("}"):
        for suffix, name in (('"}', "append_quote_brace"), ("}", "append_brace")):
            try:
                return json.loads(snippet + suffix), name
            except json.JSONDecodeError:
                pass

    return None


def parse_json_block(text: str) -> dict:
    """Parse a JSON object embedded in agent text. Tolerates markdown code
    fences and surrounding prose. On a clean-parse failure, attempts a sequence
    of conservative, deterministic repairs before giving up."""
    # Strip common markdown fences. Real models often wrap JSON like:
    #   ```json
    #   { ... }
    #   ```
    cleaned = text.replace("```json", "").replace("```JSON", "").replace("```", "")
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"No JSON object found in agent response: {text[:200]!r}")
    snippet = cleaned[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        repaired = _repair_json(snippet)
        if repaired is not None:
            parsed, repair_name = repaired
            log.warn("parse_repaired", repair=repair_name, preview=text[:120])
            return parsed
        raise ValueError(
            f"Could not parse JSON from agent response (after repairs): "
            f"{exc}; text={text[:200]!r}"
        ) from exc
