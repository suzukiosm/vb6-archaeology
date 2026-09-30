"""Unit tests for lib.vbparse logical-line folding and colon split (synthetic)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.vbparse import (  # noqa: E402
    conditional_regions,
    find_comment_continuations,
    innermost_region,
    iter_logical_lines,
    iter_statements,
    split_colon_statements,
)


class LogicalLineTests(unittest.TestCase):
    def test_plain_lines_map_one_to_one(self) -> None:
        lines = ["A = 1", "B = 2", "C = 3"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 3)
        for i, ll in enumerate(out, start=1):
            self.assertEqual(ll.phys_start, i)
            self.assertEqual(ll.phys_end, i)

    def test_continuation_is_folded_but_span_preserved(self) -> None:
        lines = [
            'Declare Function Foo Lib "k32" ( _',
            "    ByVal a As Long, _",
            "    ByVal b As Long) As Long",
            "X = 1",
        ]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 2)
        first = out[0]
        self.assertEqual(first.phys_start, 1)
        self.assertEqual(first.phys_end, 3)
        self.assertIn('Lib "k32"', first.text)
        self.assertIn("ByVal b As Long) As Long", first.text)
        self.assertEqual(out[1].phys_start, 4)

    def test_trailing_identifier_underscore_is_not_continuation(self) -> None:
        # "my_var" ends in underscore but has no preceding whitespace -> not a cont.
        lines = ["Dim my_var", "Y = 2"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 2)

    def test_dangling_continuation_does_not_crash(self) -> None:
        lines = ["Foo = 1 _"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].phys_start, 1)


class ColonSplitTests(unittest.TestCase):
    def test_simple_two_assignments(self) -> None:
        self.assertEqual(
            split_colon_statements("a = 1: b = 2"),
            ["a = 1", "b = 2"],
        )

    def test_colon_inside_string_is_not_a_split(self) -> None:
        self.assertEqual(
            split_colon_statements('Caption = "a:b"'),
            ['Caption = "a:b"'],
        )

    def test_escaped_quotes_in_caption_style(self) -> None:
        text = 'Me.Caption = "say ""hi:there"""'
        self.assertEqual(split_colon_statements(text), [text])
        both = 'Me.Caption = "say ""hi:there""": x = 1'
        self.assertEqual(
            split_colon_statements(both),
            ['Me.Caption = "say ""hi:there"""', "x = 1"],
        )

    def test_if_then_two_statements(self) -> None:
        self.assertEqual(
            split_colon_statements("If x Then Unload Me: Exit Sub"),
            ["If x Then Unload Me", "Exit Sub"],
        )

    def test_line_comment_is_dropped(self) -> None:
        self.assertEqual(split_colon_statements("' Open x As #1"), [])
        self.assertEqual(
            split_colon_statements("a = 1: b = 2 ' tail"),
            ["a = 1", "b = 2"],
        )

    def test_rem_comment_yields_no_statements(self) -> None:
        self.assertEqual(split_colon_statements("Rem this is a comment"), [])
        self.assertEqual(split_colon_statements("Rem foo: x = 1"), [])
        self.assertEqual(split_colon_statements("x = 1: Rem rest: y = 2"), ["x = 1"])

    def test_label_only_omitted_from_split(self) -> None:
        self.assertEqual(split_colon_statements("Foo:"), [])
        self.assertEqual(split_colon_statements("Foo: ' comment"), [])
        self.assertEqual(split_colon_statements("Foo: x = 1"), ["x = 1"])

    def test_bare_identifier_call_is_a_statement(self) -> None:
        self.assertEqual(split_colon_statements("Foo"), ["Foo"])
        self.assertEqual(split_colon_statements("Kill"), ["Kill"])


class IterStatementsTests(unittest.TestCase):
    def test_three_stmts_share_physical_line(self) -> None:
        out = iter_statements(["a = 1: b = 2: c = 3"])
        self.assertEqual(len(out), 3)
        for stmt in out:
            self.assertEqual(stmt.phys_start, 1)
            self.assertEqual(stmt.phys_end, 1)
            self.assertEqual(stmt.kind, "stmt")
        self.assertEqual([s.text for s in out], ["a = 1", "b = 2", "c = 3"])

    def test_label_kind_is_distinct(self) -> None:
        out = iter_statements(["Foo:"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "label")
        self.assertEqual(out[0].text, "Foo")
        self.assertEqual(out[0].phys_start, 1)
        labeled = iter_statements(['Foo: Kill "tmp.bak"'])
        self.assertEqual([(s.kind, s.text) for s in labeled], [
            ("label", "Foo"),
            ("stmt", 'Kill "tmp.bak"'),
        ])

    def test_continuation_then_colon_keeps_span(self) -> None:
        lines = [
            "a = 1 _",
            "    : b = 2",
        ]
        out = iter_statements(lines)
        self.assertEqual(len(out), 2)
        self.assertEqual([s.text for s in out], ["a = 1", "b = 2"])
        for stmt in out:
            self.assertEqual(stmt.phys_start, 1)
            self.assertEqual(stmt.phys_end, 2)
            self.assertEqual(stmt.kind, "stmt")

    def test_kill_label_is_not_a_statement(self) -> None:
        out = iter_statements(["Kill:"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "label")
        self.assertEqual(out[0].text, "Kill")

    def test_bare_identifier_is_stmt_not_label(self) -> None:
        out = iter_statements(["Foo"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "stmt")
        self.assertEqual(out[0].text, "Foo")


class SpecAlignedLexingTests(unittest.TestCase):
    def kinds(self, line: str) -> list[tuple[str, str]]:
        return [(s.kind, s.text) for s in iter_statements([line])]

    def test_keywords_before_a_colon_are_statements(self) -> None:
        self.assertEqual(self.kinds("Else: x = 1"), [("stmt", "Else"), ("stmt", "x = 1")])
        self.assertEqual(self.kinds("Loop: y = 2"), [("stmt", "Loop"), ("stmt", "y = 2")])

    def test_numeric_line_labels(self) -> None:
        self.assertEqual(self.kinds("10 Print x"), [("label", "10"), ("stmt", "Print x")])
        self.assertEqual(self.kinds("20: GoTo 10"), [("label", "20"), ("stmt", "GoTo 10")])
        self.assertEqual(self.kinds("30"), [("label", "30")])
        self.assertEqual(self.kinds("40 ' just a line number"), [("label", "40")])

    def test_frx_offset_after_a_colon_stays_a_statement(self) -> None:
        self.assertEqual(self.kinds('Picture = "Form1.frx":0000'),
                         [("stmt", 'Picture = "Form1.frx"'), ("stmt", "0000")])

    def test_japanese_identifier_label(self) -> None:
        self.assertEqual(self.kinds("処理終了:"), [("label", "処理終了")])

    def test_comment_continuation_spans_several_lines(self) -> None:
        lines = ["x = 1 ' note _", "  still comment _", "  and this", "y = 2"]
        self.assertEqual([(s.text, s.phys_start) for s in iter_statements(lines)],
                         [("x = 1", 1), ("y = 2", 4)])
        self.assertEqual(find_comment_continuations(lines), [{"line": 1, "absorbed": [2, 3]}])

    def test_code_continuation_then_comment_continuation(self) -> None:
        lines = ["s = \"a\" & _", "    \"b\" ' tail _", "Kill p", "z = 3"]
        self.assertEqual([s.text for s in iter_statements(lines)], ['s = "a" & "b"', "z = 3"])
        self.assertEqual(find_comment_continuations(lines), [{"line": 2, "absorbed": [3]}])

    def test_underscore_inside_a_word_or_string_is_not_continuation(self) -> None:
        self.assertEqual(find_comment_continuations(["' my_var_", "x = 1"]), [])
        self.assertEqual(len(iter_logical_lines(['s = "a _"', "t = 1"])), 2)


class ConditionalRegionTests(unittest.TestCase):
    LINES = [
        "#Const DEBUG_MODE = 1",   # 1
        "#If DEBUG_MODE Then",     # 2
        "Sub A()",                 # 3
        "End Sub",                 # 4
        "  #If Win32 Then",        # 5
        "Sub B()",                 # 6
        "End Sub",                 # 7
        "  #End If",               # 8
        "#Else",                   # 9
        "Sub A()",                 # 10
        "End Sub",                 # 11
        "#End If",                 # 12
        "Sub C()",                 # 13
    ]

    def test_regions_and_innermost_branch(self) -> None:
        regions = conditional_regions(iter_statements(self.LINES))
        self.assertEqual(
            [(r["line"], r["directive"], r["expr"], r["depth"], r["end"]) for r in regions],
            [(1, "#Const", "DEBUG_MODE = 1", 0, 1),
             (2, "#If", "DEBUG_MODE", 1, 9),
             (5, "#If", "Win32", 2, 8),
             (9, "#Else", "", 1, 12)],
        )
        self.assertEqual(innermost_region(regions, 3)["line"], 2)
        self.assertEqual(innermost_region(regions, 6)["line"], 5)
        self.assertEqual(innermost_region(regions, 10)["directive"], "#Else")
        self.assertIsNone(innermost_region(regions, 13))

    def test_unterminated_region_runs_to_the_end(self) -> None:
        regions = conditional_regions(iter_statements(["#If X Then", "Sub A()", "End Sub"]))
        self.assertEqual(innermost_region(regions, 3)["line"], 1)


if __name__ == "__main__":
    unittest.main()
