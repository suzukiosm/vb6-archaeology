"""Landing page and static serve for working/reports."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from tools.serve_reports import (
    FILE_URI_NOTE,
    ReportsHandler,
    classify_report,
    render_landing,
)


class ClassifyReportTests(unittest.TestCase):
    def test_known_kinds(self) -> None:
        self.assertEqual(classify_report("demo_inventory.html"), "inventory")
        self.assertEqual(classify_report("demo_inventory.JSON"), "inventory")
        self.assertEqual(classify_report("demo_comprehension.html"), "comprehension")
        self.assertEqual(classify_report("demo_reimpl_excerpt.html"), "excerpt")
        self.assertEqual(classify_report("runtime_layout.md"), "layout")
        self.assertEqual(classify_report("form_layout_gap.md"), "layout")
        self.assertEqual(classify_report("form1_deep_read.md"), "deep_read")
        self.assertIsNone(classify_report("demo_verify.json"))
        self.assertIsNone(classify_report("notes.txt"))

    def test_landing_lists_existing_and_marks_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo_inventory.html").write_text("<html></html>", encoding="utf-8")
            (root / "form1_deep_read.md").write_text("# f\n", encoding="utf-8")
            (root / "notes.txt").write_text("x", encoding="utf-8")
            html = render_landing(root)
        self.assertIn(FILE_URI_NOTE, html)
        self.assertIn('href="/excerpt"', html)
        self.assertIn("demo_inventory.html", html)
        self.assertIn("form1_deep_read.md", html)
        self.assertIn("notes.txt", html)
        self.assertIn("<h2>comprehension</h2>", html)
        self.assertIn("<h2>layout</h2>", html)
        self.assertIn("（なし）", html)
        self.assertNotIn("demo_comprehension.html", html)


class ServeLandingTests(unittest.TestCase):
    def test_root_is_landing_and_files_still_served(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "demo_inventory.html").write_text(
                "<html>inventory-ok</html>", encoding="utf-8"
            )
            (reports / "demo_inventory.json").write_text(
                json.dumps({"stem": "demo", "files": [], "proc_total": 0}),
                encoding="utf-8",
            )
            handler = partial(ReportsHandler, directory=str(reports))
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=5
                ) as resp:
                    landing = resp.read().decode("utf-8")
                    self.assertEqual(resp.status, 200)
                self.assertIn("demo_inventory.html", landing)
                self.assertIn("/excerpt", landing)
                self.assertIn(FILE_URI_NOTE, landing)
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/demo_inventory.html", timeout=5
                ) as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertIn("inventory-ok", resp.read().decode("utf-8"))
            finally:
                httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
