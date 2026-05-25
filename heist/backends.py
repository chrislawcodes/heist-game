"""Real Heist AI backends.

Each backend wraps one of the CLI invokers in the repo-root `agents.py` module
(`ask_codex`, `ask_gemini`) and threads its `session_id` across every call,
so a single heist run corresponds to a single CLI session. That continuity
is the design doc's "Use a single Heist AI instance throughout, maintaining
conversation context" requirement.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable

from agents import Turn, ask_codex, ask_gemini
from heist.ai import AgentTurn
from heist.logs import log

# Per-call ceiling for ONE attempt at an in-game AI turn. Deliberately far
# shorter than agents.py's 600s default: this is a watch-only game, so a single
# attempt that runs this long is effectively hung.
AI_TURN_TIMEOUT_SECONDS = 120

# General rule for every in-game AI call: attempt it up to this many times
# before giving up. A timeout or any other failure triggers a retry; only after
# ALL attempts fail does the exception propagate to the caller's fallback (the
# auction skips the bid; the heist fails that AI's round; wire/reflection fall
# back). Most failures are transient (cold start, brief hang), so retrying
# recovers the common case.
#
# Worst case before a fully-dead backend is finally skipped is roughly
# AI_MAX_ATTEMPTS * AI_TURN_TIMEOUT_SECONDS (plus the retry delays). Tune these
# constants together if that ceiling is too long or too aggressive.
AI_MAX_ATTEMPTS = 3

# Brief pause between attempts. Patchable in tests.
AI_RETRY_DELAY_SECONDS = 2.0


def _ask_with_retries(
    call: Callable[[], Turn],
    on_attempt: Callable[[int, int], None] | None = None,
) -> tuple[Turn, int, int]:
    """Run one backend call up to AI_MAX_ATTEMPTS times.

    Retries on ANY exception (subprocess timeout, CLI error, malformed output).
    Re-raises the last exception only after every attempt has failed, so callers
    skip / fall back only once the retries are exhausted — never on the first
    blip.

    Returns ``(result, attempts_used, attempt_ms)`` where ``attempt_ms`` is the
    wall time of the SUCCESSFUL attempt alone — a clean per-call latency, not
    inflated by earlier failed attempts or the pauses between them. Each failed
    attempt is logged separately (``ai_call_attempt_failed``) with its own
    ``attempt_ms`` so slow-then-failed calls are visible too.
    """
    last_exc: Exception | None = None
    for attempt in range(1, AI_MAX_ATTEMPTS + 1):
        if on_attempt is not None:
            with contextlib.suppress(Exception):
                on_attempt(attempt, AI_MAX_ATTEMPTS)
        t0 = time.monotonic()
        try:
            result = call()
        except Exception as exc:
            attempt_ms = int((time.monotonic() - t0) * 1000)
            last_exc = exc
            log.warn(
                "ai_call_attempt_failed",
                attempt=attempt,
                max_attempts=AI_MAX_ATTEMPTS,
                attempt_ms=attempt_ms,
                error=str(exc),
            )
            if attempt < AI_MAX_ATTEMPTS:
                time.sleep(AI_RETRY_DELAY_SECONDS)
            continue
        attempt_ms = int((time.monotonic() - t0) * 1000)
        return result, attempt, attempt_ms
    assert last_exc is not None  # the loop always runs at least once
    raise last_exc


class CodexHeistAI:
    def __init__(self, model: str | None = None, progress_cb=None) -> None:
        self.session_id: str | None = None
        self.model = model
        self._progress_cb = progress_cb
        # Stats from the most recent successful ask(), surfaced by the caller's
        # ai_call log: attempts taken and the clean latency of the call that
        # actually succeeded.
        self.last_attempts: int = 0
        self.last_attempt_ms: int = 0

    def ask(self, prompt: str) -> AgentTurn:
        result, attempts, attempt_ms = _ask_with_retries(
            lambda: ask_codex(
                prompt,
                session_id=self.session_id,
                model=self.model,
                timeout=AI_TURN_TIMEOUT_SECONDS,
            ),
            on_attempt=self._progress_cb if self._progress_cb is not None else None,
        )
        self.last_attempts = attempts
        self.last_attempt_ms = attempt_ms
        self.session_id = result.session_id
        return AgentTurn(text=result.text, session_id=result.session_id)


class GeminiHeistAI:
    def __init__(self, progress_cb=None) -> None:
        self.session_id: str | None = None
        self._progress_cb = progress_cb
        self.last_attempts: int = 0
        self.last_attempt_ms: int = 0

    def ask(self, prompt: str) -> AgentTurn:
        result, attempts, attempt_ms = _ask_with_retries(
            lambda: ask_gemini(
                prompt,
                session_id=self.session_id,
                timeout=AI_TURN_TIMEOUT_SECONDS,
            ),
            on_attempt=self._progress_cb if self._progress_cb is not None else None,
        )
        self.last_attempts = attempts
        self.last_attempt_ms = attempt_ms
        self.session_id = result.session_id
        return AgentTurn(text=result.text, session_id=result.session_id)
