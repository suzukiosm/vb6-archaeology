#!/usr/bin/env python3
"""Copy a VB6 .vbp and its referenced source files.

Never writes under protected source trees listed in archaeology.config.json
(default: source/).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.config import (  # noqa: E402
    decode_vb6_bytes,
    default_source_root,
    extracts_root,
    protected_dir_names,
)
from lib.console import enable_utf8_stdio  # noqa: E402

# Keys that name project-relative source files in a .vbp
FILE_KEYS = (
    "Form",
    "Module",
    "Class",
    "UserControl",
    "PropertyPage",
    "UserDocument",
    "Designer",
    "RelatedDoc",
    "ResFile32",
)

LINE_RE = re.compile(
    r"^(?P<key>[A-Za-z0-9]+)=(?P<value>.+)$",
    re.IGNORECASE,
)


def decode_vbp(raw: bytes) -> str:
    return decode_vb6_bytes(raw)


def parse_referenced_files(vbp_text: str) -> tuple[list[str], list[str]]:
    files: list[str] = []
    skipped_refs: list[str] = []
    seen: set[str] = set()

    for line in vbp_text.splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        value = m.group("value").strip().strip('"')
        key_norm = key.lower()

        if key_norm == "reference":
            skipped_refs.append(value)
            continue

        if key_norm not in {k.lower() for k in FILE_KEYS}:
            continue

        # Module=Module1; path.bas  /  Form=path.frm
        path_part = value.split(";", 1)[-1].strip() if ";" in value else value
        if not path_part or path_part in seen:
            continue
        seen.add(path_part)
        files.append(path_part)

    return files, skipped_refs


def companion_frx(path: Path) -> Path | None:
    if path.suffix.lower() == ".frm":
        frx = path.with_suffix(".frx")
        return frx if frx.is_file() else None
    return None


def ensure_not_writing_source(dest: Path, source_root: Path) -> None:
    try:
        dest_resolved = dest.resolve()
        source_resolved = source_root.resolve()
    except OSError as exc:
        raise SystemExit(f"path resolve failed: {exc}") from exc
    if dest_resolved == source_resolved or source_resolved in dest_resolved.parents:
        raise SystemExit(
            f"refusing to write under source tree: {dest_resolved} "
            f"(source={source_resolved})"
        )


def extract(vbp_path: Path, out_dir: Path, source_root: Path) -> dict:
    ensure_not_writing_source(out_dir, source_root)
    if not vbp_path.is_file():
        raise SystemExit(f"vbp not found: {vbp_path}")

    text = decode_vbp(vbp_path.read_bytes())
    rel_files, skipped_refs = parse_referenced_files(text)

    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    missing: list[str] = []

    # Always copy the vbp itself
    dest_vbp = out_dir / vbp_path.name
    shutil.copy2(vbp_path, dest_vbp)
    copied.append(vbp_path.name)

    vbp_dir = vbp_path.parent
    for rel in rel_files:
        src = (vbp_dir / rel).resolve()
        # Stay within source tree when possible; still allow listed relative paths
        if not src.is_file():
            missing.append(rel)
            continue
        dest = out_dir / Path(rel).name
        ensure_not_writing_source(dest, source_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(dest.name)

        frx = companion_frx(src)
        if frx is not None:
            dest_frx = out_dir / frx.name
            ensure_not_writing_source(dest_frx, source_root)
            shutil.copy2(frx, dest_frx)
            copied.append(dest_frx.name)

    report = {
        "vbp": str(vbp_path),
        "out": str(out_dir),
        "copied": copied,
        "missing": missing,
        "skipped_ref_count": len(skipped_refs),
    }
    report_path = out_dir / "_extract_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    protected = ", ".join(protected_dir_names())
    parser = argparse.ArgumentParser(
        description=(
            "Extract a VB6 .vbp and referenced files "
            f"(read-only on protected dirs: {protected})."
        )
    )
    parser.add_argument(
        "vbp",
        type=Path,
        help="Path to .vbp (usually under source/ or another protected tree)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: working/extracts/<vbp-stem>)",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Protected source root (default: archaeology.config.json default_source_dir)",
    )
    args = parser.parse_args(argv)

    source_root = (args.source_root or default_source_root()).resolve()
    vbp_path = args.vbp
    if not vbp_path.is_absolute():
        vbp_path = (REPO_ROOT / vbp_path).resolve()
    else:
        vbp_path = vbp_path.resolve()

    out_dir = args.out
    if out_dir is None:
        out_dir = extracts_root() / vbp_path.stem
    elif not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir = out_dir.resolve()

    report = extract(vbp_path, out_dir, source_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
