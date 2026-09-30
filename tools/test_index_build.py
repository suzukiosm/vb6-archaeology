"""AI index: scope-rule candidates, effects, chunks, schema conformance (synthetic VB6)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.index_build import build_index, estimate_tokens, sha256_text, write_index
from tools.lib.config_schema import validate
from tools.vb6_inventory import build_report

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "schema" / "index.schema.json")
                    .read_text(encoding="utf-8"))

SOURCES = {
    "P.vbp": "Type=Exe\nForm=Form1.frm\nForm=Form2.frm\nModule=Main; Main.bas\nClass=Widget; Widget.cls\n"
             'Startup="Sub Main"\n',
    "Main.bas": """\
Attribute VB_Name = "Main"
Public Const MAX_ROWS = 10
Public gCount As Long
Private Declare Function GetTickCount Lib "kernel32" () As Long
Public Enum Mode
    ModeRead = 0
End Enum
Public Sub Boot()
    Dim cn As Object
    Set cn = CreateObject("ADODB.Connection")
    cn.Execute "SELECT * FROM T WHERE id = 1"
    gCount = GetTickCount
    Form1.Show
    SaveSetting "App", "S", "K", "v"
    Shell "notepad.exe", vbNormalFocus
End Sub
Public Function Twice(x) As Long
    Twice = x * 2
End Function
""",
    "Form1.frm": """\
VERSION 5.00
Begin VB.Form Form1
   Begin VB.CommandButton cmdGo
   End
End
Attribute VB_Name = "Form1"
Private m As Widget
Private Sub cmdGo_Click()
    On Error Resume Next
    Boot
    m.Ping 1
    Form2.Refresh2
    Form2.Hidden
    Call Twice(MAX_ROWS)
    With m
        .Ping 2
    End With
    Dim r As New ADODB.Recordset
    MsgBox ModeRead
End Sub
Public Sub Refresh2()
End Sub
""",
    "Form2.frm": """\
VERSION 5.00
Begin VB.Form Form2
End
Attribute VB_Name = "Form2"
Option Explicit
Public Sub Refresh2()
End Sub
Private Sub Hidden()
End Sub
""",
    "Widget.cls": """\
VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "Widget"
Public Function Ping(ByVal n As Long) As Long
    Ping = n
End Function
""",
}


class IndexBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        for name, text in SOURCES.items():
            (cls.root / name).write_bytes(text.encode("cp932"))
        cls.inventory = build_report(cls.root, cls.root / "P.vbp", use_cache=False)
        cls.data = build_index(cls.inventory, cls.root)
        cls.occ = cls.data["occurrences"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def uses(self, name: str, file: str = "Form1.frm") -> list[dict]:
        return [o for o in self.occ if o["name"] == name and o["file"] == file]

    def test_unqualified_names_resolve_by_scope(self) -> None:
        boot = self.uses("Boot")[0]
        self.assertEqual((boot["candidates"], boot["basis"], boot["context"]),
                         (["Main.bas#Sub:Boot"], "global", "head"))
        self.assertEqual(self.uses("Twice")[0]["context"], "call")
        self.assertEqual(self.uses("MAX_ROWS")[0]["candidates"], ["Main.bas#Const:MAX_ROWS"])
        self.assertEqual(self.uses("ModeRead")[0]["candidates"], ["Main.bas#Enum:Mode.ModeRead"])

    def test_form_qualified_member_picks_that_form_not_the_caller(self) -> None:
        refresh = self.uses("Refresh2")
        self.assertEqual([(o["candidates"], o["basis"], o["qualifier"]) for o in refresh],
                         [(["Form2.frm#Sub:Refresh2"], "qualified", "Form2")])

    def test_private_member_is_not_visible_through_the_form(self) -> None:
        self.assertEqual(self.uses("Hidden"), [])

    def test_typed_module_variable_and_with_block(self) -> None:
        pings = self.uses("Ping")
        self.assertEqual([(o["line"], o["candidates"], o["basis"]) for o in pings],
                         [(11, ["Widget.cls#Function:Ping"], "typed_variable")])

    def test_function_result_assignment_is_not_a_call(self) -> None:
        twice = self.uses("Twice", "Main.bas")
        self.assertEqual([o["context"] for o in twice], ["function_result"])

    def test_effects_are_facts_with_detail(self) -> None:
        boot = {(e["kind"], e.get("progid") or e.get("method") or e.get("declare") or e.get("call")
                 or e.get("target") or e.get("sql"))
                for e in self.data["effects"] if e["in"] == "Main.bas#Sub:Boot"}
        self.assertTrue({("com.create", "ADODB.Connection"), ("db.method", "Execute"),
                         ("sql.literal", "SELECT * FROM T WHERE id = 1"), ("api.call", "GetTickCount"),
                         ("ui.show", "Form1"), ("registry", "SaveSetting"),
                         ("process.shell", None)} <= boot, boot)
        click = {e["kind"] for e in self.data["effects"] if e["in"] == "Form1.frm#Sub:cmdGo_Click"}
        self.assertTrue({"com.new", "ui.msgbox"} <= click, click)
        self.assertFalse([e for e in self.data["effects"] if e["kind"] == "api.call" and e["line"] == 4])

    def test_chunks_carry_code_notes_and_refs(self) -> None:
        chunks = {c["id"]: c for c in self.data["chunks"]}
        click = chunks["chunk:Form1.frm#Sub:cmdGo_Click"]
        self.assertTrue(click["code"].startswith("8| Private Sub cmdGo_Click()"))
        self.assertEqual(click["sha256"], sha256_text(click["code"]))
        self.assertEqual(click["tokens_est"], estimate_tokens(click["header"] + click["code"]))
        self.assertIn("event cmdGo.Click [designer]", click["header"])
        self.assertTrue(any("On Error Resume Next" in n for n in click["notes"]))
        self.assertTrue(any("Option Explicit なし" in n for n in click["notes"]))
        self.assertIn("Form2.frm#Sub:Refresh2", click["refs"])
        twice = chunks["chunk:Main.bas#Function:Twice"]
        self.assertTrue(any(n.startswith("ByRef（省略時）の引数: x") for n in twice["notes"]))
        self.assertIn("chunk:Main.bas#declarations", chunks)
        self.assertIn("chunk:Form1.frm#designer", chunks)

    def test_every_record_matches_the_schema(self) -> None:
        defs = SCHEMA["$defs"]
        problems = validate(self.data["manifest"], defs["manifest"], "manifest")
        for name, key in (("symbols", "symbol"), ("occurrences", "occurrence"),
                          ("effects", "effect"), ("chunks", "chunk")):
            for i, record in enumerate(self.data[name]):
                problems += validate(record, defs[key], f"{name}[{i}]")
        self.assertEqual(problems, [])

    def test_output_is_deterministic_jsonl(self) -> None:
        again = build_index(self.inventory, self.root)
        self.assertEqual(again, self.data)
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_index(self.data, Path(tmp))
            lines = paths["symbols"].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), self.data["manifest"]["counts"]["symbols"])
        self.assertTrue(all(json.loads(line)["id"] for line in lines))


if __name__ == "__main__":
    unittest.main()
