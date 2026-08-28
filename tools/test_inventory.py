"""Unit tests for vb6_inventory parsing (synthetic input; no originals)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vb6_inventory as inv  # noqa: E402
from lib.vbparse import iter_statements  # noqa: E402


def _stmt_end_count(lines: list[str]) -> int:
    return sum(
        1
        for st in iter_statements(lines)
        if st.kind == "stmt" and inv.END_RE.match(st.text.strip())
    )

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
        # Guards the verify_inventory invariant (statement-level End).
        end_count = _stmt_end_count(self.lines)
        self.assertEqual(end_count, len(self.procs))

    def test_end_after_colon_closes_procedure(self) -> None:
        src = """\
Attribute VB_Name = "M"
Public Sub Alpha()
    x = 1: End Sub
"""
        procs, _ = inv.parse_procedures(src.splitlines())
        self.assertEqual(len(procs), 1)
        self.assertEqual(procs[0]["name"], "Alpha")
        self.assertNotIn("unterminated", procs[0])
        self.assertEqual(procs[0]["line_start"], 2)
        self.assertEqual(procs[0]["line_end"], 3)
        self.assertEqual(_stmt_end_count(src.splitlines()), 1)

    def test_one_line_sub_with_colon(self) -> None:
        src = """\
Attribute VB_Name = "M"
Public Sub Alpha(): x = 1: End Sub
"""
        procs, _ = inv.parse_procedures(src.splitlines())
        self.assertEqual(len(procs), 1)
        self.assertEqual(procs[0]["line_start"], 2)
        self.assertEqual(procs[0]["line_end"], 2)
        self.assertEqual(procs[0]["lines"], 1)
        self.assertEqual(_stmt_end_count(src.splitlines()), 1)

    def test_label_is_not_a_procedure(self) -> None:
        src = """\
Attribute VB_Name = "M"
Public Sub Alpha()
Foo:
    x = 1
End Sub
"""
        procs, _ = inv.parse_procedures(src.splitlines())
        self.assertEqual([p["name"] for p in procs], ["Alpha"])
        self.assertEqual(_stmt_end_count(src.splitlines()), 1)

    def test_property_get_let_set_signatures(self) -> None:
        src = """\
Attribute VB_Name = "P"
Public Property Get Value() As Long
    Value = 1
End Property
Public Property Let Value(ByVal v As Long)
End Property
Friend Property Set Value(ByRef obj As Object)
End Property
"""
        procs, _ = inv.parse_procedures(src.splitlines())
        by_kind = {p["kind"]: p for p in procs}
        self.assertEqual(set(by_kind), {"Property Get", "Property Let", "Property Set"})
        self.assertEqual(by_kind["Property Get"]["params"], "")
        self.assertEqual(by_kind["Property Get"]["returns"], "Long")
        self.assertEqual(by_kind["Property Get"]["visibility"], "Public")
        self.assertEqual(by_kind["Property Let"]["params"], "ByVal v As Long")
        self.assertIsNone(by_kind["Property Let"]["returns"])
        self.assertEqual(by_kind["Property Set"]["params"], "ByRef obj As Object")
        self.assertEqual(by_kind["Property Set"]["visibility"], "Friend")
        self.assertIsNone(by_kind["Property Set"]["returns"])


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
        self.assertEqual(_stmt_end_count(DECL_BAS.splitlines()), len(procs))
        self.assertEqual(len(procs), 1)

    def test_colon_separated_module_consts(self) -> None:
        src = """\
Attribute VB_Name = "M"
Public Const A = 1: Private Const B = 2
Public Sub Alpha(): Const LocalOnly = 5: End Sub
"""
        d = inv.parse_declarations(src.splitlines())
        names = [c["name"] for c in d["consts"]]
        self.assertEqual(names, ["A", "B"])
        self.assertNotIn("LocalOnly", names)
        procs, _ = inv.parse_procedures(src.splitlines())
        self.assertEqual(len(procs), 1)
        self.assertEqual(_stmt_end_count(src.splitlines()), 1)


class ParserVersionTests(unittest.TestCase):
    def test_parser_version_is_inv10(self) -> None:
        self.assertEqual(inv.PARSER_VERSION, "inv-10")


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
        self.assertEqual(got["user_controls"], [])
        self.assertEqual(got["objects"][0]["file"], "ComDlg32.OCX")
        self.assertEqual(got["meta"]["MajorVer"], "1")
        self.assertEqual(got["meta"]["HelpFile"], "proj.hlp")
        self.assertEqual(got["meta"]["Command32"], "/silent")
        self.assertEqual(got["meta"]["Type"], "Exe")
        self.assertEqual(got["meta"]["CondComp"], "")
        self.assertEqual(got["meta"]["CompatibleMode"], "")
        self.assertEqual(got["meta"]["CompilationType"], "")
        self.assertEqual(got["meta"]["CompatibleEXE32"], "")
        self.assertEqual(got["meta"]["AutoIncrementVer"], "")

    def test_skip_parent_common(self) -> None:
        vbp = """\
Form=Form1.frm
Form=..\\..\\shared\\Shared.frm
Module=Shared; ..\\..\\common\\Shared.bas
Class=Local; Local.cls
Class=Remote; ..\\..\\common\\Remote.cls
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            kept = inv.parse_vbp(path, skip_parent_common=False)
            skipped = inv.parse_vbp(path, skip_parent_common=True)
        self.assertEqual(len(kept["forms"]), 2)
        self.assertEqual(len(kept["modules"]), 1)
        self.assertEqual(len(kept["classes"]), 2)
        self.assertEqual(skipped["forms"], ["Form1.frm"])
        self.assertEqual(skipped["modules"], [])
        self.assertEqual(skipped["classes"][0]["file"], "Local.cls")
        skipped_files = {s["file"] for s in skipped["skipped_parent_common"]}
        self.assertEqual(
            skipped_files,
            {
                "..\\..\\shared\\Shared.frm",
                "..\\..\\common\\Shared.bas",
                "..\\..\\common\\Remote.cls",
            },
        )

    def test_module_class_without_path_warned(self) -> None:
        vbp = """\
Form=
Module=Orphan
Class=Bare;
Module=Ok; Ok.bas
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            got = inv.parse_vbp(path)
        self.assertEqual(got["forms"], [])
        self.assertEqual(got["modules"], [{"module": "Ok", "file": "Ok.bas"}])
        self.assertEqual(got["classes"], [])
        reasons = {(w["kind"], w["reason"], w.get("ident")) for w in got["warnings"]}
        self.assertIn(("form", "missing_path", None), reasons)
        self.assertIn(("module", "missing_path", "Orphan"), reasons)
        self.assertIn(("class", "missing_path", "Bare"), reasons)

    def test_extra_file_keys(self) -> None:
        vbp = """\
Form=Form1.frm
UserControl=MiniCtl; MiniCtl.ctl
PropertyPage=PP1; PP1.pag
UserDocument=Doc1.dob
Designer=D1; D1.dsr
RelatedDoc=notes.txt
ResFile32="app.res"
UserControl=Orphan;
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            got = inv.parse_vbp(path)
        self.assertEqual(got["user_controls"], [{"ident": "MiniCtl", "file": "MiniCtl.ctl"}])
        self.assertEqual(got["property_pages"], [{"ident": "PP1", "file": "PP1.pag"}])
        self.assertEqual(got["user_documents"], [{"ident": "Doc1", "file": "Doc1.dob"}])
        self.assertEqual(got["designers"], [{"ident": "D1", "file": "D1.dsr"}])
        self.assertEqual(got["related_docs"], [{"file": "notes.txt"}])
        self.assertEqual(got["res_files"], [{"file": "app.res"}])
        reasons = {(w["kind"], w["reason"], w.get("ident")) for w in got["warnings"]}
        self.assertIn(("usercontrol", "missing_path", "Orphan"), reasons)

    def test_skip_parent_common_usercontrol(self) -> None:
        vbp = """\
UserControl=Local; Local.ctl
UserControl=Remote; ..\\..\\common\\Remote.ctl
RelatedDoc=..\\..\\docs\\notes.txt
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proj.vbp"
            path.write_bytes(vbp.encode("cp932"))
            skipped = inv.parse_vbp(path, skip_parent_common=True)
        self.assertEqual(skipped["user_controls"], [{"ident": "Local", "file": "Local.ctl"}])
        self.assertEqual(skipped["related_docs"], [])
        skipped_files = {s["file"] for s in skipped["skipped_parent_common"]}
        self.assertEqual(
            skipped_files,
            {"..\\..\\common\\Remote.ctl", "..\\..\\docs\\notes.txt"},
        )

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

    def test_compile_meta_empty_and_present(self) -> None:
        empty = "Type=Exe\nForm=Form1.frm\nCondComp=\nCompatibleMode=\nCompilationType=\n"
        full = """\
Type=OleDll
CondComp="FOO = 1"
CompatibleMode=1
CompilationType=0
CompatibleEXE32="proj.dll"
AutoIncrementVer=0
UnknownKey=drop
"""
        with tempfile.TemporaryDirectory() as td:
            empty_path = Path(td) / "empty.vbp"
            empty_path.write_bytes(empty.encode("cp932"))
            empty_got = inv.parse_vbp(empty_path)
            full_path = Path(td) / "full.vbp"
            full_path.write_bytes(full.encode("cp932"))
            full_got = inv.parse_vbp(full_path)
        for key in (
            "Type",
            "CondComp",
            "CompatibleMode",
            "CompilationType",
            "CompatibleEXE32",
            "AutoIncrementVer",
        ):
            self.assertIn(key, empty_got["meta"])
            self.assertIn(key, full_got["meta"])
        self.assertEqual(empty_got["meta"]["Type"], "Exe")
        self.assertEqual(empty_got["meta"]["CondComp"], "")
        self.assertEqual(empty_got["meta"]["CompatibleMode"], "")
        self.assertEqual(empty_got["meta"]["CompilationType"], "")
        self.assertEqual(full_got["meta"]["Type"], "OleDll")
        self.assertEqual(full_got["meta"]["CondComp"], "FOO = 1")
        self.assertEqual(full_got["meta"]["CompatibleMode"], "1")
        self.assertEqual(full_got["meta"]["CompilationType"], "0")
        self.assertEqual(full_got["meta"]["CompatibleEXE32"], "proj.dll")
        self.assertEqual(full_got["meta"]["AutoIncrementVer"], "0")
        self.assertNotIn("UnknownKey", full_got["meta"])
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "inv.md"
            inv.write_markdown(
                {
                    "vbp": "t.vbp",
                    "meta": {},
                    "file_count": 0,
                    "proc_total": 0,
                    "objects": [],
                    "missing_in_extract": [],
                    "not_in_vbp": [],
                    "files": [],
                },
                out,
            )
            md = out.read_text(encoding="utf-8")
        self.assertIn("Type:", md)
        self.assertIn("CondComp:", md)


class ShowFactsTests(unittest.TestCase):
    def test_mdi_child_and_vbmodal_outbound(self) -> None:
        src = """\
VERSION 5.00
Begin VB.Form Form12
   Caption         =   "x"
   MDIChild        =   -1  'True
End
Attribute VB_Name = "Form12"
Private Sub Command1_Click()
    Form1.Show vbModal
End Sub
"""
        facts = inv.scan_form_show_facts(src.splitlines(), "VB.Form")
        self.assertTrue(facts["mdi_child"])
        self.assertEqual(facts["self"]["show_style"], "mdi_child")
        self.assertEqual(len(facts["outbound"]), 1)
        self.assertEqual(facts["outbound"][0]["target"], "Form1")
        self.assertEqual(facts["outbound"][0]["show_style"], "modal_overlay")

    def test_inventory_file_includes_show_fields(self) -> None:
        frm = """\
VERSION 5.00
Begin VB.Form Form1
   Caption = "F"
End
Attribute VB_Name = "Form1"
Private Sub Command1_Click()
    Form12.Show vbModal
End Sub
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Form1.frm"
            path.write_bytes(frm.encode("cp932"))
            info = inv.inventory_file(path, use_cache=False)
        self.assertEqual(info["show_style"]["show_style"], "unknown")
        self.assertEqual(info["show_calls"][0]["show_style"], "modal_overlay")
        self.assertEqual(info.get("lifetime_calls"), [])
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "inv.md"
            inv.write_markdown(
                {
                    "vbp": "t.vbp",
                    "meta": {},
                    "file_count": 1,
                    "proc_total": 1,
                    "objects": [],
                    "missing_in_extract": [],
                    "not_in_vbp": [],
                    "files": [{**info, "type": "form"}],
                },
                out,
            )
            md = out.read_text(encoding="utf-8")
            self.assertIn("show_style / Show 文", md)
            self.assertIn("Show 文の転置（事実）", md)
            self.assertIn("modal_overlay", md)

    def test_lifetime_calls_in_json(self) -> None:
        frm = """\
VERSION 5.00
Begin VB.Form Form1
   Caption = "F"
End
Attribute VB_Name = "Form1"
Private Sub Command1_Click()
    Load Form2
    Unload Me
    Me.Show
    Show vbModal
End Sub
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Form1.frm"
            path.write_bytes(frm.encode("cp932"))
            info = inv.inventory_file(path, use_cache=False)
        kinds = [c["kind"] for c in info["lifetime_calls"]]
        targets = [c["target"] for c in info["lifetime_calls"]]
        self.assertEqual(kinds, ["load", "unload"])
        self.assertEqual(targets, ["Form2", "Me"])
        show_targets = [c["target"] for c in info["show_calls"]]
        self.assertIn("Me", show_targets)
        self.assertIn("", show_targets)

    def test_colon_line_splits_show_and_lifetime(self) -> None:
        src = """\
VERSION 5.00
Begin VB.Form Form1
   Caption = "F"
End
Attribute VB_Name = "Form1"
Private Sub Command1_Click()
    If Err Then Unload Me: Form12.Show vbModal
End Sub
"""
        facts = inv.scan_form_show_facts(src.splitlines(), "VB.Form")
        self.assertEqual(facts["lifetime"][0]["kind"], "unload")
        self.assertEqual(facts["lifetime"][0]["target"], "Me")
        self.assertEqual(facts["outbound"][0]["target"], "Form12")
        self.assertEqual(facts["outbound"][0]["show_style"], "modal_overlay")


class ParseSurfaceTests(unittest.TestCase):
    def test_implements_withevents_instancing_and_attrs(self) -> None:
        src = """\
VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
  Instancing = 5
END
Attribute VB_Name = "Widget"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_Exposed = False
Option Explicit

Implements IPing

Private WithEvents Bus As AppEvents

Public Property Get Ready() As Boolean
    Ready = True
End Property

Public Sub Ping()
End Sub
"""
        surf = inv.parse_surface(src.splitlines())
        self.assertEqual(surf["instancing"], 5)
        self.assertTrue(surf["vb_creatable"])
        self.assertFalse(surf["vb_exposed"])
        self.assertFalse(surf["vb_global_name_space"])
        self.assertIsNone(surf["vb_predeclared_id"])
        self.assertIsNone(surf["vb_user_mem_id"])
        self.assertEqual([i["name"] for i in surf["implements"]], ["IPing"])
        self.assertEqual(surf["with_events"][0]["name"], "Bus")
        self.assertEqual(surf["with_events"][0]["as_type"], "AppEvents")
        self.assertEqual(surf["with_events"][0]["visibility"], "Private")
        self.assertGreater(surf["implements"][0]["line"], 0)
        self.assertGreater(surf["with_events"][0]["line"], 0)
        procs, _ = inv.parse_procedures(src.splitlines())
        self.assertEqual(inv.public_property_count(procs), 1)

    def test_form_predeclared_id_true_and_user_mem_id_null(self) -> None:
        src = """\
VERSION 5.00
Begin VB.Form Form1
   Caption         =   "x"
End
Attribute VB_Name = "Form1"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
"""
        surf = inv.parse_surface(src.splitlines())
        self.assertTrue(surf["vb_predeclared_id"])
        self.assertIsNone(surf["vb_user_mem_id"])

    def test_class_predeclared_id_false_and_user_mem_id(self) -> None:
        src = """\
VERSION 1.0 CLASS
BEGIN
  Instancing = 5
END
Attribute VB_Name = "Widget"
Attribute VB_PredeclaredId = False
Attribute VB_UserMemId = 0
"""
        surf = inv.parse_surface(src.splitlines())
        self.assertFalse(surf["vb_predeclared_id"])
        self.assertEqual(surf["vb_user_mem_id"], 0)

    def test_withevents_inside_proc_is_ignored(self) -> None:
        src = """\
Attribute VB_Name = "M"
Public Sub Alpha()
    Dim WithEvents x As AppEvents
End Sub
"""
        surf = inv.parse_surface(src.splitlines())
        self.assertEqual(surf["with_events"], [])
        self.assertEqual(surf["implements"], [])

    def test_markdown_lists_surface_for_class(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Widget.cls"
            path.write_bytes(
                (
                    "VERSION 1.0 CLASS\nBEGIN\n  Instancing = 2\nEND\n"
                    'Attribute VB_Name = "Widget"\n'
                    "Implements IFoo\n"
                    "Public Sub Ping()\nEnd Sub\n"
                ).encode("cp932")
            )
            info = inv.inventory_file(path, use_cache=False)
            out = Path(td) / "inv.md"
            inv.write_markdown(
                {
                    "vbp": "t.vbp",
                    "meta": {},
                    "file_count": 1,
                    "proc_total": 1,
                    "objects": [],
                    "missing_in_extract": [],
                    "not_in_vbp": [],
                    "files": [{**info, "type": "class"}],
                },
                out,
            )
            md = out.read_text(encoding="utf-8")
            html_path = Path(td) / "inv.html"
            inv.write_html(
                {
                    "vbp": "t.vbp",
                    "stem": "t",
                    "meta": {},
                    "file_count": 1,
                    "proc_total": 1,
                    "objects": [],
                    "missing_in_extract": [],
                    "not_in_vbp": [],
                    "files": [{**info, "type": "class"}],
                },
                html_path,
            )
            html = html_path.read_text(encoding="utf-8")
        self.assertIn("Implements / WithEvents / Instancing", md)
        self.assertIn("`IFoo`", md)
        self.assertIn("Instancing: `2`", md)
        self.assertIn("Implements / WithEvents / Instancing", html)
        self.assertIn("IFoo", html)


if __name__ == "__main__":
    unittest.main()
