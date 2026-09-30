"""Shared designer parser: BeginProperty isolation, strings, .frx refs, data binding."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.frm_deep_read import extract_controls
from tools.lib.designer import parse_designer, parse_property_value
from tools.vb6_inventory import _parse_bytes

FRM = [
    "VERSION 5.00",
    "Begin VB.Form F",
    '   Caption         =   "Main ""Menu"""',
    "   ClientWidth     =   4800",
    "   Begin MSComctlLib.Toolbar Toolbar1",
    "      Width           =   4800",
    "      BeginProperty Buttons {66833FE8-8583-11D1-B16A-00C0F0283628}",
    "         NumButtons      =   1",
    "         BeginProperty Button1 {66833FEA-8583-11D1-B16A-00C0F0283628}",
    '            Caption         =   "Save"',
    "            Width           =   99",
    "         EndProperty",
    "      EndProperty",
    "   End",
    "   Begin VB.Data Data1",
    '      DatabaseName    =   "C:\\db\\main.mdb"',
    '      RecordSource    =   "SELECT * FROM Customer"',
    "   End",
    "   Begin VB.TextBox txtName",
    '      DataField       =   "NAME"',
    '      DataSource      =   "Data1"',
    "      Index           =   0",
    "      TabIndex        =   2",
    "   End",
    "   Begin VB.Label lblMemo",
    '      Caption         =   $"F.frx":0000',
    '      MouseIcon       =   "F.frx":0112',
    "      Alignment       =   1  'Right Justify",
    "   End",
    "End",
    'Attribute VB_Name = "F"',
    "Private Sub Form_Load()",
    "End Sub",
]


class DesignerParserTests(unittest.TestCase):
    def test_property_values(self) -> None:
        self.assertEqual(parse_property_value('"Say ""Hi"""'), ('Say "Hi"', None))
        self.assertEqual(parse_property_value("1  'Right Justify"), (1, None))
        self.assertEqual(parse_property_value("&H8000000F&"), ("&H8000000F&", None))
        self.assertEqual(parse_property_value('$"F.frx":0000'),
                         (None, {"file": "F.frx", "offset": "0000", "kind": "string"}))

    def test_tree_stops_at_code_section(self) -> None:
        nodes = parse_designer(FRM)
        self.assertEqual([(n["kind"], n["name"], n["depth"]) for n in nodes],
                         [("VB.Form", "F", 0), ("MSComctlLib.Toolbar", "Toolbar1", 1),
                          ("VB.Data", "Data1", 1), ("VB.TextBox", "txtName", 1), ("VB.Label", "lblMemo", 1)])
        blocks = nodes[1]["property_blocks"]
        self.assertEqual([(b["path"], b["props"]) for b in blocks],
                         [("Buttons", {"NumButtons": 1}),
                          ("Buttons/Button1", {"Caption": "Save", "Width": 99})])


class DeepReadControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.form, controls = extract_controls(FRM)
        self.by_name = {c["name"]: c for c in controls}

    def test_property_block_does_not_overwrite_control_values(self) -> None:
        bar = self.by_name["Toolbar1"]
        self.assertEqual((bar["caption"], bar["width"]), ("", 4800))
        self.assertEqual(bar["property_blocks"][1]["props"]["Caption"], "Save")

    def test_escaped_caption_and_frx_references(self) -> None:
        self.assertEqual(self.form["caption"], 'Main "Menu"')
        memo = self.by_name["lblMemo"]
        self.assertEqual(memo["caption"], "")
        self.assertEqual([(r["prop"], r["kind"]) for r in memo["frx_refs"]],
                         [("Caption", "string"), ("MouseIcon", "binary")])
        self.assertEqual(memo["props"]["Alignment"], 1)

    def test_data_binding_and_raw_props(self) -> None:
        self.assertEqual(self.by_name["Data1"]["data_binding"],
                         {"DatabaseName": "C:\\db\\main.mdb", "RecordSource": "SELECT * FROM Customer"})
        txt = self.by_name["txtName"]
        self.assertEqual(txt["data_binding"], {"DataSource": "Data1", "DataField": "NAME"})
        self.assertEqual((txt["index"], txt["props"]["TabIndex"]), (0, 2))


class InventoryDesignerTests(unittest.TestCase):
    def test_controls_have_parent_and_index_and_bindings_are_listed(self) -> None:
        info = _parse_bytes("\r\n".join(FRM).encode("cp932"), Path("F.frm"))
        self.assertEqual(info["form_kind"], "VB.Form")
        self.assertEqual([(c["name"], c["parent"], c.get("index")) for c in info["controls"]],
                         [("Toolbar1", "F", None), ("Data1", "F", None), ("txtName", "F", 0),
                          ("lblMemo", "F", None)])
        self.assertEqual(info["data_bindings"], [
            {"control": "Data1", "class": "VB.Data", "line": 15,
             "DatabaseName": "C:\\db\\main.mdb", "RecordSource": "SELECT * FROM Customer"},
            {"control": "txtName", "class": "VB.TextBox", "line": 19,
             "DataSource": "Data1", "DataField": "NAME"},
        ])


if __name__ == "__main__":
    unittest.main()
