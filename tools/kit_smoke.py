#!/usr/bin/env python3
"""Kit self-check: fixture pipeline + unit tests. Exit non-zero on failure."""

from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
INV_JSON = REPO / "working" / "reports" / "mini_vbp_inventory.json"
EXTRACT = REPO / "working" / "extracts" / "mini_vbp"
VBP = REPO / "source" / "mini_vbp" / "mini_vbp.vbp"


def run_step(label: str, args: list[str]) -> None:
    """Run one CLI subcommand the same way an agent would."""
    argv = [sys.executable, "-m", "tools", *args]
    print(f"==> {label}")
    print(" ".join(argv))
    proc = subprocess.run(argv, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit(f"kit_smoke failed at: {label} (exit {proc.returncode})")


def run_pipeline() -> None:
    run_step("config-check", ["config-check"])
    run_step("fixture", ["fixture"])
    run_step("extract", ["extract", str(VBP)])
    run_step("inventory", ["inventory", str(EXTRACT)])
    run_step("verify", ["verify", str(INV_JSON)])
    run_step(
        "deep-read Form1",
        ["deep-read", "Form1.frm", "--extract", str(EXTRACT)],
    )
    run_step(
        "deep-read BackupDay (VB_Name != stem)",
        ["deep-read", "BackupDay.frm", "--extract", str(EXTRACT)],
    )
    form12_skel = REPO / "working" / "skeletons" / "form12-skeleton.json"
    if not form12_skel.is_file():
        raise SystemExit(
            "kit_smoke failed: expected form12-skeleton.json "
            "(VB_Name out_key for BackupDay.frm)"
        )
    run_step("deep-read-all", ["deep-read-all", "--extract", str(EXTRACT)])
    run_step("layout", ["layout", "--extract", str(EXTRACT)])
    run_step("comprehend skeleton", ["comprehend", "--inventory", str(INV_JSON), "--force"])
    run_step(
        "comprehend tick",
        [
            "comprehend",
            "--inventory",
            str(INV_JSON),
            "--add-tick",
            "Command1_Click@Form1.frm",
            "--layer",
            "C",
        ],
    )
    # Reports are only trustworthy if every name in them exists in the inventory,
    # so the name check runs after every report has been generated.
    run_step("verify-names", ["verify-names", "--inventory", str(INV_JSON)])
    run_step("serve --check", ["serve", "--check"])
    run_step("scan-chars", ["scan-chars"])


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


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Kit self-check: fixture pipeline + unit tests"
    ).parse_args(argv)
    run_pipeline()
    run_unit_tests()
    print("kit_smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
