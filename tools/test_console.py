"""Tool output must survive a non-Japanese console code page.

CP932 captions reach stdout, so on a cp1252 console the whole run used to die
with UnicodeEncodeError after the analysis had already succeeded. CI on an
English Windows runner is where this surfaced.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from lib.console import enable_utf8_stdio  # noqa: E402

FIXTURE_VBP = REPO_ROOT / "source" / "mini_vbp" / "mini_vbp.vbp"
EXTRACT = REPO_ROOT / "working" / "extracts" / "mini_vbp"


def run_cli(args: list[str], encoding: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": encoding, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class TestEnableUtf8Stdio(unittest.TestCase):
    def test_ignores_streams_without_reconfigure(self):
        original = sys.stdout
        sys.stdout = io.StringIO()
        try:
            enable_utf8_stdio()  # must not raise on StringIO
        finally:
            sys.stdout = original

    def test_is_idempotent(self):
        enable_utf8_stdio()
        enable_utf8_stdio()
        self.assertTrue(True)


class TestJapaneseOutputUnderLegacyCodePage(unittest.TestCase):
    """Reproduces the CI failure: cp1252 stdout plus a Japanese Caption."""

    @classmethod
    def setUpClass(cls):
        if not EXTRACT.is_dir():
            run_cli(["fixture"], "utf-8")
            run_cli(["extract", str(FIXTURE_VBP)], "utf-8")

    def test_deep_read_survives_cp1252_stdout(self):
        proc = run_cli(
            ["deep-read", "Form1.frm", "--extract", str(EXTRACT)], "cp1252"
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("UnicodeEncodeError", proc.stderr)

    def test_lines_survives_cp1252_stdout(self):
        proc = run_cli(
            ["lines", str(EXTRACT / "Form1.frm"), "1-20"], "cp1252"
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("UnicodeEncodeError", proc.stderr)


if __name__ == "__main__":
    unittest.main()
