"""Unit tests for vb6_inventory parsing (synthetic input; no originals)."""

from __future__ import annotations

import sys
import tempfile
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

    def test_signature_params_and_returns(self) -> None:
        alpha, beta = self.procs
        self.assertEqual(alpha["params"], "")
        self.assertIsNone(alpha["returns"])
        self.assertEqual(beta["params"], "ByVal n As Long")
        self.assertEqual(beta["returns"], "Long")

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


class ParseVbpTests(unittest.TestCase):
    def test_class_object_and_meta(self) -> None:
        vbp = """\
Type=Exe
Form=Form1.frm
Module=Module1; Module1.bas
Class=Widget; Widget.cls
Object={F9043C88-F6F2-101A-A3C9-08002B2F49FB}#1.2#0; ComDlg32.OCX
Startup="Form1"
Name="proj"
MajorVer=1
MinorVer=2
RevisionVer=3
Command32="/silent"
HELPFILE="proj.hlp"
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            got = inv.parse_vbp(path)
        self.assertEqual(got["forms"], ["Form1.frm"])
        self.assertEqual(got["modules"][0]["file"], "Module1.bas")
        self.assertEqual(got["classes"], [{"class": "Widget", "file": "Widget.cls"}])
        self.assertEqual(got["objects"][0]["file"], "ComDlg32.OCX")
        self.assertEqual(got["meta"]["MajorVer"], "1")
        self.assertEqual(got["meta"]["HelpFile"], "proj.hlp")
        self.assertEqual(got["meta"]["Command32"], "/silent")

    def test_skip_parent_common(self) -> None:
        vbp = """\
Form=Form1.frm
Module=Shared; ..\\..\\common\\Shared.bas
Class=Local; Local.cls
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            kept = inv.parse_vbp(path, skip_parent_common=False)
            skipped = inv.parse_vbp(path, skip_parent_common=True)
        self.assertEqual(len(kept["modules"]), 1)
        self.assertEqual(skipped["modules"], [])
        self.assertEqual(skipped["classes"][0]["file"], "Local.cls")
        self.assertEqual(skipped["skipped_parent_common"][0]["file"], "..\\..\\common\\Shared.bas")

    def test_array_param_parens(self) -> None:
        params, ret = inv.extract_params_returns("(ByRef a() As Long) As Boolean")
        self.assertEqual(params, "ByRef a() As Long")
        self.assertEqual(ret, "Boolean")

    def test_return_strips_inline_comment(self) -> None:
        params, ret = inv.extract_params_returns("() As Long  'returns a long")
        self.assertEqual(params, "")
        self.assertEqual(ret, "Long")

    def test_object_without_semicolon_has_null_file(self) -> None:
        vbp = "Object={12345}#1.0#0\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            got = inv.parse_vbp(path)
        self.assertIsNone(got["objects"][0]["file"])
        self.assertIn("{12345}", got["objects"][0]["raw"])


if __name__ == "__main__":
    unittest.main()
