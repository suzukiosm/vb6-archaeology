"""VB6 ソース（CP932）の行範囲を行番号つきで出す。

監査で「L4626 の Exit Sub より後か」のような判断をするたびに使う。
Cursor の Read は日本語が化けやすく、PowerShell の Get-Content も
エンコーディング指定が要るので、ここを正とする。

usage:
    python tools/frm_lines.py <file> <start>-<end> [<start>-<end> ...]
    python tools/frm_lines.py <file> --find "Form1.Show" [--context 10]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import decode_vb6_bytes  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402


def read_lines(path: Path) -> list[str]:
    return decode_vb6_bytes(path.read_bytes()).splitlines()


def emit(path: Path, lines: list[str], start: int, end: int) -> None:
    start = max(1, start)
    end = min(len(lines), end)
    print(f"=== {path} L{start}-{end}")
    for n in range(start, end + 1):
        print(n, lines[n - 1])
    print()


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file")
    ap.add_argument("ranges", nargs="*", help="START-END（1 始まり・両端含む）")
    ap.add_argument("--find", help="正規表現。ヒット行の前後を出す")
    ap.add_argument("--context", type=int, default=8)
    ap.add_argument("--ignore-case", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        ap.error(f"not a file: {path}")
    lines = read_lines(path)

    if args.find:
        flags = re.IGNORECASE if args.ignore_case else 0
        pat = re.compile(args.find, flags)
        hits = [i + 1 for i, l in enumerate(lines) if pat.search(l)]
        if not hits:
            print(f"(no match for {args.find!r} in {path})")
            return 1
        for n in hits:
            emit(path, lines, n - args.context, n + args.context)

    for r in args.ranges:
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", r)
        if not m:
            ap.error(f"bad range: {r}（START-END で指定）")
        emit(path, lines, int(m.group(1)), int(m.group(2)))

    if not args.find and not args.ranges:
        emit(path, lines, 1, len(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
