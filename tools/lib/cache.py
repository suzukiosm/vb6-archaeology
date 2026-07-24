"""Content-addressed parse cache.

Keys are SHA-256 over (parser version + file bytes), so results are path- and
mtime-independent and self-invalidate when either the file content or the
parser version changes. Cache lives under working/.cache/ (gitignored).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.config import load_config


def cache_root(repo_root: Path | None = None) -> Path:
    cfg = load_config(repo_root)
    return Path(cfg["_repo_root"]) / "working" / ".cache"


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
