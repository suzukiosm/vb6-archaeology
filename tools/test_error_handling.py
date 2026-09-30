"""Error-handling facts and statement-based GoTo maps (review counterexamples)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.frm_deep_read import collect_goto_label_maps, extract_events, find_goto_skipped_stmts
from tools.vb6_inventory import _parse_bytes

REVIEW_CASE = [
    "Public Sub G()",
    "    On Error GoTo ErrH",
    "    x = 1: GoTo Done",
    '    Kill "a.dat"',
    "Done:",
    "    Exit Sub",
    "ErrH: MsgBox Err.Description",
    "End Sub",
]


class StatementBasedGotoTests(unittest.TestCase):
    def test_label_with_trailing_statement_and_colon_joined_goto(self) -> None:
        maps = collect_goto_label_maps(REVIEW_CASE, extract_events(REVIEW_CASE))
        self.assertEqual([(lb["name"], lb["line"]) for lb in maps[0]["labels"]],
                         [("done", 5), ("errh", 7)])
        self.assertEqual([(g["line"], g["target"], g["kind"]) for g in maps[0]["gotos"]],
                         [(2, "ErrH", "on_error"), (3, "Done", "unconditional")])
        hits = find_goto_skipped_stmts(REVIEW_CASE)
        self.assertEqual([(h["stmt_kind"], h["stmt_line"], h["goto_line"]) for h in hits],
                         [("kill", 4, 3)])

    def test_statement_after_goto_on_the_same_line_is_skipped(self) -> None:
        lines = ["Sub S()", '    GoTo Done: Kill "x.dat"', "Done:", "End Sub"]
        hits = find_goto_skipped_stmts(lines)
        self.assertEqual([(h["stmt_kind"], h["stmt_line"]) for h in hits], [("kill", 2)])

    def test_numeric_line_label_target(self) -> None:
        lines = ["Sub S()", "10 GoTo 30", "20 Open f For Input As #1", "30 Close", "End Sub"]
        hits = find_goto_skipped_stmts(lines)
        self.assertEqual([(h["stmt_kind"], h["label"], h["label_line"]) for h in hits],
                         [("open", "30", 4)])

    def test_else_colon_is_not_a_label(self) -> None:
        lines = ["Sub S()", "    If a Then", "        b = 1", "    Else: GoTo Out", "    End If",
                 '    Kill "x"', "Out:", "End Sub"]
        maps = collect_goto_label_maps(lines)
        self.assertEqual([lb["name"] for lb in maps[0]["labels"]], ["out"])
        self.assertEqual([h["stmt_kind"] for h in find_goto_skipped_stmts(lines)], ["kill"])


class InventoryErrorHandlingTests(unittest.TestCase):
    def test_error_modes_resumes_raises_and_labels(self) -> None:
        info = _parse_bytes("\r\n".join([
            'Attribute VB_Name = "M"',
            "Public Sub Work()",
            "    On Error Resume Next",
            '    Kill "tmp.dat"',
            "    On Error GoTo 0",
            "    On Error GoTo Fail",
            '    If bad Then Err.Raise vbObjectError + 1',
            "    Exit Sub",
            "Fail:",
            "    If Err.Number = 53 Then Resume Next",
            "    Resume Retry",
            "Retry: Resume",
            "End Sub",
            "Public Sub Quiet()",
            "End Sub",
        ]).encode("cp932"), Path("M.bas"))
        work, quiet = info["procedures"]
        self.assertEqual(
            [(e["kind"], e["line"], e.get("target")) for e in work["error_handling"]],
            [("on_error_resume_next", 3, None), ("on_error_goto_0", 5, None),
             ("on_error_goto", 6, "Fail"), ("err_raise", 7, None), ("resume_next", 10, None),
             ("resume_label", 11, "Retry"), ("resume", 12, None)],
        )
        self.assertEqual(work["labels"], [{"name": "Fail", "line": 9}, {"name": "Retry", "line": 12}])
        self.assertNotIn("error_handling", quiet)
        self.assertNotIn("labels", quiet)


if __name__ == "__main__":
    unittest.main()
