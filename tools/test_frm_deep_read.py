from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.frm_deep_read import (
    annotate_hidden_ancestor,
    collect_goto_label_maps,
    find_goto_skipped_opens,
    find_goto_skipped_stmts,
    resolve_deep_read_out_key,
    write_report,
)


def ctrl(
    name: str,
    *,
    kind: str = "VB.Label",
    parent: str | None = None,
    visible: bool = True,
    live: bool = False,
    left: int = 0,
    top: int = 0,
    width: int = 100,
    height: int = 100,
) -> dict:
    return {
        "kind": kind,
        "name": name,
        "parent": parent,
        "visible": visible,
        "live": live,
        "abs_left": left,
        "abs_top": top,
        "width": width,
        "height": height,
        "line": 1,
        "caption": "",
        "index": None,
    }


def _frm_lines(*body: str) -> list[str]:
    """Minimal .frm code section so extract_events sees the Subs."""
    return [
        'Attribute VB_Name = "FormTest"',
        "Option Explicit",
        *body,
    ]


class OutKeyTests(unittest.TestCase):
    def test_uses_vb_name_not_file_stem(self) -> None:
        key = resolve_deep_read_out_key(
            "Form12", Path("BackupDay.frm"), mapping={}
        )
        self.assertEqual(key, "form12")

    def test_name_map_override(self) -> None:
        key = resolve_deep_read_out_key(
            "MDIForm1",
            Path("MDIForm1.frm"),
            mapping={"MDIForm1": "mdi"},
        )
        self.assertEqual(key, "mdi")

    def test_fallback_to_stem(self) -> None:
        key = resolve_deep_read_out_key("", Path("Orphan.frm"), mapping={})
        self.assertEqual(key, "orphan")


class AncestorHiddenTests(unittest.TestCase):
    def test_dead_invisible_frame_marks_children(self) -> None:
        controls = [
            ctrl(
                "FrameDead",
                kind="VB.Frame",
                visible=False,
                live=False,
                width=2000,
                height=1000,
            ),
            ctrl("LabelHidden", parent="FrameDead", left=120, top=360),
        ]
        annotate_hidden_ancestor(controls)
        child = controls[1]
        self.assertTrue(child.get("ancestor_hidden"))
        self.assertEqual(child.get("ancestor_hidden_by"), "FrameDead")

    def test_live_invisible_frame_does_not_mark_children(self) -> None:
        controls = [
            ctrl(
                "FrameLive",
                kind="VB.Frame",
                visible=False,
                live=True,
                width=2000,
                height=1000,
            ),
            ctrl("LabelOk", parent="FrameLive", left=120, top=360),
        ]
        annotate_hidden_ancestor(controls)
        self.assertFalse(controls[1].get("ancestor_hidden"))


class GotoSkippedOpenTests(unittest.TestCase):
    def test_unconditional_goto_skips_open(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoTo OWA",
            '    Open App.Path & "\\LABEL.dat" For Input As #1',
            "OWA:",
            "End Sub",
        )
        hits = find_goto_skipped_opens(lines)
        self.assertEqual(len(hits), 1)
        h = hits[0]
        self.assertEqual(h["sub"], "Form_Load")
        self.assertEqual(h["goto_kind"], "unconditional")
        self.assertEqual(h["label"], "OWA")
        self.assertIn("LABEL.dat", h["path_fragment"])
        self.assertLess(h["goto_line"], h["open_line"])
        self.assertLess(h["open_line"], h["label_line"])

    def test_acceptance_fixture_loop_then_goto_skips_open(self) -> None:
        """Minimal acceptance fixture: Do/Loop + If Then GoTo spanning Open."""
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    Do",
            "        If ds1.EOF = True Then GoTo OWA",
            "        ds1.MoveNext",
            "    Loop",
            "JP:",
            '    Open DRV & ":\\Dtmanage\\LABEL.dat" For Input As #1',
            "    Close",
            "OWA:",
            "    ds1.Close",
            "End Sub",
        )
        hits = find_goto_skipped_opens(lines)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["goto_kind"], "conditional")
        self.assertEqual(hits[0]["label"], "OWA")
        self.assertIn("LABEL.dat", hits[0]["path_fragment"])
        self.assertLess(hits[0]["goto_line"], hits[0]["open_line"])
        self.assertLess(hits[0]["open_line"], hits[0]["label_line"])

    def test_reachable_open_without_spanning_goto(self) -> None:
        """Ordinary Open with no forward GoTo over it must not be flagged."""
        lines = _frm_lines(
            "Private Sub Form_Load()",
            '    Open App.Path & "\\ok.dat" For Input As #1',
            "    Close #1",
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_opens(lines), [])

    def test_open_after_label_not_flagged(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    If ds1.EOF Then GoTo OWA",
            "OWA:",
            '    Open App.Path & "\\LABEL.dat" For Input As #1',
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_opens(lines), [])

    def test_on_error_goto_not_flagged(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    On Error GoTo ErrH",
            '    Open App.Path & "\\x.dat" For Input As #1',
            "    Exit Sub",
            "ErrH:",
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_opens(lines), [])

    def test_backward_goto_not_flagged(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "Retry:",
            '    Open App.Path & "\\x.dat" For Input As #1',
            "    GoTo Retry",
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_opens(lines), [])

    def test_report_section_includes_caveat(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoTo Done",
            '    Open "skip.dat" For Input As #1',
            "Done:",
            "End Sub",
        )
        hits = find_goto_skipped_opens(lines)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [{"name": "Form_Load", "status": "live", "start_line": 3,
                  "end_line": 7, "size": 5, "scope": "Private"}],
                {},
                [],
                len(lines),
                [],
                [],
                goto_skipped_stmts=hits,
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("GoTo で飛び越えられる文（候補）", text)
        self.assertIn("静的近似", text)
        self.assertIn("断定しない", text)
        self.assertIn("ソース順＝実行順と読まないこと", text)
        self.assertIn("unconditional", text)
        self.assertIn("skip.dat", text)

    def test_skips_call_and_kill(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoTo Done",
            '    Kill App.Path & "\\tmp.dat"',
            "    Call Helper",
            "Done:",
            "End Sub",
        )
        hits = find_goto_skipped_stmts(lines)
        kinds = {h["stmt_kind"] for h in hits}
        self.assertEqual(kinds, {"kill", "call"})

    def test_dim_not_flagged_as_skip(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoTo Done",
            "    Dim x As Long",
            "    x = 1",
            "Done:",
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_stmts(lines), [])

    def test_label_map_lists_gotos(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoTo Done",
            "    Dim x As Long",
            "Done:",
            "End Sub",
        )
        events = [
            {
                "name": "Form_Load",
                "status": "live",
                "start_line": 3,
                "end_line": 7,
            }
        ]
        maps = collect_goto_label_maps(lines, events)
        self.assertEqual(len(maps), 1)
        self.assertEqual(maps[0]["gotos"][0]["target"], "Done")
        self.assertEqual(maps[0]["labels"][0]["name"], "done")


if __name__ == "__main__":
    unittest.main()
