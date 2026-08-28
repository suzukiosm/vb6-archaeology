from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.frm_deep_read import (
    FONT_FACE_BLACKLIST,
    analyze_module_file,
    annotate_hidden_ancestor,
    build_menu_tree,
    classify_controls,
    classify_events,
    collect_goto_label_maps,
    extract_controls,
    extract_events,
    extract_para,
    extract_show_map,
    find_goto_skipped_opens,
    find_goto_skipped_stmts,
    flatten_menu_tree,
    resolve_deep_read_out_key,
    write_module_report,
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

    def test_label_map_lists_on_error_and_gosub(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    On Error GoTo ErrH",
            "    GoSub Prep",
            '    Open App.Path & "\\x.dat" For Input As #1',
            "    Exit Sub",
            "Prep:",
            "    Return",
            "ErrH:",
            "End Sub",
        )
        maps = collect_goto_label_maps(lines)
        kinds = {g["kind"]: g["target"] for g in maps[0]["gotos"]}
        self.assertEqual(kinds["on_error"], "ErrH")
        self.assertEqual(kinds["gosub"], "Prep")
        self.assertEqual(find_goto_skipped_opens(lines), [])

    def test_gosub_does_not_open_skip_span(self) -> None:
        lines = _frm_lines(
            "Private Sub Form_Load()",
            "    GoSub Prep",
            '    Open App.Path & "\\x.dat" For Input As #1',
            "    Exit Sub",
            "Prep:",
            "    Return",
            "End Sub",
        )
        self.assertEqual(find_goto_skipped_opens(lines), [])
        self.assertEqual(find_goto_skipped_stmts(lines), [])


class MenuTreeTests(unittest.TestCase):
    def test_nested_designer_values_and_has_click(self) -> None:
        lines = [
            "VERSION 5.00",
            "Begin VB.Form Form1",
            '   Caption         =   "t"',
            "   Begin VB.Menu mnuFile",
            '      Caption         =   "File"',
            "      Begin VB.Menu mnuOpen",
            '         Caption         =   "Open"',
            "      End",
            "      Begin VB.Menu mnuHidden",
            '         Caption         =   "Hide"',
            "         Visible         =   0   'False",
            "      End",
            "      Begin VB.Menu mnuOff",
            '         Caption         =   "Off"',
            "         Enabled         =   0   'False",
            "      End",
            "   End",
            "End",
            'Attribute VB_Name = "Form1"',
        ]
        form_info, controls = extract_controls(lines)
        self.assertEqual(form_info["name"], "Form1")
        menus = [c for c in controls if c["kind"] == "VB.Menu"]
        self.assertEqual([c["name"] for c in menus], ["mnuOpen", "mnuHidden", "mnuOff", "mnuFile"])
        by_name = {c["name"]: c for c in menus}
        self.assertEqual(by_name["mnuOpen"]["parent"], "mnuFile")
        self.assertEqual(by_name["mnuFile"]["parent"], "Form1")
        self.assertFalse(by_name["mnuHidden"]["visible"])
        self.assertFalse(by_name["mnuOff"]["enabled"])

        events = [{"name": "mnuOpen_Click"}]
        tree = build_menu_tree(controls, events)
        self.assertEqual(len(tree), 1)
        root = tree[0]
        self.assertEqual(root["name"], "mnuFile")
        self.assertEqual(root["caption"], "File")
        self.assertFalse(root["has_click"])
        self.assertEqual(root["parent"], "Form1")
        child_names = [c["name"] for c in root["children"]]
        self.assertEqual(child_names, ["mnuOpen", "mnuHidden", "mnuOff"])
        self.assertTrue(root["children"][0]["has_click"])
        self.assertFalse(root["children"][1]["visible"])
        self.assertFalse(root["children"][2]["enabled"])
        self.assertEqual(root["children"][0]["parent"], "mnuFile")

    def test_empty_controls_yield_empty_tree(self) -> None:
        self.assertEqual(build_menu_tree([ctrl("Label1")], []), [])

    def test_report_separates_tree_from_runtime_enabled(self) -> None:
        tree = [{
            "name": "mnuFile",
            "caption": "File",
            "line": 10,
            "visible": True,
            "enabled": True,
            "has_click": False,
            "parent": "Form1",
            "children": [{
                "name": "mnuOpen",
                "caption": "Open",
                "line": 12,
                "visible": True,
                "enabled": True,
                "has_click": True,
                "parent": "mnuFile",
                "children": [],
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [],
                {},
                [],
                20,
                [],
                [],
                menu_tree=tree,
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("メニュー木（デザイナ値）", text)
        self.assertIn("layout を見る（混ぜない）", text)
        self.assertIn("`mnuFile`", text)
        self.assertIn("`mnuOpen`", text)
        self.assertIn("`Form1`", text)
        rows = flatten_menu_tree(tree)
        self.assertEqual([r["name"] for r in rows], ["mnuFile", "mnuOpen"])
        self.assertEqual(rows[1]["depth"], 1)


class ModuleReadTests(unittest.TestCase):
    def test_class_surface_and_skip_open(self) -> None:
        lines = [
            "VERSION 1.0 CLASS",
            "BEGIN",
            "  Instancing = 5",
            "END",
            'Attribute VB_Name = "Widget"',
            "Implements IPing",
            "Private WithEvents Bus As AppEvents",
            "Public Sub PlaceHost()",
            "    GoTo After",
            '    Open "modskip.dat" For Input As #3',
            "After:",
            "End Sub",
        ]
        data = analyze_module_file(lines, Path("Widget.cls"), "Widget")
        self.assertEqual(data["kind"], "class")
        self.assertEqual(data["surface"]["instancing"], 5)
        self.assertEqual(data["surface"]["implements"][0]["name"], "IPing")
        self.assertEqual(data["procedures"][0]["name"], "PlaceHost")
        self.assertEqual(data["goto_skipped_stmts"][0]["stmt_kind"], "open")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "widget_deep_read.md"
            write_module_report(
                path, data, source_label="working/extracts/demo/Widget.cls", total_lines=12
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("表面レポート", text)
        self.assertIn("Form の deep-read ではない", text)
        self.assertIn("IPing", text)
        self.assertIn("PlaceHost", text)

    def test_bas_kind(self) -> None:
        data = analyze_module_file(
            ['Attribute VB_Name = "Module1"', "Public Sub A()", "End Sub"],
            Path("Module1.bas"),
            "Module1",
        )
        self.assertEqual(data["kind"], "module")
        self.assertEqual(data["procedures"][0]["name"], "A")


class ClassifyEventsTests(unittest.TestCase):
    def test_general_sub_without_caller_is_unobserved(self) -> None:
        events = [{"name": "Helper"}]
        classify_events(events, "Private Sub Helper()\nEnd Sub\n", "", [], "Form1")
        self.assertEqual(events[0]["status"], "unobserved")
        self.assertEqual(events[0]["dead_reason"], "no_caller_observed")
        self.assertNotEqual(events[0]["status"], "dead")

    def test_event_with_designer_owner_is_live(self) -> None:
        events = [{"name": "Command1_Click"}]
        classify_events(events, "", "", [{"name": "Command1"}], "Form1")
        self.assertEqual(events[0]["status"], "live")

    def test_orphan_called_as_sub_is_live(self) -> None:
        events = [{"name": "FX_Click"}]
        code = (
            "Private Sub faxx_Click()\n"
            "    Dim x As Long\n"
            "    x = 1\n"
            "    FX_Click\n"
            "End Sub\n"
        )
        classify_events(events, code, "", [], "Form1")
        self.assertEqual(events[0]["status"], "live")
        self.assertEqual(events[0]["note"], "orphan handler, called as sub")

    def test_orphan_without_call_stays_dead(self) -> None:
        events = [{"name": "Ghost_Click"}]
        classify_events(events, "Private Sub Ghost_Click()\nEnd Sub\n", "", [], "Form1")
        self.assertEqual(events[0]["status"], "dead")
        self.assertIn("orphan", events[0]["dead_reason"])


class ReportHonestyTests(unittest.TestCase):
    def test_unobserved_section_says_not_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [{
                    "name": "Helper",
                    "status": "unobserved",
                    "start_line": 3,
                    "end_line": 5,
                    "size": 3,
                    "scope": "Private",
                    "dead_reason": "no_caller_observed",
                }],
                {},
                [],
                10,
                [],
                [],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("到達不能ではない", text)
        self.assertIn("未観測", text)
        self.assertIn("Helper", text)
        self.assertNotIn("## デッドプロシージャ", text)


class FontFaceTests(unittest.TestCase):
    def test_blacklist_excludes_ms_pgothic(self) -> None:
        controls = [ctrl("ＭＳ Ｐゴシック", kind="VB.Label"), ctrl("Label1")]
        classify_controls(controls, 'Label1.Caption = "x"', "", [], "Form1")
        by_name = {c["name"]: c for c in controls}
        self.assertFalse(by_name["ＭＳ Ｐゴシック"]["live"])
        self.assertTrue(by_name["Label1"]["live"])
        self.assertIn("ＭＳ Ｐゴシック", FONT_FACE_BLACKLIST)
        self.assertIn("ＭＳ ゴシック", FONT_FACE_BLACKLIST)
        self.assertIn("MS PGothic", FONT_FACE_BLACKLIST)
        self.assertIn("MS Gothic", FONT_FACE_BLACKLIST)
        self.assertGreaterEqual(len(FONT_FACE_BLACKLIST), 2)


class ParaOptionalTests(unittest.TestCase):
    def test_empty_markers_yield_no_hits(self) -> None:
        lines = _frm_lines('    PARA = "ABC"')
        self.assertEqual(extract_para(lines, markers=[]), [])

    def test_configured_marker_hits(self) -> None:
        lines = _frm_lines('    PARA = "ABC"')
        hits = extract_para(lines, markers=["PARA"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["line"], 3)
        self.assertEqual(hits[0]["marker"], "PARA")

    def test_extract_events_respects_markers(self) -> None:
        lines = _frm_lines(
            "Private Sub Command1_Click()",
            '    PARA = "X"',
            "End Sub",
        )
        ev_empty = extract_events(lines, assign_markers=[])
        self.assertEqual(ev_empty[0].get("para_sets"), [])
        ev_para = extract_events(lines, assign_markers=["PARA"])
        self.assertEqual(ev_para[0]["para_sets"], ["X"])

    def test_report_omits_para_heading_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [],
                {},
                [],
                10,
                [],
                [],
            )
            text = path.read_text(encoding="utf-8")
        self.assertNotIn("## PARA", text)
        self.assertNotIn("## 任意スキャン", text)
        self.assertNotIn("PARA=", text)

    def test_report_optional_scan_when_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [],
                {},
                [{"line": 10, "text": 'PARA = "X"'}],
                10,
                [],
                [],
                assign_markers=["PARA"],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("任意スキャン（消費者固有の識別子）", text)
        self.assertNotIn("## PARA（", text)


class LifetimeSurfaceTests(unittest.TestCase):
    def test_extract_events_lifetime_and_me_bare_show(self) -> None:
        lines = _frm_lines(
            "Private Sub Command1_Click()",
            "    Me.Show",
            "    Show vbModal",
            "    Load Form1",
            "    Unload Me",
            "    If Err Then Unload Me: Form12.Show vbModal",
            "End Sub",
        )
        events = extract_events(lines)
        self.assertEqual(len(events), 1)
        ev = events[0]
        show_targets = [c["target"] for c in ev["show_calls"]]
        self.assertIn("Me", show_targets)
        self.assertIn("", show_targets)
        self.assertIn("Form12", show_targets)
        kinds = [(c["kind"], c["target"]) for c in ev["lifetime_calls"]]
        self.assertIn(("load", "Form1"), kinds)
        self.assertGreaterEqual(sum(1 for k, t in kinds if k == "unload" and t == "Me"), 2)

    def test_report_includes_lifetime_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {"name": "FormTest", "caption": "t"},
                [],
                [
                    {
                        "name": "Command1_Click",
                        "status": "live",
                        "start_line": 3,
                        "end_line": 8,
                        "size": 6,
                        "scope": "Private",
                        "lifetime_calls": [
                            {
                                "kind": "load",
                                "target": "Form1",
                                "line": 5,
                                "text": "Load Form1",
                            },
                            {
                                "kind": "unload",
                                "target": "Me",
                                "line": 6,
                                "text": "Unload Me",
                            },
                        ],
                    }
                ],
                {},
                [],
                10,
                [],
                [],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("Load/Unload 文面", text)
        self.assertIn("`load`", text)
        self.assertIn("`Form1`", text)
        self.assertIn("`unload`", text)


class ShowMapStatusTests(unittest.TestCase):
    def test_unobserved_excluded_like_dead(self) -> None:
        events = [
            {
                "name": "LiveShow",
                "status": "live",
                "start_line": 1,
                "shows": ["Form2"],
                "para_sets": [],
                "show_calls": [{"target": "Form2"}],
            },
            {
                "name": "DeadShow",
                "status": "dead",
                "start_line": 2,
                "shows": ["Form3"],
                "para_sets": [],
                "show_calls": [{"target": "Form3"}],
            },
            {
                "name": "UnseenShow",
                "status": "unobserved",
                "start_line": 3,
                "shows": ["Form4"],
                "para_sets": [],
                "show_calls": [{"target": "Form4"}],
            },
        ]
        rows = extract_show_map(events)
        self.assertEqual([r["sub"] for r in rows], ["LiveShow"])


if __name__ == "__main__":
    unittest.main()

