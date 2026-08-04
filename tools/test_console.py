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
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from lib.config import extracts_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402


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


def find_extracted_frm() -> Path | None:
    """Any extracted .frm; the kit fixture and consumer projects both qualify."""
    root = extracts_root()
    if not root.is_dir():
        return None
    for extract in sorted(p for p in root.iterdir() if p.is_dir()):
        frms = sorted(extract.glob("*.frm"))
        if frms:
            return frms[0]
    return None


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
        cls.frm = find_extracted_frm()
        if cls.frm is None:
            raise unittest.SkipTest("no extracted .frm; run extract first")

    def test_deep_read_survives_cp1252_stdout(self):
        # Write into a temp dir: the repo's reports are investigation history,
        # and a test must never overwrite them.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            proc = run_cli(
                [
                    "deep-read",
                    self.frm.name,
                    "--extract",
                    str(self.frm.parent),
                    "--skeleton",
                    str(out / "skeleton.json"),
                    "--report",
                    str(out / "report.md"),
                ],
                "cp1252",
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("UnicodeEncodeError", proc.stderr)

    def test_lines_survives_cp1252_stdout(self):
        proc = run_cli(["lines", str(self.frm), "1-20"], "cp1252")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("UnicodeEncodeError", proc.stderr)


if __name__ == "__main__":
    unittest.main()
