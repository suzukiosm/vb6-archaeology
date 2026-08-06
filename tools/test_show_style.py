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
from tools.lib.show_style import classify_show_arg, parse_show_calls_in_line
from tools.reimpl_excerpt import build_excerpt_html, load_goto_counts, write_excerpt
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
            counts = load_goto_counts(skel)
            self.assertEqual(counts["Form1"]["skip_stmts"], 1)


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
