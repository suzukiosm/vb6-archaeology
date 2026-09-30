"""Shared VB6 file-statement rules: '#' is optional before a file number."""

from __future__ import annotations

import unittest

from tools.frm_deep_read import classify_goto_skip_stmt, find_goto_skipped_stmts
from tools.io_catalog import classify_io_statement, scan_source_text
from tools.lib.file_statements import file_statement_kind, is_file_statement
from tools.lib.vbparse import code_mask

ALL_KINDS = ("open", "line_input", "input", "print", "write", "get", "put", "close", "kill", "name")


def kind(stmt: str) -> str | None:
    return file_statement_kind(code_mask(stmt), ALL_KINDS)


class HashlessChannelTests(unittest.TestCase):
    def test_hashless_forms_are_file_statements(self) -> None:
        cases = {
            "Open sFile For Input As fnum": "open",
            "Open sFile For Random Access Read As fnum Len = 128": "open",
            "Open App.Path & \"\\x.dat\" For Binary As m.fh": "open",
            "Get fnum, , rec": "get",
            "Put 1, lPos, rec": "put",
            "Get arr(i), , rec": "get",
            "Close fnum": "close",
            "Close": "close",
            "If ok Then Get fnum, , rec": "get",
            "Line Input #fnum, s": "line_input",
            "Print #1, s": "print",
        }
        for stmt, want in cases.items():
            with self.subTest(stmt=stmt):
                self.assertEqual(kind(stmt), want)

    def test_methods_and_headers_are_not_file_statements(self) -> None:
        for stmt in (
            "rs.Open sql, cn, adOpenStatic",
            'cn.Open "Provider=Microsoft.Jet.OLEDB.4.0"',
            "rs.Close",
            ".Close",
            "Public Property Get Item(ByVal i As Long, j) As Variant",
            "Set f = fso.OpenTextFile(p)",
            'MsgBox "Open x For Input As y"',
            "x = Input(5, #1)",
        ):
            with self.subTest(stmt=stmt):
                self.assertIsNone(kind(stmt))

    def test_input_function_is_not_input_statement(self) -> None:
        self.assertFalse(is_file_statement(code_mask("s = Input(5, #1)"), "input"))


class ToolsShareTheRulesTests(unittest.TestCase):
    def test_io_catalog_finds_hashless_open_get_put(self) -> None:
        text = "Open sFile For Input As fnum\nGet fnum, , rec\nPut fnum, 1, rec\nClose fnum\n"
        self.assertEqual([e["kind"] for e in scan_source_text(text, "M.bas")],
                         ["open", "get", "put"])

    def test_io_catalog_contract_stays_five_kinds(self) -> None:
        self.assertIsNone(classify_io_statement("Close #1"))
        self.assertIsNone(classify_io_statement("Print #1, s"))

    def test_deep_read_skip_hint_uses_the_same_rules(self) -> None:
        self.assertEqual(classify_goto_skip_stmt("Get fnum, , rec"), "get_file")
        self.assertEqual(classify_goto_skip_stmt("Close fnum"), "close")
        self.assertIsNone(classify_goto_skip_stmt("rs.Close"))
        lines = ["Public Sub S()", "    GoTo Done", "    Open f For Input As fnum",
                 "Done:", "End Sub"]
        hits = find_goto_skipped_stmts(lines)
        self.assertEqual([(h["stmt_kind"], h["stmt_line"]) for h in hits], [("open", 3)])


if __name__ == "__main__":
    unittest.main()
