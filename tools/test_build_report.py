"""build_report tests: parallel determinism and VBP ordering (self-contained)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vb6_inventory as inv  # noqa: E402
from lib import cache  # noqa: E402
from lib.cache import content_key  # noqa: E402

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

    def test_cache_key_includes_suffix(self) -> None:
        raw = b"Attribute VB_Name = \"X\"\n"
        k_frm = content_key(raw, f"{inv.PARSER_VERSION}|.frm")
        k_bas = content_key(raw, f"{inv.PARSER_VERSION}|.bas")
        self.assertNotEqual(k_frm, k_bas)

    def test_cache_does_not_confuse_frm_and_bas(self) -> None:
        """Same bytes under .frm vs .bas must not share a cache entry."""
        body = FRM.encode("cp932")
        with tempfile.TemporaryDirectory() as td:
            croot = Path(td) / ".cache"
            frm = Path(td) / "twin.frm"
            bas = Path(td) / "twin.bas"
            frm.write_bytes(body)
            bas.write_bytes(body)
            with patch.object(cache, "cache_root", return_value=croot):
                as_frm = inv.inventory_file(frm, use_cache=True)
                as_bas = inv.inventory_file(bas, use_cache=True)
                # Second pass: bas must still miss the .frm entry (re-parse / own key).
                as_bas_again = inv.inventory_file(bas, use_cache=True)
        self.assertEqual(as_frm["form_kind"], "VB.Form")
        self.assertIsNone(as_bas["form_kind"])
        self.assertIsNone(as_bas_again["form_kind"])
        self.assertEqual(as_frm["procedures"][0]["role"], "event")
        self.assertEqual(as_bas["procedures"][0]["role"], "general")

    def test_html_search_ties_toc_to_section(self) -> None:
        rep = inv.build_report(self.d, self.vbp, use_cache=False, jobs=1)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "inv.html"
            inv.write_html(rep, out)
            doc = out.read_text(encoding="utf-8")
        self.assertIn("data-for='f1'", doc)
        self.assertIn('tr.tocrow[data-for="\'+s.id+\'"]', doc)
        self.assertIn("s.textContent", doc)
        self.assertNotIn("s.innerText", doc)


if __name__ == "__main__":
    unittest.main()
