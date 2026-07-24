"""build_report tests: parallel determinism and VBP ordering (self-contained)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vb6_inventory as inv  # noqa: E402

VBP = """\
Type=Exe
Form=Form1.frm
Module=Module1; Module1.bas
Module=Module2; Module2.bas
Startup="Form1"
Name="proj"
"""

FRM = """\
VERSION 5.00
Begin VB.Form Form1
   Caption = "F"
End
Attribute VB_Name = "Form1"
Private Sub Form_Load()
End Sub
"""

BAS1 = 'Attribute VB_Name = "Module1"\nPublic Sub A()\nEnd Sub\n'
BAS2 = 'Attribute VB_Name = "Module2"\nPublic Function B()\nEnd Function\n'


class BuildReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        (self.d / "proj.vbp").write_bytes(VBP.encode("cp932"))
        (self.d / "Form1.frm").write_bytes(FRM.encode("cp932"))
        (self.d / "Module1.bas").write_bytes(BAS1.encode("cp932"))
        (self.d / "Module2.bas").write_bytes(BAS2.encode("cp932"))
        self.vbp = self.d / "proj.vbp"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_parallel_matches_sequential(self) -> None:
        seq = inv.build_report(self.d, self.vbp, use_cache=False, jobs=1)
        par = inv.build_report(self.d, self.vbp, use_cache=False, jobs=4)
        self.assertEqual(seq, par)

    def test_vbp_order_preserved(self) -> None:
        rep = inv.build_report(self.d, self.vbp, use_cache=False, jobs=4)
        self.assertEqual(
            [f["file"] for f in rep["files"]],
            ["Form1.frm", "Module1.bas", "Module2.bas"],
        )

    def test_proc_total(self) -> None:
        rep = inv.build_report(self.d, self.vbp, use_cache=False, jobs=1)
        self.assertEqual(rep["proc_total"], 3)


if __name__ == "__main__":
    unittest.main()
