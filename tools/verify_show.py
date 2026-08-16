#!/usr/bin/env python3
"""Compare inventory vs deep-read show_style. Neither side is canon.

Inventory scans the whole file. Deep-read ``show_map`` keeps live Subs only.
A difference is a warning, not a verdict. This is not a callgraph.

    python -m tools verify-show
    python -m tools verify-show --inventory working/reports/<stem>_inventory.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from frm_deep_read import resolve_deep_read_out_key  # noqa: E402
from lib.config import load_config, reports_root, skeletons_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

HARD_KINDS = frozenset({"self_style", "call_style", "deep_read_only"})
WARN_KINDS = frozenset({"inventory_only", "missing_skeleton"})
NOTE = "neither side is canon; inventory=full file, deep-read=live Subs"


def _style(block: dict | None) -> str:
    return str((block or {}).get("show_style") or "unknown")


def _call_key(call: dict) -> tuple[int, str]:
    try:
        line = int(call.get("line") or 0)
    except (TypeError, ValueError):
        line = 0
    return (line, str(call.get("target") or "").strip().lower())


def flatten_show_map(skel: dict) -> list[dict]:
    """Live-Sub Show calls from a skeleton (``extract_show_map`` shape)."""
    out: list[dict] = []
    for row in skel.get("show_map") or []:
        sub = row.get("sub")
        for call in row.get("calls") or []:
            rec = dict(call)
            rec["sub"] = sub
            out.append(rec)
    return out


def compare_form(entry: dict, skel: dict | None) -> list[dict]:
    """Return findings for one inventory Form. ``skel`` None → missing_skeleton."""
    file_name = str(entry.get("file") or "")
    vb_name = entry.get("vb_name")
    if skel is None:
        return [
            {
                "kind": "missing_skeleton",
                "file": file_name,
                "vb_name": vb_name,
                "note": NOTE,
            }
        ]

    findings: list[dict] = []
    inv_style = _style(entry.get("show_style"))
    dr_style = _style(skel.get("show_style"))
    if inv_style != dr_style:
        findings.append(
            {
                "kind": "self_style",
                "file": file_name,
                "vb_name": vb_name,
                "inventory": inv_style,
                "deep_read": dr_style,
                "note": NOTE,
            }
        )

    inv_calls = {_call_key(c): c for c in entry.get("show_calls") or []}
    dr_calls = {_call_key(c): c for c in flatten_show_map(skel)}

    for key, call in sorted(inv_calls.items()):
        other = dr_calls.get(key)
        if other is None:
            findings.append(
                {
                    "kind": "inventory_only",
                    "file": file_name,
                    "vb_name": vb_name,
                    "line": key[0],
                    "target": call.get("target"),
                    "inventory_style": call.get("show_style", "unknown"),
                    "note": NOTE,
                }
            )
            continue
        inv_cs = str(call.get("show_style") or "unknown")
        dr_cs = str(other.get("show_style") or "unknown")
        if inv_cs != dr_cs:
            findings.append(
                {
                    "kind": "call_style",
                    "file": file_name,
                    "vb_name": vb_name,
                    "line": key[0],
                    "target": call.get("target"),
                    "inventory": inv_cs,
                    "deep_read": dr_cs,
                    "note": NOTE,
                }
            )

    for key, call in sorted(dr_calls.items()):
        if key in inv_calls:
            continue
        findings.append(
            {
                "kind": "deep_read_only",
                "file": file_name,
                "vb_name": vb_name,
                "line": key[0],
                "target": call.get("target"),
                "deep_read_style": call.get("show_style", "unknown"),
                "sub": call.get("sub"),
                "note": NOTE,
            }
        )
    return findings


def load_skeleton(skeletons: Path, entry: dict, mapping: dict) -> dict | None:
    vb = str(entry.get("vb_name") or "")
    file_name = str(entry.get("file") or "")
    key = resolve_deep_read_out_key(vb, Path(file_name), mapping=mapping)
    path = skeletons / f"{key}-skeleton.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def compare_inventory(
    data: dict,
    skeletons: Path,
    mapping: dict | None = None,
) -> dict:
    """Compare every inventory Form to its skeleton. Does not scan VB6 source."""
    mapping = mapping if mapping is not None else {}
    forms = [
        f
        for f in data.get("files") or []
        if str(f.get("type") or "").lower() == "form"
    ]
    findings: list[dict] = []
    compared = 0
    missing = 0
    for entry in forms:
        skel = load_skeleton(skeletons, entry, mapping)
        if skel is None:
            missing += 1
        else:
            compared += 1
        findings.extend(compare_form(entry, skel))

    hard = [f for f in findings if f.get("kind") in HARD_KINDS]
    warns = [f for f in findings if f.get("kind") in WARN_KINDS]
    counts: dict[str, int] = {}
    for row in findings:
        kind = str(row.get("kind") or "")
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "ok": not hard,
        "forms": len(forms),
        "compared": compared,
        "missing_skeleton": missing,
        "hard_count": len(hard),
        "warning_count": len(warns),
        "counts": counts,
        "findings": findings,
        "note": NOTE,
    }


def resolve_inventory(path: Path | None) -> Path:
    if path is None:
        reports = reports_root()
        cands = sorted(reports.glob("*_inventory.json"))
        if len(cands) != 1:
            raise SystemExit(
                f"Pass inventory_json explicitly (found {len(cands)} under {reports})"
            )
        return cands[0]
    if not path.is_absolute():
        return REPO_ROOT / path
    return path


def format_summary(result: dict) -> str:
    if result["hard_count"]:
        return (
            f"show_style mismatches: FOUND hard={result['hard_count']} "
            f"warnings={result['warning_count']} ({NOTE})"
        )
    if result["warning_count"]:
        return (
            f"show_style mismatches: warnings={result['warning_count']} "
            f"(inventory_only or missing skeleton; {NOTE})"
        )
    return (
        f"show_style mismatches: none "
        f"(forms={result['forms']} compared={result['compared']})"
    )


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    parser = argparse.ArgumentParser(
        description=(
            "Compare inventory vs deep-read show_style "
            "(warnings only; neither side is canon)"
        )
    )
    parser.add_argument(
        "inventory_json",
        type=Path,
        nargs="?",
        help="Path to <stem>_inventory.json (default: sole inventory under reports/)",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Same as inventory_json (verify-names-style flag)",
    )
    parser.add_argument(
        "--skeletons",
        type=Path,
        default=None,
        help="Skeleton dir (default: archaeology.config.json skeletons_dir)",
    )
    args = parser.parse_args(argv)

    inv_path = resolve_inventory(args.inventory or args.inventory_json)
    if not inv_path.is_file():
        print(f"inventory not found: {inv_path}", file=sys.stderr)
        return 2

    data = json.loads(inv_path.read_text(encoding="utf-8"))
    stem = data.get("stem") or inv_path.name.replace("_inventory.json", "")
    skeletons = args.skeletons
    if skeletons is None:
        skeletons = skeletons_root()
    elif not skeletons.is_absolute():
        skeletons = REPO_ROOT / skeletons
    skeletons = skeletons.resolve()

    mapping_raw = load_config().get("deep_read_name_map") or {}
    mapping = mapping_raw if isinstance(mapping_raw, dict) else {}
    result = compare_inventory(data, skeletons, mapping)
    result["inventory"] = str(inv_path).replace("\\", "/")
    result["skeletons"] = str(skeletons).replace("\\", "/")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    verify_path = reports_root() / f"{stem}_verify_show.json"
    try:
        verify_path.parent.mkdir(parents=True, exist_ok=True)
        verify_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["persisted"] = str(verify_path).replace("\\", "/")
    except OSError:
        pass

    summary = format_summary(result)
    if result["ok"]:
        print(summary)
        return 0
    print(summary, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
