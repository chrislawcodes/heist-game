"""On-disk persistence for game records and per-AI runner snapshots.

Layout (under ``HEIST_STATE_DIR``, default ``./state/``):

    state/games/<id>.json                full game record (incl. events list)
    state/games/<id>/ai-<idx>.json       per-AI runner snapshot (live AIs only)

All writes go through ``_atomic_write``: write to ``<path>.tmp.<pid>.<n>``,
then ``os.replace`` into place. A crash mid-write leaves the tmp file (which
we ignore on load) and the previous good file intact.

Loading is forgiving: any unparseable file is skipped with a logged warning
so one corrupt record can't take the whole server down.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from heist.logs import log

_DEFAULT_STATE_DIR = Path("state")
_write_lock = threading.Lock()
_tmp_counter = 0


def _state_dir() -> Path:
    override = os.environ.get("HEIST_STATE_DIR")
    return Path(override) if override else _DEFAULT_STATE_DIR


def _games_dir() -> Path:
    return _state_dir() / "games"


def _game_record_path(game_id: int) -> Path:
    return _games_dir() / f"{game_id}.json"


def _game_snapshot_dir(game_id: int) -> Path:
    return _games_dir() / str(game_id)


def _snapshot_path(game_id: int, ai_idx: int) -> Path:
    return _game_snapshot_dir(game_id) / f"ai-{ai_idx}.json"


def _atomic_write(path: Path, payload: dict) -> None:
    """Write JSON ``payload`` to ``path`` via a temp file + ``os.replace``.

    Thread-safe: a single process-wide lock serialises tmp-name allocation so
    parallel writers in the same process never collide on the suffix counter.
    Inter-process is fine too — each gets its own ``pid``.
    """
    global _tmp_counter
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        _tmp_counter += 1
        n = _tmp_counter
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{n}")
    data = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        # Make sure we don't leave a partial tmp file around if something
        # blew up between open and replace.
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


def _safe_load(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        log.warn("persist_load_failed", path=str(path), error=str(exc))
        return None


# ── game records ──────────────────────────────────────────────────────────────


def save_game_record(game: dict) -> None:
    """Atomic write of the full game record. Caller must supply ``game['id']``."""
    gid = int(game["id"])
    _atomic_write(_game_record_path(gid), game)


def load_game_records() -> dict[int, dict]:
    """Scan ``state/games/`` and return ``{id: record}`` for everything parseable."""
    out: dict[int, dict] = {}
    d = _games_dir()
    if not d.is_dir():
        return out
    for entry in d.iterdir():
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        # Skip ``.tmp.<pid>.<n>`` partial writes.
        if ".tmp." in entry.name:
            continue
        try:
            gid = int(entry.stem)
        except ValueError:
            continue
        record = _safe_load(entry)
        if record is None:
            continue
        # Last-write wins on id collisions — but the filename id is authoritative.
        record["id"] = gid
        out[gid] = record
    return out


def delete_game_record(game_id: int) -> None:
    path = _game_record_path(game_id)
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


# ── runner snapshots ──────────────────────────────────────────────────────────


def save_runner_snapshot(game_id: int, ai_idx: int, snapshot: dict) -> None:
    _atomic_write(_snapshot_path(game_id, ai_idx), snapshot)


def load_runner_snapshot(game_id: int, ai_idx: int) -> dict | None:
    return _safe_load(_snapshot_path(game_id, ai_idx))


def delete_runner_snapshot(game_id: int, ai_idx: int) -> None:
    path = _snapshot_path(game_id, ai_idx)
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    # If the per-game snapshot dir is empty, prune it (purely cosmetic).
    parent = path.parent
    with contextlib.suppress(OSError):
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def list_pending_snapshots(game_id: int) -> dict[int, dict]:
    """Return ``{ai_idx: snapshot}`` for every snapshot file under this game."""
    out: dict[int, dict] = {}
    d = _game_snapshot_dir(game_id)
    if not d.is_dir():
        return out
    for entry in d.iterdir():
        if not entry.is_file() or not entry.name.startswith("ai-"):
            continue
        if not entry.name.endswith(".json") or ".tmp." in entry.name:
            continue
        try:
            ai_idx = int(entry.stem[len("ai-"):])
        except ValueError:
            continue
        snap = _safe_load(entry)
        if snap is not None:
            out[ai_idx] = snap
    return out


def _serialize_rng(rng: Any) -> str:
    """Serialise a ``random.Random``'s internal state as base64-pickled bytes."""
    import base64
    import pickle
    return base64.b64encode(pickle.dumps(rng.getstate())).decode("ascii")


def _deserialize_rng_into(rng: Any, encoded: str) -> None:
    import base64
    import pickle
    rng.setstate(pickle.loads(base64.b64decode(encoded.encode("ascii"))))
