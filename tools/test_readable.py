"""UTF-8 sidecar keeps physical lines; extract bytes stay untouched."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.readable import write_readable, write_utf8_lines


class ReadableSidecarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.extract = self.root / "extract"
        self.out = self.root / "readable"
        self.extract.mkdir()
        caption = 'Begin VB.Form Form1\r\n   Caption         =   "ミニ画面"\r\nEnd\r\n'
        self.frm = self.extract / "Form1.frm"
        self.frm.write_bytes(caption.encode("cp932"))
        (self.extract / "Form1.frx").write_bytes(b"\x00\x01binary")
        (self.extract / "_extract_report.json").write_text(
            '{"copied": ["Form1.frm"]}\n', encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_utf8_lines_match_and_japanese_survives(self) -> None:
        before = self.frm.read_bytes()
        report = write_readable(self.extract, self.out)
        self.assertTrue(report["ok"])
        self.assertEqual(self.frm.read_bytes(), before)
        dest = self.out / "Form1.frm"
        text = dest.read_text(encoding="utf-8")
        self.assertIn("ミニ画面", text)
        self.assertEqual(
            text.splitlines(),
            before.decode("cp932").splitlines(),
        )
        written = {row["file"]: row["lines"] for row in report["written"]}
        self.assertEqual(written["Form1.frm"], 3)
        skipped = {row["file"]: row["reason"] for row in report["skipped"]}
        self.assertEqual(skipped["Form1.frx"], "companion_binary")
        self.assertEqual(skipped["_extract_report.json"], "not_source_text")
        self.assertFalse((self.out / "Form1.frx").exists())

    def test_refuses_to_overwrite_extract(self) -> None:
        with self.assertRaises(SystemExit):
            write_readable(self.extract, self.extract)

    def test_write_utf8_lines_roundtrip(self) -> None:
        dest = self.root / "one.frm"
        lines = ['Caption = "別名画面"', "End"]
        write_utf8_lines(dest, lines)
        self.assertEqual(dest.read_text(encoding="utf-8").splitlines(), lines)
        self.assertTrue(dest.read_bytes().endswith(b"\n"))


class ReadableReportTests(unittest.TestCase):
    def test_report_json_is_utf8(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            extract = Path(tmp.name) / "ex"
            out = Path(tmp.name) / "out"
            extract.mkdir()
            (extract / "mini_vbp.vbp").write_bytes(
                'Name="mini_vbp"\r\n'.encode("cp932")
            )
            report = write_readable(extract, out)
            raw = (out / "_readable_report.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertEqual(data["ok"], True)
            self.assertEqual(data["written"][0]["file"], "mini_vbp.vbp")
            self.assertEqual(report["written"][0]["lines"], 1)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
