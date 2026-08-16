#!/usr/bin/env python3
"""List remaining kit-improvement-ideas.md items. Does not invent new work.

The ideas file is the kit backlog of record. GitHub Issues are optional intake.
Adopted rows (採用済 / strikethrough) are listed separately from open holes.

    python -m tools ideas
    python -m tools ideas --json-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.console import enable_utf8_stdio  # noqa: E402

IDEAS = REPO / "docs" / "kit-improvement-ideas.md"
F_ROW = re.compile(r"^\|\s*(F\d+)\s*\|\s*(.+?)\s*\|")
P_HEAD = re.compile(r"^####\s+([A-Z])\.\s+(.+)$")
DEFER_ROW = re.compile(r"^\|\s+([^|]+?)\s+\|\s+([^|]+?)\s+\|\s*$")
WONT_ROW = re.compile(r"^\|\s+([^|]+?)\s+\|\s+([^|]+?)\s+\|\s*$")


def _adopted(text: str) -> bool:
    return "採用済" in text or text.strip().startswith("~~")


def parse_ideas(text: str) -> dict:
    """Split the ideas markdown into open / adopted / deferred / wont."""
    holes_open: list[dict] = []
    holes_adopted: list[dict] = []
    proposals_open: list[dict] = []
    proposals_adopted: list[dict] = []
    deferred: list[dict] = []
    wont: list[dict] = []
    section = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## 0."):
            section = "wont"
            continue
        if line.startswith("## 1."):
            section = "holes"
            continue
        if line.startswith("## 2."):
            section = "proposals"
            continue
        if line.startswith("## 3."):
            section = "deferred"
            continue
        if line.startswith("## 4."):
            section = ""
            continue
        if section == "holes":
            match = F_ROW.match(line)
            if not match or match.group(1) == "#":
                continue
            ident, body = match.group(1), match.group(2)
            row = {"id": ident, "text": body}
            (holes_adopted if _adopted(body) else holes_open).append(row)
            continue
        if section == "proposals":
            match = P_HEAD.match(line)
            if not match:
                continue
            letter, title = match.group(1), match.group(2).strip()
            row = {"id": letter, "text": title}
            (proposals_adopted if _adopted(title) else proposals_open).append(row)
            continue
        if section in {"deferred", "wont"}:
            if not line.startswith("|") or line.startswith("|---") or line.startswith("| 案") or line.startswith("| 対象"):
                continue
            match = DEFER_ROW.match(line) if section == "deferred" else WONT_ROW.match(line)
            if not match:
                continue
            item, reason = match.group(1).strip(), match.group(2).strip()
            item = item.strip("`")
            if item in {"案", "対象"}:
                continue
            bucket = deferred if section == "deferred" else wont
            bucket.append({"id": item, "text": reason})
    return {
        "source": "docs/kit-improvement-ideas.md",
        "holes_open": holes_open,
        "holes_adopted": holes_adopted,
        "proposals_open": proposals_open,
        "proposals_adopted": proposals_adopted,
        "deferred": deferred,
        "wont": wont,
    }


def format_ideas(data: dict) -> str:
    def _ids(rows: list[dict]) -> str:
        return ", ".join(r["id"] for r in rows) or "—"

    lines = [
        f"backlog={data.get('source')}",
        f"open holes={len(data.get('holes_open') or [])} ({_ids(data.get('holes_open') or [])})",
        f"open proposals={len(data.get('proposals_open') or [])} ({_ids(data.get('proposals_open') or [])})",
        f"adopted holes={len(data.get('holes_adopted') or [])} proposals={len(data.get('proposals_adopted') or [])}",
        f"deferred={len(data.get('deferred') or [])} wont={len(data.get('wont') or [])}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="List remaining items in docs/kit-improvement-ideas.md"
    )
    ap.add_argument(
        "--json-only",
        action="store_true",
        help="Print JSON only (default: five text lines, then JSON)",
    )
    args = ap.parse_args(argv)
    path = IDEAS
    if not path.is_file():
        print(f"ideas file missing: {path}", file=sys.stderr)
        return 2
    data = parse_ideas(path.read_text(encoding="utf-8"))
    if not args.json_only:
        print(format_ideas(data))
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
