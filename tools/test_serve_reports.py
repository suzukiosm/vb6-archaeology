"""Landing page and static serve for working/reports."""

from __future__ import annotations

import contextlib
import errno
import io
import json
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from tools.serve_reports import (
    FILE_URI_NOTE,
    ReportsHandler,
    bind_reports_server,
    classify_report,
    live_get,
    main as serve_main,
    render_landing,
    serving_announcement,
)


class ClassifyReportTests(unittest.TestCase):
    def test_known_kinds(self) -> None:
        self.assertEqual(classify_report("demo_inventory.html"), "inventory")
        self.assertEqual(classify_report("demo_inventory.JSON"), "inventory")
        self.assertEqual(classify_report("demo_comprehension.html"), "comprehension")
        self.assertEqual(classify_report("demo_reimpl_excerpt.html"), "excerpt")
        self.assertEqual(classify_report("runtime_layout.md"), "layout")
        self.assertEqual(classify_report("form_layout_gap.md"), "layout")
        self.assertEqual(classify_report("demo_io_catalog.md"), "io_catalog")
        self.assertEqual(classify_report("demo_io_catalog.json"), "io_catalog")
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
        self.assertIn("<h2>io-catalog</h2>", html)
        self.assertIn("（なし）", html)
        self.assertNotIn("demo_comprehension.html", html)
        self.assertIn("Reports / レポート", html)
        self.assertIn("color-scheme: light", html)
        self.assertNotIn("color-scheme: light dark", html)
        self.assertIn("background: #ffffff", html)
        self.assertIn("Do not open as file://", html)
        self.assertNotIn("@media (prefers-color-scheme: dark)", html)


class BindReportsServerTests(unittest.TestCase):
    def test_requested_ephemeral_port_is_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handler = partial(ReportsHandler, directory=tmp)
            httpd, bound, fallback_from = bind_reports_server(
                "127.0.0.1", 0, handler
            )
            try:
                self.assertIsNone(fallback_from)
                self.assertGreater(bound, 0)
            finally:
                httpd.server_close()

    def test_falls_back_when_requested_port_is_in_use(self) -> None:
        occupied = 8765
        ephemeral = 18080

        class Fake:
            server_address: tuple[str, int]

            def __init__(self, addr: tuple[str, int], _handler: object) -> None:
                host, port = addr
                if port == occupied:
                    raise OSError(errno.EADDRINUSE, "Address already in use")
                if port == 0:
                    self.server_address = (host, ephemeral)
                    return
                raise AssertionError(f"unexpected port {port}")

            def server_close(self) -> None:
                return

            def serve_forever(self, poll_interval: float = 0.5) -> None:
                return

            def __enter__(self) -> Fake:
                return self

            def __exit__(self, *args: object) -> None:
                return None

        httpd, bound, fallback_from = bind_reports_server(
            "127.0.0.1", occupied, object(), server_class=Fake
        )
        self.assertEqual(bound, ephemeral)
        self.assertEqual(fallback_from, occupied)
        httpd.server_close()

    def test_both_binds_fail_raises(self) -> None:
        class Fake:
            def __init__(self, _addr: object, _handler: object) -> None:
                raise OSError(errno.EADDRINUSE, "Address already in use")

        with self.assertRaises(OSError):
            bind_reports_server(
                "127.0.0.1", 8765, object(), server_class=Fake
            )

    def test_announcement_uses_actual_url_after_fallback(self) -> None:
        lines = serving_announcement(
            root=Path("working/reports"),
            bind="127.0.0.1",
            bound_port=18080,
            fallback_from=8765,
        )
        text = "\n".join(lines)
        self.assertIn("8765", text)
        self.assertIn("http://127.0.0.1:18080/", text)
        self.assertNotIn("http://127.0.0.1:8765/", text)
        self.assertIn("in use", text.lower())

    def test_main_bind_failure_prints_next_command(self) -> None:
        def boom(*_args, **_kwargs):
            raise OSError(errno.EADDRINUSE, "Address already in use")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("x", encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                with patch(
                    "tools.serve_reports.bind_reports_server",
                    side_effect=boom,
                ):
                    code = serve_main(
                        ["--directory", str(root), "--port", "8765"]
                    )
        self.assertEqual(code, 1)
        err_text = err.getvalue()
        self.assertIn("cannot bind", err_text.lower())
        self.assertIn("next:", err_text.lower())
        self.assertIn("python -m tools serve --port", err_text)


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


class LiveGetTests(unittest.TestCase):
    def test_landing_and_excerpt_return_200(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "demo_inventory.json").write_text(
                json.dumps({
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
                }),
                encoding="utf-8",
            )
            result = live_get(reports, timeout=5)
        self.assertTrue(result["ok"])
        paths = {item["path"]: item["status"] for item in result["gets"]}
        self.assertEqual(paths.get("/"), 200)
        self.assertEqual(paths.get("/excerpt"), 200)

    def test_excerpt_without_inventory_is_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "notes.txt").write_text("x", encoding="utf-8")
            result = live_get(reports, timeout=5)
        self.assertFalse(result["ok"])
        excerpt = next(item for item in result["gets"] if item["path"] == "/excerpt")
        self.assertNotEqual(excerpt["status"], 200)


if __name__ == "__main__":
    unittest.main()
