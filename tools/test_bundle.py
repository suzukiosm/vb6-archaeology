"""Context bundle from the AI index, and `lines --proc` (synthetic VB6)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import bundle, frm_lines
from tools.index_build import build_index, write_index
from tools.test_index_build import SOURCES
from tools.vb6_inventory import build_report


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        src = cls.root / "src"
        src.mkdir()
        for name, text in SOURCES.items():
            (src / name).write_bytes(text.encode("cp932"))
        inventory = build_report(src, src / "P.vbp", use_cache=False)
        cls.index_dir = cls.root / "index"
        write_index(build_index(inventory, src), cls.index_dir)
        cls.index = bundle.load_index(cls.index_dir)
        cls.src = src

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def target(self, name: str, file: str | None = None) -> dict:
        return bundle.find_target(self.index["symbols"], name, file, None)

    def test_sections_in_priority_order(self) -> None:
        got = bundle.build_bundle(self.index, self.target("cmdGo_Click"), budget=5000)
        titles = [s["title"] for s in got["sections"]]
        self.assertEqual(titles[0], "Procedure Form1.frm#Sub:cmdGo_Click")
        self.assertEqual(titles[1:4], ["VB6 notes", "Effects (facts)",
                                       "Outbound references (resolved candidates)"])
        self.assertIn("Designer Form1.frm", titles)
        self.assertIn("Referenced procedure Main.bas#Sub:Boot", titles)
        self.assertEqual(got["omitted"], [])

    def test_small_budget_keeps_the_code_and_lists_omissions(self) -> None:
        got = bundle.build_bundle(self.index, self.target("cmdGo_Click"), budget=10)
        self.assertEqual([s["title"] for s in got["sections"]], ["Procedure Form1.frm#Sub:cmdGo_Click"])
        self.assertIn("VB6 notes", got["omitted"])
        self.assertIn("Omitted (budget)", bundle.render_markdown(got))

    def test_inbound_candidates_for_a_module_procedure(self) -> None:
        got = bundle.build_bundle(self.index, self.target("Boot"), budget=5000)
        inbound = next(s for s in got["sections"] if s["title"] == "Inbound reference candidates")
        self.assertIn("Form1.frm:10 in Form1.frm#Sub:cmdGo_Click (head, global, unique)", inbound["body"])

    def test_ambiguous_name_needs_a_file(self) -> None:
        with self.assertRaisesRegex(SystemExit, "several procedures"):
            self.target("Refresh2")
        self.assertEqual(self.target("Refresh2", "Form2.frm")["id"], "Form2.frm#Sub:Refresh2")

    def test_cli_json(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bundle.main(["Twice@Main.bas", "--index", str(self.index_dir), "--json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["target"], "Main.bas#Function:Twice")
        self.assertLessEqual(data["tokens_est"], data["budget"])

    def test_lines_proc_prints_only_that_procedure(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = frm_lines.main([str(self.src / "Main.bas"), "--proc", "twice"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("# Function Twice", out)
        self.assertIn("17 Public Function Twice(x) As Long", out)
        self.assertNotIn("Public Sub Boot", out)


if __name__ == "__main__":
    unittest.main()
