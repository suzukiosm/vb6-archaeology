"""抽出プロジェクトの全 .frm を `frm_deep_read.py` で一括再生成する。

出力名の既定は **VB_Name の小文字**（例: `Form1` → `form1-skeleton.json`）。
特例（例: `MDIForm1` → `mdi`）は `archaeology.config.json` の
`deep_read_name_map` で指定する。マップ無しなら常に小文字。

    python tools/frm_deep_read_all.py --extract working/extracts/mini_vbp
    python tools/frm_deep_read_all.py --dry-run
    python tools/frm_deep_read_all.py --only Form1.frm
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from lib.config import decode_vb6_bytes, extracts_root, load_config  # noqa: E402

DEEP_READ = REPO / "tools" / "frm_deep_read.py"
VB_NAME_RE = re.compile(r'^\s*Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)


def resolve_extract(arg: Path | None) -> Path:
    if arg is not None:
        extract = arg if arg.is_absolute() else REPO / arg
        return extract.resolve()
    root = extracts_root()
    if not root.is_dir():
        raise SystemExit(f"extracts dir missing: {root} (pass --extract)")
    candidates = sorted(p for p in root.iterdir() if p.is_dir())
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise SystemExit(f"no extracts under {root}; run extract_vbp.py first")
    names = ", ".join(p.name for p in candidates)
    raise SystemExit(
        f"multiple extracts ({names}); pass --extract working/extracts/<stem>"
    )


def vb_name(frm: Path) -> str | None:
    text = decode_vb6_bytes(frm.read_bytes())
    for line in text.splitlines():
        m = VB_NAME_RE.match(line)
        if m:
            return m.group(1)
    return None


def key_for(name: str) -> str:
    """出力キー。config の deep_read_name_map があれば優先、なければ小文字。"""
    mapping = load_config().get("deep_read_name_map") or {}
    if isinstance(mapping, dict):
        for k, v in mapping.items():
            if str(k).lower() == name.lower():
                return str(v)
    return name.lower()


def main() -> int:
    ap = argparse.ArgumentParser(description="全 .frm の deep_read / skeleton 再生成")
    ap.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Extracted project dir (default: sole folder under working/extracts/)",
    )
    ap.add_argument("--only", action="append", default=None, help=".frm 名（複数可）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    extract = resolve_extract(args.extract)
    frms = sorted(p for p in extract.glob("*.frm"))
    if args.only:
        wanted = {o.lower() for o in args.only}
        frms = [p for p in frms if p.name.lower() in wanted]
    if not frms:
        raise SystemExit(f"対象 .frm がありません: {extract}")

    failed = 0
    for frm in frms:
        name = vb_name(frm)
        if not name:
            print(f"SKIP {frm.name}: VB_Name が読めません")
            failed += 1
            continue
        key = key_for(name)
        skeleton = f"{key}-skeleton.json"
        report = f"{key}_deep_read.md"
        print(f"{frm.name:<32} VB_Name={name:<16} -> {skeleton} / {report}")
        if args.dry_run:
            continue
        proc = subprocess.run(
            [
                sys.executable,
                str(DEEP_READ),
                frm.name,
                "--extract",
                str(extract),
                "--skeleton",
                skeleton,
                "--report",
                report,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            failed += 1
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)

    print(f"\n{len(frms)} .frm · 失敗 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
