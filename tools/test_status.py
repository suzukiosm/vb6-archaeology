"""Facts-only pipeline status: presence and counts from artifacts on disk."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.lib import config  # noqa: E402
from tools.status import build_status, format_status_lines  # noqa: E402


class TempRepo:
    def __init__(self, data: dict | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        payload = data or {
            "extracts_dir": "working/extracts",
            "reports_dir": "working/reports",
            "skeletons_dir": "working/skeletons",
        }
        (self.root / "archaeology.config.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        (self.root / "working" / "extracts").mkdir(parents=True)
        (self.root / "working" / "reports").mkdir(parents=True)

    def __enter__(self) -> Path:
        config.load_config.cache_clear()
        return self.root

    def __exit__(self, *exc):
        config.load_config.cache_clear()
        self.tmp.cleanup()


def _write_inventory(reports: Path, stem: str, files: list[dict]) -> Path:
    body = {
        "stem": stem,
        "file_count": len(files),
        "proc_total": sum(len(f.get("procedures") or []) for f in files),
        "files": files,
    }
    path = reports / f"{stem}_inventory.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


class TestStatusEmpty(unittest.TestCase):
    def test_empty_repo_is_absent_not_an_error(self):
        with TempRepo() as root:
            data = build_status(root)
        self.assertIsNone(data["stem"])
        self.assertFalse(data["extract"]["present"])
        self.assertEqual(data["extract"]["reason"], "missing")
        self.assertFalse(data["inventory"]["present"])
        self.assertFalse(data["verify"]["persisted"])
        self.assertEqual(data["deep_read"]["reports"], 0)
        self.assertEqual(data["ticks"]["count"], 0)
        self.assertFalse(data["excerpt"]["present"])
        self.assertFalse(data["io_catalog"]["present"])
        lines = format_status_lines(data).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("extract=no", lines[0])
        self.assertIn("verify=not persisted", lines[2])
        self.assertIn("io=no", lines[2])


class TestStatusArtifacts(unittest.TestCase):
    def test_counts_forms_ticks_excerpt_and_verify(self):
        with TempRepo() as root:
            extract = root / "working" / "extracts" / "demo"
            extract.mkdir()
            reports = root / "working" / "reports"
            _write_inventory(
                reports,
                "demo",
                [
                    {
                        "file": "Form1.frm",
                        "type": "form",
                        "vb_name": "Form1",
                        "procedures": [{"name": "Form_Load"}, {"name": "Click"}],
                    },
                    {
                        "file": "Form12.frm",
                        "type": "form",
                        "vb_name": "Form12",
                        "procedures": [{"name": "Load"}],
                    },
                    {
                        "file": "Mod.bas",
                        "type": "module",
                        "vb_name": "Mod",
                        "procedures": [{"name": "Helper"}],
                    },
                ],
            )
            (reports / "form1_deep_read.md").write_text("# Form1\n", encoding="utf-8")
            (reports / "demo_comprehension.html").write_text(
                '<section class="tick" data-tick="1"></section>\n'
                '<section class="tick" data-tick="2"></section>\n',
                encoding="utf-8",
            )
            (reports / "demo_reimpl_excerpt.html").write_text("<html></html>", encoding="utf-8")
            (reports / "demo_verify.json").write_text(
                json.dumps({"ok": True, "mismatches": [], "files_checked": 3}),
                encoding="utf-8",
            )
            (reports / "runtime_layout.md").write_text("# layout\n", encoding="utf-8")
            (reports / "demo_io_catalog.json").write_text(
                json.dumps({"stem": "demo", "entry_count": 0, "entries": []}),
                encoding="utf-8",
            )
            data = build_status(root)

        self.assertEqual(data["stem"], "demo")
        self.assertTrue(data["extract"]["present"])
        self.assertEqual(data["inventory"]["file_count"], 3)
        self.assertEqual(data["inventory"]["proc_total"], 4)
        self.assertEqual(data["inventory"]["form_count"], 2)
        self.assertEqual(data["deep_read"]["reports"], 1)
        self.assertEqual(data["deep_read"]["forms"], 2)
        self.assertEqual(data["deep_read"]["absent"], ["Form12.frm"])
        self.assertEqual(data["ticks"]["count"], 2)
        self.assertTrue(data["excerpt"]["present"])
        self.assertTrue(data["verify"]["persisted"])
        self.assertTrue(data["verify"]["ok"])
        self.assertTrue(data["layout"]["present"])
        self.assertTrue(data["io_catalog"]["present"])
        text = format_status_lines(data)
        self.assertIn("io=yes", text)
        self.assertIn("deep-read=1/2", text)
        self.assertIn("ticks=2/4", text)
        self.assertIn("verify=ok", text)

    def test_deep_read_name_map(self):
        with TempRepo({"extracts_dir": "working/extracts", "reports_dir": "working/reports",
                       "deep_read_name_map": {"Form12": "backupday"}}) as root:
            (root / "working" / "extracts" / "demo").mkdir()
            reports = root / "working" / "reports"
            _write_inventory(
                reports,
                "demo",
                [
                    {
                        "file": "BackupDay.frm",
                        "type": "form",
                        "vb_name": "Form12",
                        "procedures": [],
                    }
                ],
            )
            (reports / "backupday_deep_read.md").write_text("# mapped\n", encoding="utf-8")
            data = build_status(root)
        self.assertEqual(data["deep_read"]["reports"], 1)
        self.assertEqual(data["deep_read"]["absent"], [])

    def test_multiple_extracts_without_default(self):
        with TempRepo() as root:
            (root / "working" / "extracts" / "aaa").mkdir()
            (root / "working" / "extracts" / "bbb").mkdir()
            data = build_status(root)
        self.assertFalse(data["extract"]["present"])
        self.assertEqual(data["extract"]["reason"], "multiple")
        self.assertEqual(data["extract"]["candidates"], ["aaa", "bbb"])
        self.assertIn("multiple:aaa,bbb", format_status_lines(data))

    def test_default_extract_picks_named_folder(self):
        with TempRepo(
            {
                "extracts_dir": "working/extracts",
                "reports_dir": "working/reports",
                "default_extract": "bbb",
            }
        ) as root:
            (root / "working" / "extracts" / "aaa").mkdir()
            (root / "working" / "extracts" / "bbb").mkdir()
            _write_inventory(
                root / "working" / "reports",
                "bbb",
                [{"file": "A.frm", "type": "form", "vb_name": "A", "procedures": []}],
            )
            data = build_status(root)
        self.assertTrue(data["extract"]["present"])
        self.assertEqual(data["extract"]["name"], "bbb")
        self.assertEqual(data["stem"], "bbb")
        self.assertTrue(data["inventory"]["present"])

    def test_explicit_extract_missing_is_reported(self):
        with TempRepo() as root:
            data = build_status(root, extract=Path("working/extracts/nope"))
        self.assertFalse(data["extract"]["present"])
        self.assertEqual(data["extract"]["reason"], "missing")


class TestVerifyPersist(unittest.TestCase):
    def test_verify_writes_stem_verify_json(self):
        import tools.verify_inventory as verify

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extract = root / "ex"
            extract.mkdir()
            (extract / "M.bas").write_bytes(b"Sub Foo()\r\nEnd Sub\r\n")
            reports = root / "rep"
            reports.mkdir()
            inv = {
                "stem": "demo",
                "extract_dir": str(extract),
                "files": [{"file": "M.bas", "procedures": [{"name": "Foo"}]}],
            }
            inv_path = reports / "demo_inventory.json"
            inv_path.write_text(json.dumps(inv), encoding="utf-8")
            saved = verify.reports_root

            def fake_reports(_repo=None):
                return reports

            verify.reports_root = fake_reports
            try:
                code = verify.main([str(inv_path), "--extract", str(extract)])
            finally:
                verify.reports_root = saved
            self.assertEqual(code, 0)
            persisted = json.loads((reports / "demo_verify.json").read_text(encoding="utf-8"))
            self.assertTrue(persisted["ok"])
            self.assertEqual(persisted["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
