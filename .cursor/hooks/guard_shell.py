#!/usr/bin/env python3
"""beforeShellExecution: ask before shell commands that may mutate protected dirs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MUTATING = re.compile(
    r"(?i)\b("
    r"remove-item|move-item|rename-item|"
    r"set-content|add-content|out-file|new-item|clear-content|"
    r"del|erase|rmdir|rd|move|ren|"
    r"rm\b|mv\b|tee\b"
    r")\b"
)

# Explicit allowlist: regenerates fixture under source/mini_vbp only.
# Both spellings are the same tool: the script path and the CLI subcommand.
ALLOWLIST = re.compile(
    r"(?i)python(\.exe)?\s+(?:"
    r"([\"']?)(?:\.\\|/)?tools[/\\]make_fixture\.py\2"
    r"|-m\s+tools\s+fixture\b"
    r")"
)


def protected_names() -> list[str]:
    """In-repo dir names plus markers for originals kept outside the repo."""
    cfg_path = Path(__file__).resolve().parents[2] / "archaeology.config.json"
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


def mentions_protected_path(command: str, names: list[str]) -> str | None:
    """Return protected dir name if command references it as a path segment."""
    # Normalize and split on common separators; avoid substring false positives
    # like "resources" matching "source".
    tokens = re.split(r"[\\/\"'\s;=]+", command)
    for tok in tokens:
        if not tok:
            continue
        for name in names:
            if tok == name or tok.startswith(name + ".") or tok.endswith(":" + name):
                return name
        # quoted path fragments already split; also check path-like pieces
        parts = [p for p in tok.replace("\\", "/").split("/") if p]
        for name in names:
            if name in parts:
                return name
    return None


def main() -> int:
    names = protected_names()
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print(json.dumps({"permission": "allow"}))
        return 0

    command = data.get("command") or ""
    if ALLOWLIST.search(command):
        print(json.dumps({"permission": "allow"}))
        return 0

    hit_name = mentions_protected_path(command, names)
    redirect_hit = False
    if hit_name:
        redirect_hit = bool(
            re.search(rf"[>]{{1,2}}\s*\"?[^\s\"]*{re.escape(hit_name)}", command)
        )

    if hit_name and (MUTATING.search(command) or redirect_hit):
        print(
            json.dumps(
                {
                    "permission": "ask",
                    "user_message": (
                        f"このコマンドは保護ディレクトリ（{hit_name}）を変更する可能性があります。"
                    ),
                    "agent_message": (
                        "This shell command may mutate a protected VB6 source tree. "
                        "Prefer read-only commands. Copies must target working/extracts/. "
                        "Fixture regeneration: python tools/make_fixture.py (allowlisted)."
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
