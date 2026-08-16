"""Same-stem designer companions are copied; contents are not parsed."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.extract_vbp import companion_frx, companion_paths, extract


class CompanionPathTests(unittest.TestCase):
    def test_frm_finds_frx_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frm = root / "Form1.frm"
            frx = root / "Form1.frx"
            ctx = root / "Form1.ctx"
            frm.write_text("Begin VB.Form Form1\nEnd\n", encoding="utf-8")
            frx.write_bytes(b"frx")
            ctx.write_bytes(b"not-a-companion")
            self.assertEqual(companion_paths(frm), [frx])
            self.assertEqual(companion_frx(frm), frx)

    def test_ctl_finds_ctx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctl = root / "MiniCtl.ctl"
            ctx = root / "MiniCtl.ctx"
            ctl.write_text("Begin VB.UserControl MiniCtl\nEnd\n", encoding="utf-8")
            ctx.write_bytes(b"ctx")
            self.assertEqual(companion_paths(ctl), [ctx])
            self.assertIsNone(companion_frx(ctl))

    def test_pag_dob_dsr_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pag = root / "P.pag"
            dob = root / "D.dob"
            dsr = root / "R.dsr"
            pag.write_text("x", encoding="utf-8")
            dob.write_text("x", encoding="utf-8")
            dsr.write_text("x", encoding="utf-8")
            (root / "P.pgx").write_bytes(b"pgx")
            (root / "D.dox").write_bytes(b"dox")
            (root / "R.dsx").write_bytes(b"dsx")
            self.assertEqual([p.suffix for p in companion_paths(pag)], [".pgx"])
            self.assertEqual([p.suffix for p in companion_paths(dob)], [".dox"])
            self.assertEqual([p.suffix for p in companion_paths(dsr)], [".dsx"])

    def test_bas_has_no_companion_even_if_frx_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bas = root / "Module1.bas"
            bas.write_text("Attribute VB_Name = \"Module1\"\n", encoding="utf-8")
            (root / "Module1.frx").write_bytes(b"nope")
            self.assertEqual(companion_paths(bas), [])

    def test_missing_companion_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frm = Path(tmp) / "Form1.frm"
            frm.write_text("Begin VB.Form Form1\nEnd\n", encoding="utf-8")
            self.assertEqual(companion_paths(frm), [])
            self.assertIsNone(companion_frx(frm))


class ExtractCompanionCopyTests(unittest.TestCase):
    def test_extract_copies_ctx_next_to_ctl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            out = Path(tmp) / "out"
            src.mkdir()
            (src / "mini.vbp").write_text(
                "Type=Exe\nUserControl=MiniCtl; MiniCtl.ctl\n",
                encoding="utf-8",
            )
            (src / "MiniCtl.ctl").write_text(
                "Begin VB.UserControl MiniCtl\nEnd\n",
                encoding="utf-8",
            )
            (src / "MiniCtl.ctx").write_bytes(b"opaque-binary")
            report = extract(src / "mini.vbp", out, src)
            self.assertIn("MiniCtl.ctl", report["copied"])
            self.assertIn("MiniCtl.ctx", report["copied"])
            self.assertEqual((out / "MiniCtl.ctx").read_bytes(), b"opaque-binary")
            self.assertEqual(report["missing"], [])
            saved = json.loads((out / "_extract_report.json").read_text(encoding="utf-8"))
            self.assertIn("MiniCtl.ctx", saved["copied"])


if __name__ == "__main__":
    unittest.main()
