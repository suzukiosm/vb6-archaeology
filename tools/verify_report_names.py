#!/usr/bin/env python3
"""inventory の名前集合とレポート言及を照合する（再利用 CLI）。

``verify_inventory.py`` は End 文カウント専用。本ツールは **名前集合** 専用。

正規化方針:
  - ファイル名: パス末尾の basename を小文字化。拡張子付きと stem の両方を既知集合に入れる。
  - プロシージャ名: 小文字化して比較（VB6 は大小無視）。
  - inventory の ``vb_name`` もファイル側既知集合に含める（レポートが VB_Name で書くため）。

抽出方針（保守的・取りこぼし優先）:
  - ``*.frm`` / ``*.bas`` / ``*.cls`` のファイル名トークン
  - バッククォート内でプロシージャらしい識別子（アンダースコアを含み、
    先頭が英字大文字＝VB 流儀。snake_case の JSON キーは除外）
  - ``Sub|Function|Property Get|Property Let|Property Set`` 直後の識別子

役割ラベル・callgraph・消費者固有形式は検証しない。

Usage:
  python tools/verify_report_names.py
  python tools/verify_report_names.py --inventory working/reports/mini_vbp_inventory.json
  python tools/verify_report_names.py --inventory ... --reports working/reports/foo.md
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.config import load_config, reports_root  # noqa: E402

FILE_TOKEN_RE = re.compile(
    r"\b([A-Za-z_][\w]*\.(?:frm|bas|cls))\b",
    re.IGNORECASE,
)
BACKTICK_RE = re.compile(r"`([^`\n]{1,120})`")
# PascalCase-ish with underscore (Form_Load, Command1_Click). snake_case 除外。
PROC_LIKE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z][A-Za-z0-9]*)+$")
# バッククォートは VB イベント/ハンドラ風サフィックスのみ（定数 HWND_TOPMOST 等を除外）
EVENT_SUFFIX_RE = re.compile(
    r"(?i)_("
    r"Click|DblClick|Load|Unload|Initialize|Terminate|Activate|Deactivate|"
    r"Resize|Paint|QueryUnload|GotFocus|LostFocus|KeyPress|KeyDown|KeyUp|"
    r"Change|Scroll|DropDown|CloseUp|Timer|Validate|PathChange|PatternChange|"
    r"MouseDown|MouseUp|MouseMove|OLEDragDrop|OLECompleteDrag|Error|"
    r"LinkOpen|LinkClose|LinkExecute|LinkNotify|ItemCheck"
    r")$"
)
SUB_DECL_RE = re.compile(
    r"\b(?:Sub|Function|Property\s+(?:Get|Let|Set))\s+([A-Za-z_][\w]*)\b",
    re.IGNORECASE,
)

DEFAULT_EXTS = (".md", ".html", ".json")
INVENTORY_NAME_RE = re.compile(r".*_inventory\.(json|md|html)$", re.IGNORECASE)


def norm_file(name: str) -> str:
    return Path(name).name.lower()


def norm_proc(name: str) -> str:
    return name.strip().lower()


def load_inventory_sets(data: dict) -> tuple[set[str], set[str]]:
    """Return (known_files, known_procs) — all lowercased."""
    files: set[str] = set()
    procs: set[str] = set()
    for entry in data.get("files") or []:
        fname = entry.get("file") or ""
        if fname:
            base = norm_file(fname)
            files.add(base)
            files.add(Path(base).stem.lower())
        vb = entry.get("vb_name") or ""
        if vb:
            files.add(norm_proc(vb))
        for p in entry.get("procedures") or []:
            name = p.get("name") if isinstance(p, dict) else None
            if name:
                procs.add(norm_proc(name))
        # Declare Function/Sub（例: QRmodel2）も名前集合に含める
        for d in entry.get("declares") or []:
            name = d.get("name") if isinstance(d, dict) else None
            if name:
                procs.add(norm_proc(name))
    # 他 VBP・外部モジュールへの言及を許可（消費者 config）
    raw = load_config().get("verify_report_allow_files") or []
    if isinstance(raw, list):
        for item in raw:
            base = norm_file(str(item))
            files.add(base)
            files.add(Path(base).stem.lower())
    return files, procs


def is_proc_like(token: str) -> bool:
    """Backtick 候補: PascalCase_with_underscore かつ VB イベント風サフィックス。"""
    if not PROC_LIKE_RE.match(token):
        return False
    if not any(ch.isupper() for ch in token):
        return False
    return EVENT_SUFFIX_RE.search(token) is not None


def extract_mentions(text: str) -> tuple[set[str], set[str]]:
    """Return (file_mentions, proc_mentions) — lowercased tokens."""
    files: set[str] = set()
    procs: set[str] = set()

    for m in FILE_TOKEN_RE.finditer(text):
        files.add(norm_file(m.group(1)))

    for m in BACKTICK_RE.finditer(text):
        inner = m.group(1).strip()
        if not inner:
            continue
        if FILE_TOKEN_RE.fullmatch(inner):
            files.add(norm_file(inner))
            continue
        # strip trailing punctuation / markdown noise
        token = inner.split()[0]
        token = token.rstrip(".,;:)")
        if is_proc_like(token):
            procs.add(norm_proc(token))

    for m in SUB_DECL_RE.finditer(text):
        # End Sub / Exit Sub の誤ヒットを避ける
        start = m.start()
        prefix = text[max(0, start - 6) : start].lower()
        if prefix.rstrip().endswith("end") or prefix.rstrip().endswith("exit"):
            continue
        name = m.group(1)
        # 宣言行はイベント風でなくてもよいが、行番号ラベル L123 等は除外
        if re.fullmatch(r"L\d+", name, flags=re.IGNORECASE):
            continue
        if len(name) < 2:
            continue
        procs.add(norm_proc(name))

    return files, procs


def resolve_inventory(path: Path | None) -> Path:
    if path is not None:
        p = path if path.is_absolute() else REPO_ROOT / path
        return p.resolve()
    reports = reports_root()
    cands = sorted(reports.glob("*_inventory.json"))
    if len(cands) != 1:
        raise SystemExit(
            f"pass --inventory (found {len(cands)} *_inventory.json under {reports})"
        )
    return cands[0].resolve()


def iter_report_files(
    roots: list[Path],
    exts: tuple[str, ...],
    exclude_globs: list[str],
    inventory_path: Path,
) -> list[Path]:
    out: list[Path] = []
    inv_resolved = inventory_path.resolve()

    def excluded(path: Path) -> bool:
        rel = str(path).replace("\\", "/")
        name = path.name
        if path.resolve() == inv_resolved:
            return True
        # 任意 stem の inventory 成果物は照合対象外（HTML 内のサンプル宣言を拾わない）
        if INVENTORY_NAME_RE.match(name):
            return True
        for pat in exclude_globs:
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
                return True
        return False

    for root in roots:
        root = root if root.is_absolute() else REPO_ROOT / root
        if root.is_file():
            if not excluded(root) and root.suffix.lower() in exts:
                out.append(root.resolve())
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            if excluded(path):
                continue
            out.append(path.resolve())
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def verify(
    inventory_path: Path,
    report_paths: list[Path],
) -> dict:
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    known_files, known_procs = load_inventory_sets(data)

    unknown_files: dict[str, list[str]] = {}
    unknown_procs: dict[str, list[str]] = {}

    for path in report_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        ment_files, ment_procs = extract_mentions(text)
        try:
            label = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            label = str(path).replace("\\", "/")

        for f in sorted(ment_files - known_files):
            unknown_files.setdefault(f, []).append(label)
        for p in sorted(ment_procs - known_procs):
            unknown_procs.setdefault(p, []).append(label)

    file_hits = [
        {"name": name, "reports": reps} for name, reps in sorted(unknown_files.items())
    ]
    proc_hits = [
        {"name": name, "reports": reps} for name, reps in sorted(unknown_procs.items())
    ]
    ok = not file_hits and not proc_hits
    return {
        "ok": ok,
        "inventory": str(inventory_path).replace("\\", "/"),
        "reports_scanned": len(report_paths),
        "known_files": len(known_files),
        "known_procs": len(known_procs),
        "unknown_file_count": len(file_hits),
        "unknown_proc_count": len(proc_hits),
        "unknown_files": file_hits,
        "unknown_procs": proc_hits,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify report name mentions against inventory name sets"
    )
    ap.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="<stem>_inventory.json (default: sole *_inventory.json under reports/)",
    )
    ap.add_argument(
        "--reports",
        type=Path,
        nargs="*",
        default=None,
        help="Files or dirs to scan (default: working/reports/**)",
    )
    ap.add_argument(
        "--ext",
        nargs="*",
        default=list(DEFAULT_EXTS),
        help="Extensions to include (default: .md .html .json)",
    )
    ap.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        help="fnmatch pattern to exclude (repeatable; matched against name or path)",
    )
    args = ap.parse_args(argv)

    inv = resolve_inventory(args.inventory)
    if not inv.is_file():
        print(f"inventory not found: {inv}", file=sys.stderr)
        return 2

    exts = tuple(
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in (args.ext or DEFAULT_EXTS)
    )
    if args.reports:
        roots = list(args.reports)
    else:
        roots = [reports_root()]

    report_paths = iter_report_files(roots, exts, list(args.exclude_glob or []), inv)
    summary = verify(inv, report_paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["ok"]:
        print(
            f"name mismatches: none "
            f"(files={summary['known_files']} procs={summary['known_procs']} "
            f"reports={summary['reports_scanned']})"
        )
        return 0
    print(
        f"name mismatches: files={summary['unknown_file_count']} "
        f"procs={summary['unknown_proc_count']}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
