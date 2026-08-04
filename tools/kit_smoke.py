#!/usr/bin/env python3
"""Kit self-check: fixture pipeline + unit tests. Exit non-zero on failure."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
INV_JSON = REPO / "working" / "reports" / "mini_vbp_inventory.json"
EXTRACT = REPO / "working" / "extracts" / "mini_vbp"
VBP = REPO / "source" / "mini_vbp" / "mini_vbp.vbp"


def run_step(label: str, argv: list[str]) -> None:
    print(f"==> {label}")
    print(" ".join(argv))
    proc = subprocess.run(argv, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit(f"kit_smoke failed at: {label} (exit {proc.returncode})")


def run_pipeline() -> None:
    py = sys.executable
    run_step("make_fixture", [py, str(TOOLS / "make_fixture.py")])
    run_step(
        "extract_vbp",
        [py, str(TOOLS / "extract_vbp.py"), str(VBP)],
    )
    run_step(
        "vb6_inventory",
        [py, str(TOOLS / "vb6_inventory.py"), str(EXTRACT)],
    )
    run_step(
        "verify_inventory",
        [py, str(TOOLS / "verify_inventory.py"), str(INV_JSON)],
    )
    run_step(
        "verify_report_names",
        [
            py,
            str(TOOLS / "verify_report_names.py"),
            "--inventory",
            str(INV_JSON),
        ],
    )
    run_step(
        "frm_deep_read",
        [
            py,
            str(TOOLS / "frm_deep_read.py"),
            "Form1.frm",
            "--extract",
            str(EXTRACT),
        ],
    )
    run_step(
        "runtime_layout",
        [
            py,
            str(TOOLS / "runtime_layout.py"),
            "--extract",
            str(EXTRACT),
        ],
    )


def run_unit_tests() -> None:
    print("==> unittest discover")
    # Tests import `tools.*`; repo root must be on sys.path.
    root = str(REPO)
    if root not in sys.path:
        sys.path.insert(0, root)
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TOOLS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit("kit_smoke failed at: unittest")


def main() -> int:
    run_pipeline()
    run_unit_tests()
    print("kit_smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
