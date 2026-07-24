"""Unit tests for vb6_inventory parsing (synthetic input; no originals)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vb6_inventory as inv  # noqa: E402

BAS = """\
Attribute VB_Name = "M"
Option Explicit

Private Declare Function GetTick Lib "kernel32" _
    Alias "GetTickCount" () As Long

Public Sub Alpha()
    Dim x As Long
End Sub

Private Function Beta(ByVal n As Long) As Long
    Beta = n + 1
End Function
"""


class ParseProceduresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = BAS.splitlines()
        self.procs, self.declares = inv.parse_procedures(self.lines)

    def test_two_procedures_detected(self) -> None:
        names = [p["name"] for p in self.procs]
        self.assertEqual(names, ["Alpha", "Beta"])

    def test_physical_line_numbers_are_stable(self) -> None:
        alpha = self.procs[0]
        # Alpha starts at physical line 7 (1-based) in BAS above.
        self.assertEqual(alpha["line_start"], 7)
        self.assertEqual(alpha["kind"], "Sub")
        self.assertEqual(alpha["visibility"], "Public")

    def test_multiline_declare_captures_full_lib(self) -> None:
        self.assertEqual(len(self.declares), 1)
        d = self.declares[0]
        self.assertEqual(d["name"], "GetTick")
        self.assertEqual(d["lib"], "kernel32")
        self.assertEqual(d["line"], 4)  # physical start line of the Declare
        self.assertEqual(d["visibility"], "Private")

    def test_end_count_matches_proc_count(self) -> None:
        # Guards the verify_inventory invariant.
        end_count = sum(1 for ln in self.lines if inv.END_RE.match(ln.strip()))
        self.assertEqual(end_count, len(self.procs))


class DecodeTests(unittest.TestCase):
    def test_cp932_roundtrip(self) -> None:
        raw = "Attribute VB_Name = \"日本語\"\nPublic Sub A()\nEnd Sub\n".encode("cp932")
        text = inv.decode(raw)
        self.assertIn("日本語", text)


if __name__ == "__main__":
    unittest.main()
