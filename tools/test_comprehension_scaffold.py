"""Comprehension scaffold: inventory-anchored ticks, prose preservation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comprehension_scaffold as cs  # noqa: E402

INVENTORY = {
    "vbp": "source/demo/demo.vbp",
    "stem": "demo",
    "file_count": 2,
    "proc_total": 3,
    "files": [
        {
            "file": "Form1.frm",
            "vb_name": "Form1",
            "procedures": [
                {"name": "Form_Load", "kind": "Sub", "line_start": 10, "line_end": 20},
                {
                    "name": "Command1_Click",
                    "kind": "Sub",
                    "line_start": 22,
                    "line_end": 30,
                },
            ],
        },
        {
            "file": "Form2.frm",
            "vb_name": "Form2",
            "procedures": [
                {"name": "Form_Load", "kind": "Sub", "line_start": 5, "line_end": 9}
            ],
        },
    ],
}

HUMAN_NOTE = "<p>手で書いた読解メモ</p>"


class TestComprehensionScaffold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inventory = root / "demo_inventory.json"
        self.inventory.write_text(
            json.dumps(INVENTORY, ensure_ascii=False), encoding="utf-8"
        )
        self.report = root / "demo_comprehension.html"
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, *extra: str) -> int:
        argv = ["--inventory", str(self.inventory), "--out", str(self.report), *extra]
        with contextlib.redirect_stdout(io.StringIO()):
            return cs.main(argv)

    def read(self) -> str:
        return self.report.read_text(encoding="utf-8")

    def test_skeleton_has_markers_and_layers(self):
        self.assertEqual(self.run_cli(), 0)
        text = self.read()
        self.assertIn(cs.TICKS_BEGIN, text)
        self.assertIn(cs.TICKS_END, text)
        for layer in cs.LAYERS:
            self.assertIn(f'data-layer="{layer}"', text)
        self.assertIn("color-scheme: light", text)
        self.assertNotIn("color-scheme: light dark", text)
        self.assertNotIn("@media (prefers-color-scheme: dark)", text)
        self.assertIn("background: #ffffff", text)
        self.assertIn("Rules / 記入規律", text)

    def test_rerun_preserves_written_prose(self):
        self.run_cli()
        self.report.write_text(
            self.read().replace(cs.TICKS_END, f"{HUMAN_NOTE}\n{cs.TICKS_END}"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_cli(), 0)
        self.assertIn(HUMAN_NOTE, self.read())

    def test_force_rewrites_skeleton(self):
        self.run_cli()
        self.report.write_text(
            self.read().replace(cs.TICKS_END, f"{HUMAN_NOTE}\n{cs.TICKS_END}"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_cli("--force"), 0)
        self.assertNotIn(HUMAN_NOTE, self.read())

    def test_ticks_are_numbered_and_appended_before_marker(self):
        self.run_cli("--add-tick", "Command1_Click")
        self.run_cli("--add-tick", "Form_Load@Form2.frm", "--layer", "C")
        text = self.read()
        self.assertIn('data-tick="1"', text)
        self.assertIn('data-tick="2"', text)
        self.assertIn("Form2.frm L5-9", text)
        self.assertIn("product_ui_notes", text)
        self.assertLess(text.index('data-tick="2"'), text.index(cs.TICKS_END))

    def test_tick_creates_skeleton_when_missing(self):
        self.assertEqual(self.run_cli("--add-tick", "Command1_Click"), 0)
        self.assertIn('data-tick="1"', self.read())

    def test_unknown_procedure_is_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--add-tick", "Bogus_Click")
        self.assertIn("not in the inventory", str(ctx.exception))

    def test_ambiguous_procedure_asks_for_a_file(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--add-tick", "Form_Load")
        message = str(ctx.exception)
        self.assertIn("Form1.frm", message)
        self.assertIn("Form2.frm", message)

    def test_report_without_marker_is_refused(self):
        self.report.write_text("<html>hand written</html>", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--add-tick", "Command1_Click")
        self.assertIn(cs.TICKS_END, str(ctx.exception))


SUGGEST_INVENTORY = {
    "vbp": "source/demo/demo.vbp",
    "stem": "demo",
    "file_count": 3,
    "proc_total": 6,
    "meta": {"Startup": "Form1"},
    "files": [
        {
            "file": "Form1.frm",
            "vb_name": "Form1",
            "type": "form",
            "show_calls": [
                {
                    "target": "Form2",
                    "arg": None,
                    "show_style": "unknown",
                    "line": 12,
                },
                {
                    "target": "MissingForm",
                    "arg": None,
                    "show_style": "unknown",
                    "line": 13,
                },
            ],
            "procedures": [
                {
                    "name": "Form_Load",
                    "kind": "Sub",
                    "visibility": "Public",
                    "line_start": 10,
                    "line_end": 20,
                },
                {
                    "name": "Command1_Click",
                    "kind": "Sub",
                    "visibility": "Public",
                    "line_start": 22,
                    "line_end": 30,
                },
                {
                    "name": "Hidden_Click",
                    "kind": "Sub",
                    "visibility": "Private",
                    "line_start": 32,
                    "line_end": 36,
                },
                {
                    "name": "Helper",
                    "kind": "Function",
                    "visibility": "Public",
                    "line_start": 38,
                    "line_end": 40,
                },
            ],
        },
        {
            "file": "Form2.frm",
            "vb_name": "Form2",
            "type": "form",
            "show_calls": [],
            "procedures": [
                {
                    "name": "Form_Load",
                    "kind": "Sub",
                    "visibility": "Public",
                    "line_start": 5,
                    "line_end": 9,
                }
            ],
        },
        {
            "file": "Module1.bas",
            "vb_name": "Module1",
            "type": "module",
            "procedures": [
                {
                    "name": "PublicWork",
                    "kind": "Sub",
                    "visibility": "Public",
                    "line_start": 1,
                    "line_end": 4,
                }
            ],
        },
    ],
}


class TestUntickedSuggest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inventory = root / "demo_inventory.json"
        self.inventory.write_text(
            json.dumps(SUGGEST_INVENTORY, ensure_ascii=False), encoding="utf-8"
        )
        self.report = root / "demo_comprehension.html"
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, *extra: str) -> tuple[int, str]:
        argv = ["--inventory", str(self.inventory), "--out", str(self.report), *extra]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cs.main(argv)
        return code, buf.getvalue()

    def test_unticked_lists_inventory_order_without_writing(self):
        code, out = self.run_cli("--unticked")
        self.assertEqual(code, 0)
        self.assertFalse(self.report.exists())
        self.assertEqual(
            [line for line in out.splitlines() if line],
            [
                "Form1.frm#Form_Load",
                "Form1.frm#Command1_Click",
                "Form1.frm#Hidden_Click",
                "Form1.frm#Helper",
                "Form2.frm#Form_Load",
                "Module1.bas#PublicWork",
            ],
        )

    def test_suggest_order_skips_unresolved_and_non_public_sub(self):
        code, out = self.run_cli("--suggest")
        self.assertEqual(code, 0)
        self.assertFalse(self.report.exists())
        lines = [line for line in out.splitlines() if line]
        self.assertEqual(lines[0], cs.SUGGEST_CAPTION)
        self.assertEqual(
            lines[1:],
            [
                f"{cs.SUGGEST_REASON_STARTUP}\tForm1.frm#Form_Load",
                f"{cs.SUGGEST_REASON_SHOW_TARGET}\tForm2.frm#Form_Load",
                f"{cs.SUGGEST_REASON_PUBLIC_SUB}\tForm1.frm#Command1_Click",
                f"{cs.SUGGEST_REASON_PUBLIC_SUB}\tModule1.bas#PublicWork",
            ],
        )
        self.assertNotIn("MissingForm", out)
        self.assertNotIn("Hidden_Click", out)
        self.assertNotIn("Helper", out)

    def test_ticked_procedure_drops_from_unticked(self):
        self.assertEqual(self.run_cli("--add-tick", "Form_Load@Form1.frm")[0], 0)
        before = self.report.read_text(encoding="utf-8")
        code, out = self.run_cli("--unticked")
        self.assertEqual(code, 0)
        self.assertNotIn("Form1.frm#Form_Load", out)
        self.assertIn("Form2.frm#Form_Load", out)
        self.assertEqual(self.report.read_text(encoding="utf-8"), before)

    def test_empty_prints_zero_only(self):
        empty = {
            "stem": "empty",
            "files": [],
            "proc_total": 0,
            "meta": {},
        }
        self.inventory.write_text(json.dumps(empty), encoding="utf-8")
        code, out = self.run_cli("--unticked", "--suggest")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "未 tick 0")
        self.assertFalse(self.report.exists())

    def test_json_only_and_flag_conflicts(self):
        code, out = self.run_cli("--unticked", "--suggest", "--json-only")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(len(payload["unticked"]), 6)
        self.assertEqual(
            [row["reason"] for row in payload["suggest"]],
            [
                cs.SUGGEST_REASON_STARTUP,
                cs.SUGGEST_REASON_SHOW_TARGET,
                cs.SUGGEST_REASON_PUBLIC_SUB,
                cs.SUGGEST_REASON_PUBLIC_SUB,
            ],
        )
        self.assertEqual(payload["caption"], cs.SUGGEST_CAPTION)
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--json-only")
        self.assertIn("--unticked", str(ctx.exception))
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--add-tick", "Command1_Click", "--unticked")
        self.assertIn("--add-tick", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
