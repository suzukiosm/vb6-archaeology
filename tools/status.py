#!/usr/bin/env python3
"""Read existing pipeline artifacts and print a facts-only status.

Does not run extract / inventory / verify / verify-show / deep-read / io-catalog. Missing
artifacts are reported as absent. No ranking and no "what to do next".

    python -m tools status
    python -m tools status --extract working/extracts/mini_vbp
    python -m tools status --json-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.config import (  # noqa: E402
    extracts_root,
    load_config,
    preferred_extract,
    reports_root,
)
from lib.console import enable_utf8_stdio  # noqa: E402

TICK_ATTR_RE = re.compile(r'data-tick="(\d+)"')


def _rel(path: Path | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _out_key(vb_name: str | None, file_name: str, mapping: dict) -> str:
    """Same contract as frm_deep_read.resolve_deep_read_out_key (no import)."""
    if vb_name and mapping:
        for key, value in mapping.items():
            if str(key).lower() == vb_name.lower():
                return str(value)
    if vb_name:
        return vb_name.lower()
    return Path(file_name).stem.lower().replace("　", "").replace(" ", "")


def resolve_extract_dir(
    repo_root: Path, explicit: Path | None
) -> dict:
    if explicit is not None:
        path = explicit if explicit.is_absolute() else repo_root / explicit
        path = path.resolve()
        return {
            "present": path.is_dir(),
            "path": _rel(path, repo_root) if path.is_dir() else str(path),
            "name": path.name,
            "reason": None if path.is_dir() else "missing",
            "candidates": [],
        }
    preferred = preferred_extract(repo_root)
    if preferred is not None:
        return {
            "present": True,
            "path": _rel(preferred, repo_root),
            "name": preferred.name,
            "reason": None,
            "candidates": [],
        }
    root = extracts_root(repo_root)
    if not root.is_dir():
        return {
            "present": False,
            "path": _rel(root, repo_root),
            "name": None,
            "reason": "missing",
            "candidates": [],
        }
    candidates = sorted(p for p in root.iterdir() if p.is_dir())
    names = [p.name for p in candidates]
    if len(candidates) == 1:
        chosen = candidates[0].resolve()
        return {
            "present": True,
            "path": _rel(chosen, repo_root),
            "name": chosen.name,
            "reason": None,
            "candidates": names,
        }
    if not candidates:
        return {
            "present": False,
            "path": _rel(root, repo_root),
            "name": None,
            "reason": "missing",
            "candidates": [],
        }
    return {
        "present": False,
        "path": _rel(root, repo_root),
        "name": None,
        "reason": "multiple",
        "candidates": names,
    }


def resolve_inventory_path(
    repo_root: Path,
    reports: Path,
    stem: str | None,
    explicit: Path | None,
) -> tuple[Path | None, str | None, list[str]]:
    """Return (path, reason, candidate names). reason is None when found."""
    if explicit is not None:
        path = explicit if explicit.is_absolute() else repo_root / explicit
        path = path.resolve()
        if path.is_file():
            return path, None, [path.name]
        return None, "missing", []
    if not reports.is_dir():
        return None, "missing", []
    matches = sorted(reports.glob("*_inventory.json"))
    names = [m.name for m in matches]
    if stem:
        named = reports / f"{stem}_inventory.json"
        if named.is_file():
            return named, None, names
    if not matches:
        return None, "missing", []
    cfg = load_config(repo_root)
    preferred = (cfg.get("default_extract") or "").strip()
    if preferred:
        for match in matches:
            if match.name.startswith(f"{preferred}_"):
                return match, None, names
    if len(matches) == 1:
        return matches[0], None, names
    return None, "multiple", names


def _form_entries(inventory: dict) -> list[dict]:
    out: list[dict] = []
    for entry in inventory.get("files") or []:
        if str(entry.get("type") or "").lower() == "form":
            out.append(entry)
            continue
        name = str(entry.get("file") or "")
        if Path(name).suffix.lower() == ".frm":
            out.append(entry)
    return out


def _count_ticks(comprehension: Path) -> int:
    if not comprehension.is_file():
        return 0
    text = comprehension.read_text(encoding="utf-8", errors="replace")
    numbers = [int(m) for m in TICK_ATTR_RE.findall(text)]
    return max(numbers) if numbers else 0


def _read_verify(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mismatches = raw.get("mismatches") or []
    ok = raw.get("ok")
    if ok is None:
        ok = len(mismatches) == 0
    return {
        "persisted": True,
        "path": None,  # filled by caller
        "ok": bool(ok),
        "mismatch_count": len(mismatches),
        "files_checked": raw.get("files_checked"),
    }


def build_status(
    repo_root: Path | None = None,
    extract: Path | None = None,
    inventory: Path | None = None,
) -> dict:
    """Collect presence/counts from artifacts already on disk."""
    root = (repo_root or REPO).resolve()
    reports = reports_root(root)
    extract_info = resolve_extract_dir(root, extract)
    stem = extract_info.get("name") if extract_info.get("present") else None

    inv_path, inv_reason, inv_names = resolve_inventory_path(
        root, reports, stem, inventory
    )
    inv_data: dict = {}
    if inv_path is not None:
        try:
            inv_data = json.loads(inv_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inv_path, inv_reason, inv_data = None, "unreadable", {}
        else:
            stem = str(inv_data.get("stem") or stem or "")
            if not stem and inv_path is not None:
                stem = inv_path.name.replace("_inventory.json", "")

    forms = _form_entries(inv_data) if inv_data else []
    mapping_raw = load_config(root).get("deep_read_name_map") or {}
    mapping = mapping_raw if isinstance(mapping_raw, dict) else {}
    deep_present: list[str] = []
    deep_absent: list[str] = []
    for entry in forms:
        file_name = str(entry.get("file") or "")
        vb_name = entry.get("vb_name")
        key = _out_key(str(vb_name) if vb_name else None, file_name, mapping)
        report = reports / f"{key}_deep_read.md"
        if report.is_file():
            deep_present.append(file_name)
        else:
            deep_absent.append(file_name)

    comprehension = reports / f"{stem}_comprehension.html" if stem else None
    tick_count = _count_ticks(comprehension) if comprehension else 0
    excerpt = reports / f"{stem}_reimpl_excerpt.html" if stem else None
    io_catalog = reports / f"{stem}_io_catalog.json" if stem else None
    verify_path = reports / f"{stem}_verify.json" if stem else None
    verify_show_path = reports / f"{stem}_verify_show.json" if stem else None
    layout_md = reports / "runtime_layout.md"

    if verify_path is not None and verify_path.is_file():
        try:
            verify_info = _read_verify(verify_path)
            verify_info["path"] = _rel(verify_path, root)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            verify_info = {
                "persisted": False,
                "path": _rel(verify_path, root),
                "ok": None,
                "mismatch_count": None,
                "files_checked": None,
                "reason": "unreadable",
            }
    else:
        verify_info = {
            "persisted": False,
            "path": _rel(verify_path, root) if verify_path else None,
            "ok": None,
            "mismatch_count": None,
            "files_checked": None,
        }

    if verify_show_path is not None and verify_show_path.is_file():
        try:
            show_raw = json.loads(verify_show_path.read_text(encoding="utf-8"))
            verify_show_info = {
                "persisted": True,
                "path": _rel(verify_show_path, root),
                "ok": bool(show_raw.get("ok")),
                "hard_count": show_raw.get("hard_count"),
                "warning_count": show_raw.get("warning_count"),
                "compared": show_raw.get("compared"),
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            verify_show_info = {
                "persisted": False,
                "path": _rel(verify_show_path, root),
                "ok": None,
                "hard_count": None,
                "warning_count": None,
                "compared": None,
                "reason": "unreadable",
            }
    else:
        verify_show_info = {
            "persisted": False,
            "path": _rel(verify_show_path, root) if verify_show_path else None,
            "ok": None,
            "hard_count": None,
            "warning_count": None,
            "compared": None,
        }

    proc_total = inv_data.get("proc_total") if inv_data else None
    if proc_total is None and inv_data:
        proc_total = sum(len(f.get("procedures") or []) for f in inv_data.get("files") or [])

    return {
        "stem": stem,
        "extract": extract_info,
        "inventory": {
            "present": inv_path is not None,
            "path": _rel(inv_path, root) if inv_path else None,
            "reason": inv_reason,
            "candidates": inv_names,
            "file_count": inv_data.get("file_count") if inv_data else None,
            "proc_total": proc_total,
            "form_count": len(forms) if inv_data else None,
        },
        "verify": verify_info,
        "verify_show": verify_show_info,
        "deep_read": {
            "reports": len(deep_present),
            "forms": len(forms),
            "present": deep_present,
            "absent": deep_absent,
        },
        "ticks": {
            "count": tick_count,
            "proc_total": proc_total,
            "comprehension": _rel(comprehension, root) if comprehension and comprehension.is_file() else None,
        },
        "excerpt": {
            "present": bool(excerpt and excerpt.is_file()),
            "path": _rel(excerpt, root) if excerpt and excerpt.is_file() else None,
        },
        "layout": {
            "present": layout_md.is_file(),
            "path": _rel(layout_md, root) if layout_md.is_file() else None,
        },
        "io_catalog": {
            "present": bool(io_catalog and io_catalog.is_file()),
            "path": _rel(io_catalog, root) if io_catalog and io_catalog.is_file() else None,
        },
    }


def format_status_lines(data: dict) -> str:
    """Three short lines. Facts only — no next-step advice."""
    stem = data.get("stem") or "-"
    extract = "yes" if (data.get("extract") or {}).get("present") else "no"
    extract_reason = (data.get("extract") or {}).get("reason")
    if extract_reason == "multiple":
        names = ",".join((data.get("extract") or {}).get("candidates") or [])
        extract = f"multiple:{names}"
    inv = data.get("inventory") or {}
    if inv.get("present"):
        inventory = f"{inv.get('file_count')}files/{inv.get('proc_total')}procs"
    elif inv.get("reason") == "multiple":
        inventory = "multiple"
    else:
        inventory = "no"

    deep = data.get("deep_read") or {}
    ticks = data.get("ticks") or {}
    excerpt = "yes" if (data.get("excerpt") or {}).get("present") else "no"
    layout = "yes" if (data.get("layout") or {}).get("present") else "no"
    io_catalog = "yes" if (data.get("io_catalog") or {}).get("present") else "no"

    verify = data.get("verify") or {}
    if verify.get("persisted"):
        if verify.get("ok"):
            verify_s = "ok"
        else:
            verify_s = f"mismatches={verify.get('mismatch_count')}"
    else:
        verify_s = "not persisted"

    show = data.get("verify_show") or {}
    if show.get("persisted"):
        if not show.get("ok"):
            show_s = f"mismatches={show.get('hard_count')}"
        elif show.get("warning_count"):
            show_s = f"warnings={show.get('warning_count')}"
        else:
            show_s = "ok"
    else:
        show_s = "not persisted"

    line1 = f"stem={stem} extract={extract} inventory={inventory}"
    line2 = (
        f"deep-read={deep.get('reports', 0)}/{deep.get('forms', 0)} "
        f"ticks={ticks.get('count', 0)}/{ticks.get('proc_total') if ticks.get('proc_total') is not None else 0} "
        f"excerpt={excerpt}"
    )
    line3 = f"verify={verify_s} layout={layout} io={io_catalog} show={show_s}"
    return "\n".join((line1, line2, line3))


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Print facts-only pipeline status from existing artifacts"
    )
    ap.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Extract dir (default: default_extract, or the sole folder under extracts/)",
    )
    ap.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Path to <stem>_inventory.json",
    )
    ap.add_argument(
        "--json-only",
        action="store_true",
        help="Print JSON only (default: three text lines, then JSON)",
    )
    args = ap.parse_args(argv)

    data = build_status(REPO, extract=args.extract, inventory=args.inventory)
    if not args.json_only:
        print(format_status_lines(data))
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
