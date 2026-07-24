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


DECL_BAS = """\
Attribute VB_Name = "M"
Option Explicit

Public Const MaxRows = 100
Private Const Tag = "x"

Public Enum Color
    Red = 0
    Green = 1
    Blue = 2
End Enum

Private Type Point
    X As Long
    Y As Long
End Type

Public Event Changed(ByVal id As Long)

Public Sub Alpha()
    Const LocalOnly = 5
    Dim p As Point
End Sub
"""


class ParseDeclarationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.d = inv.parse_declarations(DECL_BAS.splitlines())

    def test_module_consts_only_excludes_locals(self) -> None:
        names = [c["name"] for c in self.d["consts"]]
        self.assertIn("MaxRows", names)
        self.assertIn("Tag", names)
        self.assertNotIn("LocalOnly", names)  # local const inside Alpha excluded

    def test_enum_members(self) -> None:
        self.assertEqual(len(self.d["enums"]), 1)
        en = self.d["enums"][0]
        self.assertEqual(en["name"], "Color")
        self.assertEqual([m["name"] for m in en["members"]], ["Red", "Green", "Blue"])

    def test_type_fields(self) -> None:
        self.assertEqual(len(self.d["types"]), 1)
        t = self.d["types"][0]
        self.assertEqual(t["name"], "Point")
        self.assertEqual([f["name"] for f in t["fields"]], ["X", "Y"])

    def test_event(self) -> None:
        self.assertEqual(len(self.d["events"]), 1)
        self.assertEqual(self.d["events"][0]["name"], "Changed")

    def test_declarations_do_not_add_end_sub(self) -> None:
        # Enum/Type close with End Enum / End Type, not END_RE — invariant holds.
        procs, _ = inv.parse_procedures(DECL_BAS.splitlines())
        end_count = sum(1 for ln in DECL_BAS.splitlines() if inv.END_RE.match(ln.strip()))
        self.assertEqual(end_count, len(procs))
        self.assertEqual(len(procs), 1)


class DecodeTests(unittest.TestCase):
    def test_cp932_roundtrip(self) -> None:
        raw = "Attribute VB_Name = \"日本語\"\nPublic Sub A()\nEnd Sub\n".encode("cp932")
        text = inv.decode(raw)
        self.assertIn("日本語", text)


if __name__ == "__main__":
    unittest.main()
