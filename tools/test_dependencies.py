"""External dependencies as facts: Reference=, Declare Alias/params, per-form OCX."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.vb6_inventory import _parse_bytes, parse_reference, parse_vbp, write_markdown

ADO = (r"*\G{2A75196C-D9EB-4129-B803-931327F72D5C}#2.8#0#C:\Program Files\Common Files"
       r"\System\ado\msado15.dll#Microsoft ActiveX Data Objects 2.8 Library")


class ReferenceTests(unittest.TestCase):
    def test_typelib_reference_fields(self) -> None:
        ref = parse_reference(ADO)
        self.assertEqual(
            {k: ref[k] for k in ("kind", "guid", "version", "lcid", "description")},
            {"kind": "typelib", "guid": "{2A75196C-D9EB-4129-B803-931327F72D5C}",
             "version": "2.8", "lcid": "0", "description": "Microsoft ActiveX Data Objects 2.8 Library"},
        )
        self.assertTrue(ref["path"].endswith(r"ado\msado15.dll"))

    def test_project_reference(self) -> None:
        self.assertEqual(parse_reference(r"*\A..\Shared\Shared.vbp"),
                         {"kind": "project", "path": r"..\Shared\Shared.vbp", "raw": r"*\A..\Shared\Shared.vbp"})

    def test_vbp_lists_references_and_object_guid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vbp = Path(tmp) / "P.vbp"
            vbp.write_text(
                "Type=Exe\r\nReference=" + ADO + "\r\n"
                "Object={831FDD16-0C5C-11D2-A9FC-0000F8754DA1}#2.0#0; MSCOMCTL.OCX\r\n",
                encoding="cp932",
            )
            got = parse_vbp(vbp)
        self.assertEqual([r["description"] for r in got["references"]],
                         ["Microsoft ActiveX Data Objects 2.8 Library"])
        obj = got["objects"][0]
        self.assertEqual((obj["guid"], obj["version"], obj["file"]),
                         ("{831FDD16-0C5C-11D2-A9FC-0000F8754DA1}", "2.0", "MSCOMCTL.OCX"))


class DeclareTests(unittest.TestCase):
    def test_alias_params_and_return(self) -> None:
        info = _parse_bytes((
            'Attribute VB_Name = "M"\r\n'
            'Private Declare Function GetPrivateProfileString Lib "kernel32" _\r\n'
            '    Alias "GetPrivateProfileStringA" (ByVal lpApp As String, lpKey As Any, _\r\n'
            '    ByVal nSize As Long) As Long\r\n'
            'Public Declare Sub Sleep Lib "kernel32" (ByVal ms As Long)\r\n'
        ).encode("cp932"), Path("M.bas"))
        gpps, sleep = info["declares"]
        self.assertEqual((gpps["lib"], gpps["alias"], gpps["returns"], gpps["line"]),
                         ("kernel32", "GetPrivateProfileStringA", "Long", 2))
        self.assertEqual([(p["name"], p["passing"], p["type"]) for p in gpps["params_detail"]],
                         [("lpApp", "ByVal", "String"), ("lpKey", "ByRef", "Any"), ("nSize", "ByVal", "Long")])
        self.assertEqual(gpps["return_type"], "Long")
        self.assertEqual((sleep["alias"], sleep["params"]), (None, "ByVal ms As Long"))
        self.assertNotIn("return_type", sleep)


class DesignerDependencyTests(unittest.TestCase):
    FRM = (
        "VERSION 5.00\r\n"
        'Object = "{831FDD16-0C5C-11D2-A9FC-0000F8754DA1}#2.0#0"; "MSCOMCTL.OCX"\r\n'
        'Object = "{F9043C88-F6F2-101A-A3C9-08002B2F49FB}#1.2#0"; "COMDLG32.OCX"\r\n'
        "Begin VB.Form F\r\n"
        "   Begin MSComctlLib.ListView lv1\r\n   End\r\n"
        "   Begin MSComctlLib.ListView lv2\r\n   End\r\n"
        "   Begin MSComDlg.CommonDialog cd\r\n   End\r\n"
        "   Begin VB.CommandButton cmd\r\n   End\r\n"
        "End\r\n"
        'Attribute VB_Name = "F"\r\n'
    )

    def test_form_objects_and_external_controls(self) -> None:
        info = _parse_bytes(self.FRM.encode("cp932"), Path("F.frm"))
        self.assertEqual([(o["file"], o["version"], o["line"]) for o in info["ocx_objects"]],
                         [("MSCOMCTL.OCX", "2.0", 2), ("COMDLG32.OCX", "1.2", 3)])
        self.assertEqual(info["external_control_classes"],
                         [{"class": "MSComDlg.CommonDialog", "count": 1},
                          {"class": "MSComctlLib.ListView", "count": 2}])

    def test_markdown_shows_references_and_components(self) -> None:
        info = _parse_bytes(self.FRM.encode("cp932"), Path("F.frm"))
        report = {"vbp": "t.vbp", "meta": {}, "file_count": 1, "proc_total": 0, "objects": [],
                  "references": [parse_reference(ADO)], "missing_in_extract": [],
                  "not_in_vbp": [], "files": [{**info, "type": "form"}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "inv.md"
            write_markdown(report, out)
            md = out.read_text(encoding="utf-8")
        self.assertIn("Microsoft ActiveX Data Objects 2.8 Library（msado15.dll 2.8）", md)
        self.assertIn("外部コンポーネント: OCX MSCOMCTL.OCX（L2）", md)
        self.assertIn("MSComctlLib.ListView×2", md)


if __name__ == "__main__":
    unittest.main()
