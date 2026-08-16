#!/usr/bin/env python3
"""Catalog Open / Kill / Name / Get / Put statements across an extract.

Facts only: file + physical line + kind + optional quoted path. No business
meaning. GoTo-skip attachment reads existing skeleton ``goto_skipped_stmts``
(same source file + physical line). Does not import frm_deep_read.

    python -m tools io-catalog
    python -m tools io-catalog --extract working/extracts/mini_vbp
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.config import (  # noqa: E402
    decode_vb6_bytes,
    extracts_root,
    preferred_extract,
    reports_root,
    skeletons_root,
)
from lib.console import enable_utf8_stdio  # noqa: E402
from lib.vbparse import iter_logical_lines  # noqa: E402

SCAN_SUFFIXES = frozenset({".frm", ".bas", ".cls", ".ctl", ".pag", ".dob", ".dsr"})
IO_KINDS = ("open", "kill", "name", "get", "put")
VB_NAME_RE = re.compile(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)

_OPEN_RE = re.compile(r".*\bOpen\b.*\bAs\s*#\s*\w+", re.IGNORECASE)
_KILL_RE = re.compile(r"\bKill\b", re.IGNORECASE)
# VB6 rename: Name <old> As <new>. Not ``Name =`` (property) or ``Name(``.
_NAME_RE = re.compile(r"\bName\s+[^=(].*\sAs\s", re.IGNORECASE)
_GET_RE = re.compile(r"\bGet\s+#", re.IGNORECASE)
_PUT_RE = re.compile(r"\bPut\s+#", re.IGNORECASE)
_KIND_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("open", _OPEN_RE),
    ("kill", _KILL_RE),
    ("name", _NAME_RE),
    ("get", _GET_RE),
    ("put", _PUT_RE),
)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def classify_io_statement(text: str) -> str | None:
    """Return open/kill/name/get/put if the logical line is an I/O stmt."""
    s = text.strip()
    if not s or s.startswith("'"):
        return None
    code = s.split("'")[0].strip()
    if not code:
        return None
    for kind, pattern in _KIND_RULES:
        if pattern.search(code):
            return kind
    return None


def path_fragment(text: str) -> str:
    """Best-effort path snippet (quoted literals preferred)."""
    quotes = re.findall(r'"([^"]*)"', text)
    if quotes:
        for q in reversed(quotes):
            if re.search(r"\.\w{1,8}\b|\\|/", q):
                return q[:120]
        return quotes[-1][:120]
    return ""


def scan_source_text(text: str, file_name: str) -> list[dict]:
    """Scan decoded VB6 text. ``file_name`` is the inventory basename."""
    lines = text.splitlines()
    entries: list[dict] = []
    for logical in iter_logical_lines(lines):
        kind = classify_io_statement(logical.text)
        if kind is None:
            continue
        code = logical.text.strip().split("'")[0].strip()
        entries.append({
            "file": file_name,
            "line": logical.phys_start,
            "kind": kind,
            "text": code[:200],
            "path_fragment": path_fragment(code),
            "goto_skip": None,
        })
    return entries


def scan_file(path: Path) -> list[dict]:
    raw = path.read_bytes()
    text = decode_vb6_bytes(raw)
    return scan_source_text(text, path.name)


def extract_vb_name(text: str) -> str | None:
    match = VB_NAME_RE.search(text)
    if match:
        return match.group(1)
    return None


def iter_extract_sources(extract: Path) -> list[Path]:
    if not extract.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(extract.rglob("*")):
        if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
            out.append(path)
    return out


def load_goto_skip_index(
    skeletons_dir: Path | None,
    file_by_vb_name: dict[str, str],
) -> dict[tuple[str, int], dict]:
    """Map (file_basename.lower(), stmt_line) → skip facts from skeletons."""
    index: dict[tuple[str, int], dict] = {}
    if skeletons_dir is None or not skeletons_dir.is_dir():
        return index
    for path in sorted(skeletons_dir.glob("*-skeleton.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        skips = data.get("goto_skipped_stmts") or []
        if not skips:
            continue
        form_name = str((data.get("form") or {}).get("name") or "")
        source_file = file_by_vb_name.get(form_name.lower()) if form_name else None
        if not source_file:
            continue
        for skip in skips:
            if not isinstance(skip, dict):
                continue
            try:
                stmt_line = int(skip.get("stmt_line") or skip.get("open_line") or 0)
            except (TypeError, ValueError):
                continue
            if stmt_line <= 0:
                continue
            key = (source_file.lower(), stmt_line)
            if key in index:
                continue
            index[key] = {
                "sub": skip.get("sub") or "",
                "goto_line": skip.get("goto_line"),
                "label": skip.get("label") or "",
                "stmt_kind": skip.get("stmt_kind") or "",
            }
    return index


def attach_goto_skips(
    entries: list[dict],
    skip_index: dict[tuple[str, int], dict],
) -> list[dict]:
    """Attach skip facts when file+line match a skeleton finding."""
    for entry in entries:
        key = (str(entry.get("file") or "").lower(), int(entry.get("line") or 0))
        hit = skip_index.get(key)
        entry["goto_skip"] = dict(hit) if hit else None
    return entries


def build_catalog(
    extract: Path,
    skeletons_dir: Path | None = None,
    repo_root: Path | None = None,
) -> dict:
    """Scan extract sources and attach existing GoTo-skip facts."""
    root = (repo_root or REPO).resolve()
    extract = extract.resolve()
    entries: list[dict] = []
    file_by_vb_name: dict[str, str] = {}
    for path in iter_extract_sources(extract):
        raw = path.read_bytes()
        text = decode_vb6_bytes(raw)
        vb_name = extract_vb_name(text)
        if vb_name:
            file_by_vb_name.setdefault(vb_name.lower(), path.name)
        entries.extend(scan_source_text(text, path.name))
    entries.sort(key=lambda e: (e["file"].lower(), e["line"], e["kind"]))
    skip_index = load_goto_skip_index(skeletons_dir, file_by_vb_name)
    attach_goto_skips(entries, skip_index)
    counts = Counter(e["kind"] for e in entries)
    return {
        "stem": extract.name,
        "extract": _rel(extract, root),
        "entry_count": len(entries),
        "kind_counts": {kind: counts.get(kind, 0) for kind in IO_KINDS},
        "entries": entries,
    }


def render_markdown(data: dict) -> str:
    counts = data.get("kind_counts") or {}
    parts = [f"{kind}={counts.get(kind, 0)}" for kind in IO_KINDS]
    lines = [
        "# I/O カタログ（事実）\n",
        "\n",
        f"extract: `{data.get('extract') or ''}`\n",
        f"件数: {data.get('entry_count', 0)}（{' · '.join(parts)}）\n",
        "\n",
        "業務意味は書かない。GoTo 飛び越えは既存 skeleton の "
        "`goto_skipped_stmts` との file+line 突合のみ。\n",
        "\n",
        "| file | line | kind | path | goto_skip |\n",
        "|---|---|---|---|---|\n",
    ]
    for entry in data.get("entries") or []:
        path = entry.get("path_fragment") or "—"
        if path != "—":
            path = f"`{path}`"
        skip = entry.get("goto_skip")
        if skip:
            skip_s = (
                f"`{skip.get('sub') or ''}` "
                f"L{skip.get('goto_line')}→{skip.get('label') or ''}"
            )
        else:
            skip_s = "—"
        lines.append(
            f"| `{entry.get('file')}` | {entry.get('line')} | "
            f"{entry.get('kind')} | {path} | {skip_s} |\n"
        )
    if not data.get("entries"):
        lines.append("| — | — | — | — | — |\n")
    return "".join(lines)


def write_reports(data: dict, reports: Path) -> tuple[Path, Path]:
    reports.mkdir(parents=True, exist_ok=True)
    stem = data.get("stem") or "extract"
    json_path = reports / f"{stem}_io_catalog.json"
    md_path = reports / f"{stem}_io_catalog.md"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(data), encoding="utf-8")
    return json_path, md_path


def resolve_extract(arg: Path | None, repo_root: Path | None = None) -> Path:
    root = (repo_root or REPO).resolve()
    if arg is not None:
        extract = arg if arg.is_absolute() else root / arg
        return extract.resolve()
    preferred = preferred_extract(root)
    if preferred is not None:
        return preferred
    extracts = extracts_root(root)
    if not extracts.is_dir():
        raise SystemExit(f"extracts dir missing: {extracts} (pass --extract)")
    candidates = sorted(p for p in extracts.iterdir() if p.is_dir())
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise SystemExit(f"no extracts under {extracts}; run extract first")
    names = ", ".join(p.name for p in candidates)
    raise SystemExit(
        f"multiple extracts ({names}); pass --extract working/extracts/<stem> "
        "or set default_extract in archaeology.config.json"
    )


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=(
            "Catalog Open / Kill / Name / Get / Put in an extract "
            "(facts only; attach existing GoTo-skip findings)"
        )
    )
    ap.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Extracted project dir (default: sole folder under working/extracts/)",
    )
    args = ap.parse_args(argv)
    extract = resolve_extract(args.extract)
    if not extract.is_dir():
        print(f"extract not found: {extract}", file=sys.stderr)
        return 1
    reports = reports_root()
    skeletons = skeletons_root()
    data = build_catalog(extract, skeletons_dir=skeletons, repo_root=REPO)
    json_path, md_path = write_reports(data, reports)
    counts = data["kind_counts"]
    kind_s = " ".join(f"{k}={counts[k]}" for k in IO_KINDS)
    print(f"I/O catalog: {data['entry_count']} entries ({kind_s})")
    print(f"JSON -> {json_path}")
    print(f"MD   -> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
