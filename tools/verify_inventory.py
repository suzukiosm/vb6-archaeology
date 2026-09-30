#!/usr/bin/env python3
"""Mechanically verify inventory procedure counts vs End Sub/Function/Property lines.

Also cross-checks the inventory without the shared lexer: a plain per-line
header count (warning when it differs), inverted / overlapping spans (error)
and duplicate name+kind in one file (warning; usually ``#If`` branches).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.config import decode_vb6_bytes, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402
from lib.vbparse import iter_statements  # noqa: E402

END_RE = re.compile(r"^End\s+(Sub|Function|Property)\b", re.IGNORECASE)
# Deliberately independent of lib.vbparse: one physical line = one header, no
# continuation folding or colon split. Differences are warnings to look at.
RAW_HEADER_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend)\s+)?(?:Static\s+)?"
    r"(?:Sub|Function|Property\s+(?:Get|Let|Set))\s+[^\W\d]\w*",
    re.IGNORECASE,
)


def raw_header_count(path: Path) -> int:
    """Procedure headers counted per physical line with a plain regex."""
    text = decode_vb6_bytes(path.read_bytes())
    return sum(1 for line in text.splitlines() if RAW_HEADER_RE.match(line))


def span_problems(file: str, procs: list[dict]) -> list[dict]:
    """Inverted or overlapping procedure spans (a parser error, not a style issue)."""
    problems: list[dict] = []
    ordered = sorted(procs, key=lambda p: p.get("line_start") or 0)
    for proc in ordered:
        if (proc.get("line_end") or 0) < (proc.get("line_start") or 0):
            problems.append({"file": file, "error": "inverted span", "procedure": proc.get("name"),
                             "line_start": proc.get("line_start"), "line_end": proc.get("line_end")})
    for prev, cur in zip(ordered, ordered[1:]):
        if (cur.get("line_start") or 0) <= (prev.get("line_end") or 0):
            problems.append({"file": file, "error": "overlapping spans",
                             "procedures": [prev.get("name"), cur.get("name")],
                             "lines": [prev.get("line_end"), cur.get("line_start")]})
    return problems


def duplicate_procedures(file: str, procs: list[dict]) -> list[dict]:
    seen: dict[tuple[str, str], list[int]] = {}
    for proc in procs:
        key = (str(proc.get("name") or "").casefold(), str(proc.get("kind") or ""))
        seen.setdefault(key, []).append(proc.get("line_start"))
    return [
        {"file": file, "kind": "duplicate_procedure", "name": name, "proc_kind": kind, "lines": lines}
        for (name, kind), lines in seen.items() if len(lines) > 1
    ]


def count_ends(path: Path) -> int:
    """Count ``End Sub|Function|Property`` per colon-split statement.

    ``x = 1: End Sub`` counts. Line labels are skipped. Inventory
    ``parse_procedures`` uses the same splitter.
    """
    text = decode_vb6_bytes(path.read_bytes())
    n = 0
    for stmt in iter_statements(text.splitlines()):
        if stmt.kind != "stmt":
            continue
        if END_RE.match(stmt.text.strip()):
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
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
    stem = data.get("stem") or inv_path.name.replace("_inventory.json", "")
    extract_dir = args.extract
    if extract_dir is None and data.get("extract_dir"):
        extract_dir = Path(data["extract_dir"])
    elif extract_dir is None:
        extract_dir = REPO_ROOT / "working" / "extracts" / stem
    if not extract_dir.is_absolute():
        extract_dir = (REPO_ROOT / extract_dir).resolve()
    else:
        extract_dir = extract_dir.resolve()

    mismatches: list[dict] = [
        {'file': name, 'error': 'VBP reference missing in extract; re-extract before verification'}
        for name in data.get('missing_in_extract') or []
    ]
    warnings: list[dict] = []
    files = data.get("files") or []
    for entry in files:
        if str(entry.get("type") or "") in ("relateddoc", "resfile32"):
            continue
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
        mismatches.extend(span_problems(name, procs))
        raw = raw_header_count(path)
        if raw != proc_count:
            warnings.append({"file": name, "kind": "independent_header_count",
                             "procedures": proc_count, "raw_headers": raw})
        warnings.extend(duplicate_procedures(name, procs))

    result = {
        "inventory": str(inv_path),
        "extract_dir": str(extract_dir),
        "files_checked": len(files),
        "mismatches": mismatches,
        # Independent cross-checks worth a look; they do not fail the run.
        "warnings": warnings,
        "ok": not mismatches,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    verify_path = reports_root() / f"{stem}_verify.json"
    try:
        verify_path.parent.mkdir(parents=True, exist_ok=True)
        verify_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["persisted"] = str(verify_path)
    except OSError:
        pass
    if warnings:
        kinds = sorted({w["kind"] for w in warnings})
        print(f"verify warnings: {len(warnings)} ({', '.join(kinds)})", file=sys.stderr)
    if mismatches:
        print("count mismatches: FOUND", file=sys.stderr)
        return 1
    print("count mismatches: none", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
