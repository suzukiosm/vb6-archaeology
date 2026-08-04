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
    norm = path.replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    return any(name in parts for name in names)


def main() -> int:
    names = protected_names()
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print(json.dumps({"permission": "allow"}))
        return 0

    paths = []
    collect_paths(data, paths)
    hit = next((p for p in paths if is_protected(p, names)), None)
    if hit is not None:
        print(
            json.dumps(
                {
                    "permission": "deny",
                    "user_message": (
                        "保護された VB6 正本ディレクトリへの書込・削除をブロックしました。"
                    ),
                    "agent_message": (
                        "Blocked: path is under a protected source tree "
                        f"({', '.join(names)}). "
                        "Copy targets belong in working/extracts/. Offending path: "
                        + hit
                    ),
                },
                ensure_ascii=True,
            )
        )
        return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
