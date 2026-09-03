#!/usr/bin/env python3
"""Write a UTF-8 sidecar tree of an extract. Does not modify the extract.

Physical line count and line text match ``decode_vb6_bytes(...).splitlines()``.
No pretty-print, no comments, no designer split. Companion binaries are skipped.
Analysis tools keep reading the CP932 extract; this tree is for Cursor Read.

    python -m tools readable
    python -m tools readable --extract working/extracts/mini_vbp
    python -m tools readable --extract working/extracts/mini_vbp --out working/readable/mini_vbp
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from extract_vbp import COMPANION_BY_SOURCE  # noqa: E402
from lib.config import (  # noqa: E402
    decode_vb6_bytes,
    extracts_root,
    preferred_extract,
    readable_dir_root,
)
from lib.console import enable_utf8_stdio  # noqa: E402

TEXT_SUFFIXES = frozenset(
    {".vbp", ".frm", ".bas", ".cls", ".ctl", ".pag", ".dob", ".dsr"}
)
SKIP_SUFFIXES = frozenset(
    suffix
    for suffixes in COMPANION_BY_SOURCE.values()
    for suffix in suffixes
)
REPORT_NAME = "_readable_report.json"


def readable_root(repo_root: Path | None = None) -> Path:
    return readable_dir_root(repo_root)


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


def default_out(extract: Path, repo_root: Path | None = None) -> Path:
    return (readable_root(repo_root) / extract.name).resolve()


def classify_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return "text"
    if suffix in SKIP_SUFFIXES:
        return "companion_binary"
    return "not_source_text"


def decoded_lines(path: Path, repo_root: Path | None = None) -> list[str]:
    return decode_vb6_bytes(path.read_bytes(), repo_root).splitlines()


def write_utf8_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines)
    if lines:
        body += "\n"
    path.write_text(body, encoding="utf-8", newline="\n")


def write_readable(
    extract: Path,
    out: Path,
    repo_root: Path | None = None,
) -> dict:
    extract = extract.resolve()
    out = out.resolve()
    if not extract.is_dir():
        raise SystemExit(f"extract not found: {extract}")
    if out == extract or extract in out.parents:
        raise SystemExit(
            f"refusing to write readable tree onto the extract: {out}"
        )
    if out in extract.parents:
        raise SystemExit(
            f"refusing to write readable tree above the extract: {out}"
        )

    written: list[dict] = []
    skipped: list[dict] = []
    mismatches: list[dict] = []

    for src in sorted(p for p in extract.iterdir() if p.is_file()):
        kind = classify_file(src)
        name = src.name
        if kind != "text":
            skipped.append({"file": name, "reason": kind})
            continue
        lines = decoded_lines(src, repo_root)
        dest = out / name
        write_utf8_lines(dest, lines)
        got = dest.read_text(encoding="utf-8").splitlines()
        entry = {"file": name, "lines": len(lines)}
        written.append(entry)
        if got != lines:
            mismatches.append(
                {
                    "file": name,
                    "src_lines": len(lines),
                    "out_lines": len(got),
                }
            )

    report = {
        "extract": str(extract),
        "out": str(out),
        "written": written,
        "skipped": skipped,
        "line_mismatch": mismatches,
        "ok": not mismatches,
        "note": (
            "UTF-8 sidecar for Cursor Read. Canon remains the extract (CP932). "
            "Physical lines match decode_vb6_bytes(...).splitlines()."
        ),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=(
            "Write a UTF-8 sidecar of an extract (same physical lines). "
            "Does not modify the extract. Not for inventory/deep-read."
        )
    )
    ap.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Extracted project dir (default: default_extract or sole extract)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output dir (default: working/readable/<stem>)",
    )
    args = ap.parse_args(argv)
    extract = resolve_extract(args.extract)
    out = args.out
    if out is None:
        dest = default_out(extract)
    else:
        dest = out if out.is_absolute() else (REPO / out)
        dest = dest.resolve()
    report = write_readable(extract, dest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    n_write = len(report["written"])
    n_skip = len(report["skipped"])
    print(f"readable: wrote {n_write} skipped {n_skip} -> {dest}")
    if not report["ok"]:
        print("readable: line mismatch", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
