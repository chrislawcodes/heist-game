"""Structured (JSON Lines) logging for the heist backend.

One module-level logger writes one JSON object per line to
``./logs/heist.jsonl`` (override via ``HEIST_LOG_PATH``). Every line carries
at least ``ts`` (ISO-8601 UTC), ``level``, ``source`` (caller's module), and
``event`` (short string). Additional fields are passed as kwargs.

Public surface::

    from heist.logs import log
    log.info("ai_call", label="bid", elapsed_ms=1234)
    log.warn("subprocess_timeout", cmd="codex")
    log.error("game_crashed", traceback=tb_str)
    log.log_path()  # → str of absolute path to current log file

The module is stdlib-only and thread-safe (a single ``threading.Lock``
serialises writes so JSON lines never interleave).
"""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path("logs") / "heist.jsonl"


def _resolve_path() -> Path:
    override = os.environ.get("HEIST_LOG_PATH")
    return Path(override) if override else _DEFAULT_PATH


def _caller_module() -> str:
    """Return the dotted module name of the first caller outside this file."""
    frame = inspect.currentframe()
    try:
        # skip _caller_module, then _write, then the public log method
        f = frame
        while f is not None:
            f = f.f_back
            if f is None:
                break
            mod = f.f_globals.get("__name__", "")
            if mod and mod != __name__:
                return mod
    finally:
        del frame
    return "unknown"


class _Logger:
    """JSON-Lines logger. One instance lives at module level as ``log``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path: Path | None = None
        self._fh: Any = None

    def _ensure_open(self) -> None:
        desired = _resolve_path().resolve()
        if self._fh is not None and self._path == desired:
            return
        # path changed (or first open) — close old, open new
        if self._fh is not None:
            with contextlib.suppress(Exception):
                self._fh.close()
            self._fh = None
        desired.parent.mkdir(parents=True, exist_ok=True)
        # Long-lived line-buffered append handle — kept open for the process
        # lifetime, so a context-manager doesn't fit. Closed in _reset_for_tests.
        self._fh = open(desired, "a", buffering=1, encoding="utf-8")  # noqa: SIM115
        self._path = desired

    def _write(self, level: str, event: str, fields: dict[str, Any]) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": level,
            "source": _caller_module(),
            "event": event,
        }
        # caller fields override nothing reserved — but if they do, last write
        # wins so the caller can override ``source`` if they really want to.
        for k, v in fields.items():
            record[k] = _coerce(v)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self._ensure_open()
            assert self._fh is not None
            self._fh.write(line)

    def info(self, event: str, **fields: Any) -> None:
        self._write("info", event, fields)

    def warn(self, event: str, **fields: Any) -> None:
        self._write("warn", event, fields)

    def error(self, event: str, **fields: Any) -> None:
        self._write("error", event, fields)

    def log_path(self) -> str:
        """Absolute path of the current log file (creates the dir/file)."""
        with self._lock:
            self._ensure_open()
            assert self._path is not None
            return str(self._path)

    def _reset_for_tests(self) -> None:
        """Close the open file handle so the next write re-resolves the path.

        Tests that mutate ``HEIST_LOG_PATH`` between calls use this.
        """
        with self._lock:
            if self._fh is not None:
                with contextlib.suppress(Exception):
                    self._fh.close()
            self._fh = None
            self._path = None


def _coerce(v: Any) -> Any:
    """Best-effort coerce a value to something json.dumps can handle."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_coerce(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _coerce(x) for k, x in v.items()}
    return str(v)


log = _Logger()
