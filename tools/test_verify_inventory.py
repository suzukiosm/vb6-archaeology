"""Unit tests for verify_inventory.count_ends (synthetic; no originals)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.vb6_inventory import parse_procedures
from tools.verify_inventory import count_ends


class CountEndsTests(unittest.TestCase):
    def _write(self, src: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Module1.bas"
            path.write_text(src, encoding="ascii")
            return count_ends(path)

    def test_line_start_end_sub(self) -> None:
        src = "Public Sub Alpha()\n    x = 1\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_end_after_colon_is_counted(self) -> None:
        src = "Public Sub Alpha()\n    x = 1: End Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_label_is_not_an_end(self) -> None:
        src = "Public Sub Alpha()\nFoo:\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_rem_end_is_not_counted(self) -> None:
        src = "Public Sub Alpha()\n    Rem End Sub\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_usual_two_procs_match_line_start_ends(self) -> None:
        src = (
            "Public Sub Alpha()\n"
            "    x = 1\n"
            "End Sub\n"
            "Private Function Beta() As Long\n"
            "    Beta = 1\n"
            "End Function\n"
        )
        self.assertEqual(self._write(src), 2)

    def test_colon_end_matches_parse_procedures(self) -> None:
        src = "Attribute VB_Name = \"M\"\nPublic Sub Alpha()\n    x = 1: End Sub\n"
        procs, _ = parse_procedures(src.splitlines())
        self.assertEqual(len(procs), 1)
        self.assertNotIn("unterminated", procs[0])
        self.assertEqual(self._write(src), len(procs))


if __name__ == "__main__":
    unittest.main()
