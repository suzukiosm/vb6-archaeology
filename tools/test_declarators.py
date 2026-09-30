"""Module variables, Option / Deftype and structured parameters (synthetic VB6)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.lib.declarators import deftype_letters, parse_deftype, parse_params, parse_var_declarators
from tools.vb6_inventory import _parse_bytes

MODULE = """\
Attribute VB_Name = "M"
Option Explicit
Option Base 1
Option Compare Text
DefInt I-N
DefStr S
Global gUser As String
Public gConn As New ADODB.Connection
Private WithEvents Bus As AppEvents
Dim a, b As Long, c$
Private arr() As Variant, fixed As String * 10
Dim items(1 To 10) As Long
Private Declare Function GetTick Lib "kernel32" Alias "GetTickCount" () As Long
Public Const MAX_ROWS = 100
Public Event Changed
Dim idx
Dim sName
Public Function Calc$(ByVal n As Long)
    Dim localOnly As Long
End Function
Public Function Guess(ByRef x, Optional flag As Boolean = True, ParamArray rest() As Variant)
End Function
Property Get Count()
End Property
"""


def by_name(rows: list[dict]) -> dict:
    return {r["name"]: r for r in rows}


class ModuleDeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.info = _parse_bytes(MODULE.encode("cp932"), Path("M.bas"))
        self.vars = by_name(self.info["variables"])

    def test_options_and_deftypes(self) -> None:
        opts = self.info["options"]
        self.assertEqual((opts["explicit"], opts["base"], opts["compare"], opts["private_module"]),
                         (True, 1, "Text", False))
        self.assertEqual([(d["type"], d["ranges"], d["line"]) for d in opts["deftypes"]],
                         [("Integer", ["I-N"], 5), ("String", ["S"], 6)])

    def test_only_module_level_variables_are_listed(self) -> None:
        self.assertEqual(list(self.vars), ["gUser", "gConn", "Bus", "a", "b", "c", "arr", "fixed",
                                           "items", "idx", "sName"])
        self.assertNotIn("localOnly", self.vars)

    def test_each_declarator_has_its_own_type(self) -> None:
        # Dim a, b As Long: a is a Variant, not a Long.
        self.assertEqual((self.vars["a"]["type"], self.vars["a"]["type_source"]), ("Variant", "default"))
        self.assertEqual((self.vars["b"]["type"], self.vars["b"]["type_source"]), ("Long", "as"))
        self.assertEqual((self.vars["c"]["type"], self.vars["c"]["type_source"]), ("String", "suffix"))
        self.assertEqual((self.vars["idx"]["type"], self.vars["idx"]["type_source"]), ("Integer", "deftype"))
        self.assertEqual((self.vars["sName"]["type"], self.vars["sName"]["type_source"]), ("String", "deftype"))
        self.assertEqual(self.vars["fixed"]["type"], "String * 10")

    def test_keywords_arrays_new_and_withevents(self) -> None:
        self.assertEqual((self.vars["gUser"]["keyword"], self.vars["gUser"]["visibility"]), ("Global", "Public"))
        self.assertEqual((self.vars["a"]["keyword"], self.vars["a"]["visibility"]), ("Dim", "Private"))
        self.assertTrue(self.vars["gConn"]["new"])
        self.assertEqual(self.vars["gConn"]["type"], "ADODB.Connection")
        self.assertTrue(self.vars["Bus"]["with_events"])
        self.assertEqual((self.vars["arr"]["is_array"], self.vars["arr"]["dims"]), (True, ""))
        self.assertEqual(self.vars["items"]["dims"], "1 To 10")

    def test_function_with_type_suffix_keeps_params_and_return(self) -> None:
        procs = by_name(self.info["procedures"])
        calc = procs["Calc"]
        self.assertEqual((calc["params"], calc["type_suffix"]), ("ByVal n As Long", "$"))
        self.assertEqual((calc["return_type"], calc["return_type_source"]), ("String", "suffix"))
        self.assertEqual((procs["Guess"]["return_type"], procs["Guess"]["return_type_source"]),
                         ("Variant", "default"))
        self.assertEqual((procs["Count"]["return_type"], procs["Count"]["return_type_source"]),
                         ("Variant", "default"))

    def test_params_detail_marks_implicit_byref(self) -> None:
        params = self.info["procedures"][1]["params_detail"]
        self.assertEqual([(p["name"], p["passing"], p["passing_explicit"]) for p in params],
                         [("x", "ByRef", True), ("flag", "ByRef", False), ("rest", "ByRef", False)])
        self.assertEqual((params[1]["optional"], params[1]["default"], params[1]["type"]),
                         (True, "True", "Boolean"))
        self.assertTrue(params[2]["param_array"] and params[2]["is_array"])
        self.assertEqual(params[0]["type"], "Variant")

    def test_missing_option_explicit_is_recorded(self) -> None:
        info = _parse_bytes(b'Attribute VB_Name = "N"\r\nDim z\r\n', Path("N.bas"))
        self.assertFalse(info["options"]["explicit"])
        self.assertEqual(info["variables"][0]["type"], "Variant")


class DeclaratorUnitTests(unittest.TestCase):
    def test_deftype_ranges_and_override(self) -> None:
        letters = deftype_letters([parse_deftype("DefLng A-Z", 1), parse_deftype("DefStr s", 2)])
        self.assertEqual((letters["A"], letters["S"], letters["Z"]), ("Long", "String", "Long"))
        self.assertIsNone(parse_deftype("Dim x", 3))

    def test_string_and_paren_commas_stay_inside_declarators(self) -> None:
        got = parse_var_declarators('m(1 To 3, 1 To 4) As Long, q')
        self.assertEqual([(d["name"], d["dims"]) for d in got], [("m", "1 To 3, 1 To 4"), ("q", None)])

    def test_param_default_with_string_comma(self) -> None:
        got = parse_params('Optional ByVal sep As String = ",", n As Integer')
        self.assertEqual([(p["name"], p["default"]) for p in got], [("sep", '","'), ("n", None)])
        self.assertEqual(got[0]["passing"], "ByVal")

    def test_unparsed_param_keeps_raw_text(self) -> None:
        self.assertEqual(parse_params("ByVal"), [{"raw": "ByVal"}])


if __name__ == "__main__":
    unittest.main()
