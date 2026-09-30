#!/usr/bin/env python3
"""beforeShellExecution: ask before shell commands that may mutate protected dirs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MUTATING = re.compile(
    r"(?i)\b("
    r"remove-item|move-item|rename-item|copy-item|"
    r"set-content|add-content|out-file|new-item|clear-content|"
    r"del|erase|rmdir|rd|move|ren|copy|xcopy|robocopy|mkdir|"
    r"rm\b|mv\b|cp\b|tee\b"
    r")\b"
    r"|\bgit\s+(?:-C\s+\S+\s+)?(?:checkout|restore|clean|reset|stash|rm|mv|apply|am|switch)\b"
    r"|\[(?:system\.)?io\.(?:file|directory)\]::\s*(?:write|append|delete|move|copy|create|replace)"
)

# Explicit allowlist: regenerates fixture under source/mini_vbp only.
# Both spellings are the same tool: the script path and the CLI subcommand.
# The whole command must be the fixture call; anything chained after it
# (``;``, ``&&``, a second line) is not covered by the allowlist.
ALLOWLIST = re.compile(
    r"(?i)\s*python(?:\.exe)?\s+(?:"
    r"([\"']?)(?:\.[\\/])?tools[/\\]make_fixture\.py\1"
    r"|-m\s+tools\s+fixture"
    r")(?:\s+--?[\w-]+)*\s*"
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


def mentions_protected_path(command: str, names: list[str]) -> str | None:
    """Return protected dir name if command references it as a path segment."""
    # Normalize and split on common separators; avoid substring false positives
    # like "resources" matching "source". Windows paths are case-insensitive.
    tokens = re.split(r"[\\/\"'\s;=]+", command)
    for tok in tokens:
        if not tok:
            continue
        low = tok.casefold()
        for name in names:
            key = name.casefold()
            if low == key or low.startswith(key + ".") or low.endswith(":" + key):
                return name
        # quoted path fragments already split; also check path-like pieces
        parts = {p.casefold() for p in tok.replace("\\", "/").split("/") if p}
        for name in names:
            if name.casefold() in parts:
                return name
    return None


def ask(user_message: str, agent_message: str) -> None:
    print(
        json.dumps(
            {"permission": "ask", "user_message": user_message, "agent_message": agent_message},
            ensure_ascii=True,
        )
    )


def main() -> int:
    names = protected_names()
    data, problem = read_payload()
    if not isinstance(data, dict):
        ask(
            "シェルコマンドの内容を確認できませんでした（フック入力を読めません）。",
            f"Hook payload could not be parsed ({problem or 'not an object'}); command unchecked.",
        )
        return 0

    command = data.get("command") or ""
    if ALLOWLIST.fullmatch(command):
        print(json.dumps({"permission": "allow"}))
        return 0

    hit_name = mentions_protected_path(command, names)
    redirect_hit = False
    if hit_name:
        redirect_hit = bool(
            re.search(
                rf"[>]{{1,2}}\s*\"?[^\s\"]*{re.escape(hit_name)}", command, re.IGNORECASE
            )
        )

    if hit_name and (MUTATING.search(command) or redirect_hit):
        ask(
            f"このコマンドは保護ディレクトリ（{hit_name}）を変更する可能性があります。",
            "This shell command may mutate a protected VB6 source tree. "
            "Prefer read-only commands. Copies must target working/extracts/. "
            "Fixture regeneration: python tools/make_fixture.py (allowlisted).",
        )
        return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
