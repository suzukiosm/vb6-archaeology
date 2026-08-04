#!/usr/bin/env python3
"""テキスト資産に混入した不正な制御文字を検出する。

主目的は **PowerShell のバッククォート・エスケープ由来の破損** の早期発見。
PowerShell の二重引用符文字列内では `` ` `` がエスケープ文字なので、Markdown を
PS 経由で書くと以下のように潰れる:

    `Form1`    → \\x0c + "orm1"      (`F = FF)
    `visible`  → \\x0b + "isible"    (`v = VT)
    ```vb      → `     + \\x0b + "b"

TAB / LF / CR 以外の C0 制御文字と DEL を「不正」とみなす。

走査ルートと除外ディレクトリは `archaeology.config.json` の `scan_roots` /
`scan_skip_dirs`。保護ディレクトリとパスマーカーは自動で除外する。

使い方:
    python -m tools scan-chars                    # config の既定ルートを走査
    python -m tools scan-chars docs tools         # ルート指定
    python -m tools scan-chars --ext .md .py

終了コード: 検出 0 件で 0、1 件以上で 1（CI / フックで使える）。
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import scan_roots, scan_skip_dirs  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

DEFAULT_EXT = (".md", ".mdc", ".ts", ".tsx", ".json", ".py", ".css")
BAD_CHARS = ({chr(c) for c in range(0x20)} | {"\x7f"}) - {"\t", "\n", "\r"}


def iter_files(roots: list[str], exts: tuple[str, ...]):
    skip = set(scan_skip_dirs())
    seen: set[str] = set()
    for root in roots:
        if os.path.isfile(root):
            yield os.path.normpath(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in filenames:
                if os.path.splitext(name)[1].lower() not in exts:
                    continue
                full = os.path.normpath(os.path.join(dirpath, name))
                if full not in seen:
                    seen.add(full)
                    yield full


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="*", default=None)
    ap.add_argument("--ext", nargs="*", default=list(DEFAULT_EXT))
    args = ap.parse_args(argv)

    exts = tuple(e.lower() if e.startswith(".") else "." + e.lower() for e in args.ext)
    files = 0
    hits = 0
    for path in iter_files(args.roots or scan_roots(), exts):
        try:
            text = io.open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        files += 1
        for lineno, line in enumerate(text.split("\n"), 1):
            bad = sorted({ch for ch in line if ch in BAD_CHARS})
            if not bad:
                continue
            hits += 1
            codes = " ".join(f"\\x{ord(c):02x}" for c in bad)
            print(f"{path}:{lineno}: {codes} | {line.strip()[:160]}")

    print(f"--- files={files} hits={hits}")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
