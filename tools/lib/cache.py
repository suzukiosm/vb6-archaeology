"""Content-addressed parse cache.

Keys are SHA-256 over (parser version + file bytes), so results are path- and
mtime-independent and self-invalidate when either the file content or the
parser version changes. Callers put ``code_fingerprint`` of the parser sources
into the version string: a hand-bumped version alone let stale entries survive
parser edits. Cache lives under working/.cache/ (gitignored).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.config import load_config


def cache_root(repo_root: Path | None = None) -> Path:
    cfg = load_config(repo_root)
    return Path(cfg["_repo_root"]) / "working" / ".cache"


def code_fingerprint(paths: list[Path]) -> str:
    """SHA-256 over the given source files (sorted by name, bytes as stored)."""
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        h.update(path.name.encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def content_key(raw: bytes, version: str) -> str:
    h = hashlib.sha256()
    h.update(version.encode("utf-8"))
    h.update(b"\x00")
    h.update(raw)
    return h.hexdigest()


def load(key: str, repo_root: Path | None = None) -> dict | None:
    path = cache_root(repo_root) / f"{key}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def store(key: str, data: dict, repo_root: Path | None = None) -> None:
    root = cache_root(repo_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{key}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # cache is best-effort; never fail the run on cache write
