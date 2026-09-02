"""show_style heuristics and deep-read / excerpt wiring."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.frm_deep_read import (
    extract_controls,
    extract_events,
    extract_show_map,
    form_show_style_block,
    write_report,
)
from tools.lib.show_style import (
    attach_show_inbound,
    classify_show_arg,
    invert_show_calls,
    parse_lifetime_calls_in_line,
    parse_show_calls_in_line,
)
from tools.reimpl_excerpt import (
    build_excerpt_html,
    load_goto_counts,
    module_class_surface,
    write_excerpt,
)
from tools.serve_reports import ReportsHandler


class ClassifyShowArgTests(unittest.TestCase):
    def test_vbmodal(self) -> None:
        self.assertEqual(classify_show_arg("vbModal"), "modal_overlay")
        self.assertEqual(classify_show_arg("1"), "modal_overlay")

    def test_bare_and_modeless_stay_unknown(self) -> None:
        self.assertEqual(classify_show_arg(None), "unknown")
        self.assertEqual(classify_show_arg("vbModeless"), "unknown")
        self.assertEqual(classify_show_arg("0"), "unknown")


class ParseShowCallsTests(unittest.TestCase):
    def test_parses_arg_and_style(self) -> None:
        calls = parse_show_calls_in_line("    Form12.Show vbModal", 42)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["target"], "Form12")
        self.assertEqual(calls[0]["arg"], "vbModal")
        self.assertEqual(calls[0]["show_style"], "modal_overlay")
        self.assertEqual(calls[0]["line"], 42)

    def test_me_show_keeps_target_me(self) -> None:
        calls = parse_show_calls_in_line("    Me.Show", 7)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["target"], "Me")
        self.assertIsNone(calls[0]["arg"])
        self.assertEqual(calls[0]["show_style"], "unknown")

    def test_bare_show_target_is_empty(self) -> None:
        calls = parse_show_calls_in_line("Show vbModal", 3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["target"], "")
        self.assertEqual(calls[0]["arg"], "vbModal")
        self.assertEqual(calls[0]["show_style"], "modal_overlay")

    def test_then_else_bare_show(self) -> None:
        then_calls = parse_show_calls_in_line("If x Then Show", 4)
        self.assertEqual(then_calls[0]["target"], "")
        else_calls = parse_show_calls_in_line("Else Show vbModeless", 5)
        self.assertEqual(else_calls[0]["target"], "")
        self.assertEqual(else_calls[0]["arg"], "vbModeless")

    def test_comment_and_ident_show_not_double_counted(self) -> None:
        self.assertEqual(parse_show_calls_in_line("' Form12.Show vbModal", 1), [])
        self.assertEqual(parse_show_calls_in_line("Rem Form12.Show", 1), [])
        calls = parse_show_calls_in_line("Form12.Show vbModal", 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["target"], "Form12")


class ParseLifetimeCallsTests(unittest.TestCase):
    def test_load_form1(self) -> None:
        hits = parse_lifetime_calls_in_line("    Load Form1", 10)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "load")
        self.assertEqual(hits[0]["target"], "Form1")
        self.assertEqual(hits[0]["line"], 10)

    def test_unload_me(self) -> None:
        hits = parse_lifetime_calls_in_line("    Unload Me", 11)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "unload")
        self.assertEqual(hits[0]["target"], "Me")

    def test_load_control_array_keeps_subscript(self) -> None:
        hits = parse_lifetime_calls_in_line("Load Command1(1)", 12)
        self.assertEqual(hits[0]["target"], "Command1(1)")
        self.assertEqual(hits[0]["kind"], "load")

    def test_lifetime_skips_comment(self) -> None:
        self.assertEqual(parse_lifetime_calls_in_line("' Load Form1", 1), [])


class InvertShowCallsTests(unittest.TestCase):
    def test_known_target_becomes_inbound(self) -> None:
        files = [
            {
                "file": "Form1.frm",
                "vb_name": "Form1",
                "type": "form",
                "show_calls": [
                    {
                        "target": "Form12",
                        "arg": "vbModal",
                        "show_style": "modal_overlay",
                        "line": 10,
                    }
                ],
            },
            {
                "file": "BackupDay.frm",
                "vb_name": "Form12",
                "type": "form",
                "show_calls": [],
            },
        ]
        inbound, unresolved = invert_show_calls(files)
        self.assertEqual(unresolved, [])
        self.assertEqual(len(inbound["form12"]), 1)
        self.assertEqual(inbound["form12"][0]["from_vb_name"], "Form1")
        self.assertEqual(inbound["form1"], [])

    def test_unknown_target_is_unresolved(self) -> None:
        files = [
            {
                "file": "Form1.frm",
                "vb_name": "Form1",
                "type": "form",
                "show_calls": [
                    {
                        "target": "Ghost",
                        "arg": None,
                        "show_style": "unknown",
                        "line": 3,
                    }
                ],
            }
        ]
        inbound, unresolved = invert_show_calls(files)
        self.assertEqual(inbound["form1"], [])
        self.assertEqual(unresolved[0]["target"], "Ghost")
        self.assertEqual(unresolved[0]["reason"], "unresolved")

    def test_file_stem_match_when_vb_name_differs(self) -> None:
        files = [
            {
                "file": "Caller.frm",
                "vb_name": "Caller",
                "type": "form",
                "show_calls": [
                    {
                        "target": "BackupDay",
                        "arg": None,
                        "show_style": "unknown",
                        "line": 4,
                    }
                ],
            },
            {
                "file": "BackupDay.frm",
                "vb_name": "Form12",
                "type": "form",
                "show_calls": [],
            },
        ]
        inbound, unresolved = invert_show_calls(files)
        self.assertEqual(unresolved, [])
        self.assertEqual(inbound["form12"][0]["from_file"], "Caller.frm")

    def test_me_and_empty_target_stay_unresolved(self) -> None:
        files = [
            {
                "file": "Form1.frm",
                "vb_name": "Form1",
                "type": "form",
                "show_calls": [
                    {
                        "target": "Me",
                        "arg": None,
                        "show_style": "unknown",
                        "line": 8,
                    },
                    {
                        "target": "",
                        "arg": "vbModal",
                        "show_style": "modal_overlay",
                        "line": 9,
                    },
                ],
            }
        ]
        inbound, unresolved = invert_show_calls(files)
        self.assertEqual(inbound["form1"], [])
        reasons = {r["target"]: r["reason"] for r in unresolved}
        self.assertEqual(reasons["Me"], "self")
        self.assertEqual(reasons[""], "implicit")

    def test_attach_writes_fields_on_report(self) -> None:
        report = {
            "files": [
                {
                    "file": "A.frm",
                    "vb_name": "A",
                    "type": "form",
                    "show_calls": [
                        {
                            "target": "B",
                            "arg": "vbModal",
                            "show_style": "modal_overlay",
                            "line": 1,
                        }
                    ],
                },
                {
                    "file": "B.frm",
                    "vb_name": "B",
                    "type": "form",
                    "show_calls": [],
                },
            ]
        }
        attach_show_inbound(report)
        b = next(f for f in report["files"] if f["vb_name"] == "B")
        self.assertEqual(b["show_inbound"][0]["from_vb_name"], "A")
        self.assertEqual(report["show_unresolved"], [])


class MdiChildExtractionTests(unittest.TestCase):
    def test_mdi_child_true(self) -> None:
        lines = [
            "VERSION 5.00",
            "Begin VB.Form Form12",
            "   Caption         =   \"x\"",
            "   MDIChild        =   -1  'True",
            "End",
        ]
        form_info, _ = extract_controls(lines)
        self.assertTrue(form_info.get("mdi_child"))
        style = form_show_style_block(form_info)
        self.assertEqual(style["show_style"], "mdi_child")


class ShowMapIntegrationTests(unittest.TestCase):
    def test_events_carry_show_calls(self) -> None:
        lines = [
            'Attribute VB_Name = "Form1"',
            "Option Explicit",
            "Private Sub Command1_Click()",
            "    Form12.Show vbModal",
            "End Sub",
        ]
        events = extract_events(lines)
        for ev in events:
            ev["status"] = "live"
        rows = extract_show_map(events)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shows"], ["Form12"])
        self.assertEqual(rows[0]["calls"][0]["show_style"], "modal_overlay")

    def test_report_includes_show_style_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.md"
            write_report(
                path,
                "T.frm",
                {
                    "name": "Form12",
                    "caption": "t",
                    "kind": "VB.Form",
                    "mdi_child": True,
                },
                [],
                [],
                {},
                [],
                10,
                [],
                [
                    {
                        "sub": "Command1_Click",
                        "line": 5,
                        "shows": ["Form12"],
                        "para_sets": [],
                        "calls": [
                            {
                                "target": "Other",
                                "arg": "vbModal",
                                "show_style": "modal_overlay",
                                "line": 5,
                            }
                        ],
                    }
                ],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("show_style（候補・ヒューリスティック）", text)
        self.assertIn("mdi_child", text)
        self.assertIn("modal_overlay", text)


class ExcerptTests(unittest.TestCase):
    def test_build_lists_unticked(self) -> None:
        inventory = {
            "stem": "demo",
            "proc_total": 1,
            "files": [
                {
                    "file": "Form1.frm",
                    "vb_name": "Form1",
                    "form_kind": "VB.Form",
                    "type": "form",
                    "control_count": 0,
                    "procedures": [
                        {
                            "name": "Form_Load",
                            "role": "event",
                            "line_start": 1,
                            "line_end": 3,
                        }
                    ],
                }
            ],
        }
        html = build_excerpt_html(
            inventory, ticked=set(), show_rows=[], stem="demo"
        )
        self.assertIn("Form1.frm", html)
        self.assertIn("Form_Load", html)
        self.assertIn("未 tick", html)
        self.assertIn("color-scheme: light", html)
        self.assertNotIn("color-scheme: light dark", html)
        self.assertIn("background: #ffffff", html)
        self.assertIn("VB_Name", html)
        self.assertIn("file://", html.lower())

    def test_write_excerpt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            skel = root / "skeletons"
            reports.mkdir()
            skel.mkdir()
            inv = {
                "stem": "demo",
                "proc_total": 0,
                "files": [
                    {
                        "file": "Form1.frm",
                        "vb_name": "Form1",
                        "form_kind": "VB.Form",
                        "type": "form",
                        "control_count": 1,
                        "procedures": [],
                        "lifetime_calls": [
                            {
                                "kind": "unload",
                                "target": "Me",
                                "line": 20,
                                "text": "Unload Me",
                            }
                        ],
                    }
                ],
            }
            inv_path = reports / "demo_inventory.json"
            inv_path.write_text(json.dumps(inv), encoding="utf-8")
            (skel / "form1-skeleton.json").write_text(
                json.dumps(
                    {
                        "form": {"name": "Form1"},
                        "show_style": {
                            "show_style": "unknown",
                            "confidence": "none",
                        },
                        "goto_skipped_stmts": [
                            {
                                "sub": "Form_Load",
                                "stmt_kind": "open",
                                "stmt_line": 12,
                            }
                        ],
                        "goto_label_maps": [
                            {
                                "sub": "Form_Load",
                                "gotos": [{"line": 10, "target": "Done"}],
                            }
                        ],
                        "show_map": [
                            {
                                "sub": "Command1_Click",
                                "line": 10,
                                "shows": ["Form2"],
                                "para_sets": [],
                                "calls": [
                                    {
                                        "target": "Form2",
                                        "arg": "vbModal",
                                        "show_style": "modal_overlay",
                                        "line": 10,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            dest = write_excerpt(
                inventory_path=inv_path, reports=reports, skeletons=skel
            )
            text = dest.read_text(encoding="utf-8")
            self.assertTrue(dest.is_file())
            self.assertIn("modal_overlay", text)
            self.assertIn("Form1", text)
            self.assertIn("1 skip", text)
            self.assertIn("navigate", text)
            self.assertIn("候補", text)
            self.assertIn("unknown", text)
            self.assertIn("Show 文の転置（事実）", text)
            self.assertIn("Unload Me", text)
            counts = load_goto_counts(skel)
            self.assertEqual(counts["Form1"]["skip_stmts"], 1)

    def test_excerpt_inbound_from_inventory_show_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            skel = root / "skeletons"
            reports.mkdir()
            skel.mkdir()
            inv = {
                "stem": "demo",
                "proc_total": 0,
                "files": [
                    {
                        "file": "Form1.frm",
                        "vb_name": "Form1",
                        "form_kind": "VB.Form",
                        "type": "form",
                        "control_count": 0,
                        "procedures": [],
                        "show_style": {"show_style": "unknown"},
                        "show_calls": [
                            {
                                "target": "Form12",
                                "arg": "vbModal",
                                "show_style": "modal_overlay",
                                "line": 8,
                            }
                        ],
                    },
                    {
                        "file": "BackupDay.frm",
                        "vb_name": "Form12",
                        "form_kind": "VB.Form",
                        "type": "form",
                        "control_count": 0,
                        "procedures": [],
                        "show_style": {"show_style": "mdi_child"},
                        "show_calls": [],
                    },
                ],
            }
            inv_path = reports / "demo_inventory.json"
            inv_path.write_text(json.dumps(inv), encoding="utf-8")
            dest = write_excerpt(
                inventory_path=inv_path, reports=reports, skeletons=skel
            )
            text = dest.read_text(encoding="utf-8")
        self.assertIn("Show 文の転置（事実）", text)
        self.assertIn("Form12", text)
        self.assertIn("Form1", text)
        self.assertNotIn("unresolved</h3>", text)
        self.assertIn("Load/Unload 文面", text)

    def test_excerpt_lists_lifetime_calls(self) -> None:
        inventory = {
            "stem": "demo",
            "proc_total": 0,
            "files": [
                {
                    "file": "Form1.frm",
                    "vb_name": "Form1",
                    "form_kind": "VB.Form",
                    "type": "form",
                    "control_count": 0,
                    "procedures": [],
                    "show_style": {"show_style": "unknown"},
                    "show_calls": [],
                    "lifetime_calls": [
                        {
                            "kind": "load",
                            "target": "Form2",
                            "line": 6,
                            "text": "Load Form2",
                        }
                    ],
                }
            ],
        }
        html = build_excerpt_html(
            inventory,
            ticked=set(),
            show_rows=[],
            stem="demo",
            lifetime_rows=[
                {
                    "file": "Form1.frm",
                    "kind": "load",
                    "target": "Form2",
                    "line": 6,
                    "text": "Load Form2",
                }
            ],
        )
        self.assertIn("Load Form2", html)
        self.assertIn("Form2", html)

    def test_excerpt_module_class_surface_and_declare_counts(self) -> None:
        inventory = {
            "stem": "demo",
            "proc_total": 3,
            "files": [
                {
                    "file": "Form1.frm",
                    "vb_name": "Form1",
                    "type": "form",
                    "procedures": [{"name": "Form_Load"}],
                    "declares": [],
                },
                {
                    "file": "Module1.bas",
                    "vb_name": "Module1",
                    "type": "module",
                    "procedures": [
                        {"name": "AddOne"},
                        {"name": "Hidden"},
                    ],
                    "declares": [
                        {"name": "GetTickCount", "kind": "Function", "lib": "kernel32"}
                    ],
                },
                {
                    "file": "Widget.cls",
                    "vb_name": "Widget",
                    "type": "class",
                    "procedures": [
                        {"name": "Ready", "kind": "Property Get", "visibility": "Public"}
                    ],
                    "declares": [],
                    "surface": {
                        "implements": [{"name": "IPing", "line": 12}],
                        "with_events": [
                            {
                                "name": "Bus",
                                "as_type": "AppEvents",
                                "visibility": "Private",
                                "line": 14,
                            }
                        ],
                        "instancing": 5,
                    },
                },
                {
                    "file": "MiniCtl.ctl",
                    "vb_name": "MiniCtl",
                    "type": "usercontrol",
                    "procedures": [{"name": "Ping"}],
                    "declares": [],
                },
            ],
        }
        ticked = {("Module1.bas", "Hidden")}
        rows = module_class_surface(inventory, ticked)
        self.assertEqual([r["file"] for r in rows], ["Module1.bas", "Widget.cls"])
        self.assertEqual(rows[0]["declare_count"], 1)
        self.assertEqual(rows[0]["unticked"], ["AddOne"])
        self.assertEqual(rows[1]["declare_count"], 0)
        self.assertEqual(rows[1]["implements"], ["IPing"])
        self.assertEqual(rows[1]["with_events"], ["Bus"])
        self.assertEqual(rows[1]["instancing"], 5)
        self.assertEqual(rows[1]["public_properties"], 1)
        self.assertEqual(rows[1]["unticked"], ["Ready"])
        html = build_excerpt_html(
            inventory,
            ticked=ticked,
            show_rows=[],
            stem="demo",
        )
        self.assertIn("Module / Class 表面", html)
        self.assertIn("Module1.bas", html)
        self.assertIn("Widget.cls", html)
        self.assertIn("AddOne", html)
        self.assertIn("IPing", html)
        self.assertIn("Bus", html)
        self.assertNotIn("MiniCtl.ctl", html.split("未 tick プロシージャ")[0])
        self.assertNotIn("GetTickCount", html)


class ServeExcerptTests(unittest.TestCase):
    def test_excerpt_path_returns_html(self) -> None:
        from functools import partial
        from http.server import ThreadingHTTPServer
        from threading import Thread
        import urllib.request

        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            inv = {
                "stem": "demo",
                "proc_total": 0,
                "files": [
                    {
                        "file": "Form1.frm",
                        "vb_name": "Form1",
                        "form_kind": "VB.Form",
                        "type": "form",
                        "control_count": 0,
                        "procedures": [],
                        "show_style": {"show_style": "unknown"},
                        "show_calls": [],
                    }
                ],
            }
            (reports / "demo_inventory.json").write_text(
                json.dumps(inv), encoding="utf-8"
            )
            handler = partial(ReportsHandler, directory=str(reports))
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/excerpt?stem=demo", timeout=5
                ) as resp:
                    body = resp.read().decode("utf-8")
                    self.assertEqual(resp.status, 200)
                self.assertIn("再実装向け抜粋", body)
                self.assertIn("Form1", body)
            finally:
                httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
