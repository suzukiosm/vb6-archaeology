#!/usr/bin/env python3
"""preToolUse: deny writes into protected_source_dirs from archaeology.config.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PATH_KEYS = {
    "path",
    "file_path",
    "filepath",
    "abs_path",
    "target_notebook",
    "downloadpath",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def protected_names() -> list[str]:
    """In-repo dir names plus markers for originals kept outside the repo."""
    cfg_path = repo_root() / "archaeology.config.json"
    names: list[str] = ["source"]
    markers: list[str] = []
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            configured = data.get("protected_source_dirs")
            if configured is not None:
                names = list(configured)
            markers = list(data.get("protected_path_markers") or [])
        except Exception:
            pass
    return [str(n) for n in [*names, *markers]]


def read_payload() -> tuple[object, str]:
    """Return (payload or None, failure detail).

    Cursor on Windows sends the payload with a UTF-8 BOM, which json.loads
    rejects; UTF-16 is accepted too. The detail names byte length and the
    first bytes only, never payload content.
    """
    try:
        raw = sys.stdin.buffer.read()
    except Exception as exc:
        return None, f"stdin unreadable ({type(exc).__name__})"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    text = text.strip()
    try:
        return (json.loads(text) if text else {}), ""
    except ValueError as exc:
        return None, f"{exc.__class__.__name__}; bytes={len(raw)} head={raw[:8].hex()}"


def collect_paths(node, out):
    if isinstance(node, dict):
        for key, val in node.items():
            if isinstance(val, str) and key.lower() in PATH_KEYS:
                out.append(val)
            else:
                collect_paths(val, out)
    elif isinstance(node, list):
        for val in node:
            collect_paths(val, out)


def is_protected(path: str, names: list[str]) -> bool:
    # Windows paths are case-insensitive: Source\ and source\ are the same tree.
    norm = path.replace("\\", "/")
    parts = {p.casefold() for p in norm.split("/") if p}
    return any(name.casefold() in parts for name in names)


def deny(agent_message: str) -> None:
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": "保護された VB6 正本ディレクトリへの書込・削除をブロックしました。",
                "agent_message": agent_message,
            },
            ensure_ascii=True,
        )
    )


def main() -> int:
    names = protected_names()
    data, problem = read_payload()
    if data is None:
        # An unreadable payload cannot be checked; fail closed like hooks.json says.
        deny(f"Blocked: hook payload could not be parsed ({problem}); target path unchecked.")
        return 0

    paths = []
    collect_paths(data, paths)
    hit = next((p for p in paths if is_protected(p, names)), None)
    if hit is not None:
        deny(
            "Blocked: path is under a protected source tree "
            f"({', '.join(names)}). "
            "Copy targets belong in working/extracts/. Offending path: "
            + hit
        )
        return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
