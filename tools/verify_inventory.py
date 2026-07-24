#!/usr/bin/env python3
"""Mechanically verify inventory procedure counts vs End Sub/Function/Property lines."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.config import decode_vb6_bytes, reports_root  # noqa: E402

END_RE = re.compile(r"^End\s+(Sub|Function|Property)\b", re.IGNORECASE)


def count_ends(path: Path) -> int:
    text = decode_vb6_bytes(path.read_bytes())
    return sum(1 for line in text.splitlines() if END_RE.match(line.strip()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify inventory End-count consistency")
    parser.add_argument(
        "inventory_json",
        type=Path,
        nargs="?",
        help="Path to <stem>_inventory.json (default: sole inventory under reports/)",
    )
    parser.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Override extract dir (default: extract_dir field in inventory JSON)",
    )
    args = parser.parse_args(argv)

    inv_path = args.inventory_json
    if inv_path is None:
        reports = reports_root()
        cands = sorted(reports.glob("*_inventory.json"))
        if len(cands) != 1:
            raise SystemExit(
                f"Pass inventory_json explicitly (found {len(cands)} under {reports})"
            )
        inv_path = cands[0]
    elif not inv_path.is_absolute():
        inv_path = REPO_ROOT / inv_path

    data = json.loads(inv_path.read_text(encoding="utf-8"))
    extract_dir = args.extract
    if extract_dir is None and data.get("extract_dir"):
        extract_dir = Path(data["extract_dir"])
    elif extract_dir is None:
        stem = data.get("stem") or inv_path.name.replace("_inventory.json", "")
        extract_dir = REPO_ROOT / "working" / "extracts" / stem
    if not extract_dir.is_absolute():
        extract_dir = (REPO_ROOT / extract_dir).resolve()
    else:
        extract_dir = extract_dir.resolve()

    mismatches: list[dict] = []
    files = data.get("files") or []
    for entry in files:
        name = entry.get("file")
        procs = entry.get("procedures") or []
        path = extract_dir / name
        if not path.is_file():
            mismatches.append({"file": name, "error": f"missing: {path}"})
            continue
        end_count = count_ends(path)
        proc_count = len(procs)
        if end_count != proc_count:
            mismatches.append(
                {
                    "file": name,
                    "procedures": proc_count,
                    "end_statements": end_count,
                }
            )

    result = {
        "inventory": str(inv_path),
        "extract_dir": str(extract_dir),
        "files_checked": len(files),
        "mismatches": mismatches,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if mismatches:
        print("count mismatches: FOUND", file=sys.stderr)
        return 1
    print("count mismatches: none", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
