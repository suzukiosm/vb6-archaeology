"""One-command demo: extract → inventory → excerpt, no tick, no serve."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tools.demo import main as demo_main

VBP = """\
Type=Exe
Form=Form1.frm
Startup="Form1"
Name="DemoProj"
"""

FRM = """\
VERSION 5.00
Begin VB.Form Form1
   Caption         =   "デモ画面"
End
Attribute VB_Name = "Form1"
Private Sub Form_Load()
End Sub
"""


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = demo_main(argv)
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


class DemoPipelineTests(unittest.TestCase):
    def test_no_serve_writes_inventory_and_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            extract_out = Path(tmp) / "extract"
            reports = Path(tmp) / "reports"
            src.mkdir()
            (src / "demo.vbp").write_bytes(VBP.encode("cp932"))
            (src / "Form1.frm").write_bytes(FRM.encode("cp932"))
            code, out, err = _run(
                [
                    "--vbp",
                    str(src / "demo.vbp"),
                    "--extract-out",
                    str(extract_out),
                    "--reports",
                    str(reports),
                    "--no-serve",
                ]
            )
            self.assertEqual(code, 0, msg=err or out)
            self.assertTrue((reports / "demo_inventory.html").is_file())
            self.assertTrue((reports / "demo_reimpl_excerpt.html").is_file())
            self.assertFalse(
                (reports / "demo_comprehension.html").is_file(),
                "demo must not auto-tick or scaffold comprehension",
            )
            html = (reports / "demo_inventory.html").read_text(encoding="utf-8")
            self.assertIn("Form1", html)
            self.assertIn("VB_Name", html)
            self.assertIn("next:", out.lower())
            self.assertIn("python -m tools serve", out)

    def test_missing_vbp_prints_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.vbp"
            code, _out, err = _run(
                [
                    "--vbp",
                    str(missing),
                    "--extract-out",
                    str(Path(tmp) / "extract"),
                    "--reports",
                    str(Path(tmp) / "reports"),
                    "--no-serve",
                ]
            )
        self.assertNotEqual(code, 0)
        self.assertIn("next:", err.lower())
        self.assertIn("python -m tools", err)
