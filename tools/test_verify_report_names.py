"""Tests for verify_report_names (synthetic inventory + reports)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_report_names as vrn  # noqa: E402


def sample_inventory() -> dict:
    return {
        "stem": "mini",
        "files": [
            {
                "file": "Form1.frm",
                "vb_name": "Form1",
                "procedures": [
                    {"name": "Form_Load", "kind": "Sub"},
                    {"name": "Command1_Click", "kind": "Sub"},
                ],
            },
            {
                "file": "Module1.bas",
                "vb_name": "Module1",
                "procedures": [{"name": "AddOne", "kind": "Function"}],
                "declares": [{"name": "ExtApi", "kind": "Function", "lib": "x.dll"}],
            },
        ],
    }


class LoadSetsTests(unittest.TestCase):
    def test_files_and_procs_normalized(self) -> None:
        files, procs = vrn.load_inventory_sets(sample_inventory())
        self.assertIn("form1.frm", files)
        self.assertIn("form1", files)
        self.assertIn("module1.bas", files)
        self.assertIn("form_load", procs)
        self.assertIn("command1_click", procs)
        self.assertIn("addone", procs)
        self.assertIn("extapi", procs)

    def test_allow_files_from_config(self) -> None:
        with patch(
            "verify_report_names.load_config",
            return_value={"verify_report_allow_files": ["Other.bas", "Legacy.frm"]},
        ):
            files, _procs = vrn.load_inventory_sets(sample_inventory())
        self.assertIn("other.bas", files)
        self.assertIn("other", files)
        self.assertIn("legacy.frm", files)


class ExtractTests(unittest.TestCase):
    def test_extracts_file_and_proc_like_backticks(self) -> None:
        text = (
            "See `Form1.frm` and Sub `Form_Load`. "
            "Also `code_ref` and `ancestor_hidden` must be ignored. "
            "Constants `HWND_TOPMOST` and `SW_SHOW` are not procs. "
            "Audit file `Newprocesskensaku_frm_audit` is not a proc."
        )
        files, procs = vrn.extract_mentions(text)
        self.assertIn("form1.frm", files)
        self.assertIn("form_load", procs)
        self.assertNotIn("code_ref", procs)
        self.assertNotIn("ancestor_hidden", procs)
        self.assertNotIn("hwnd_topmost", procs)
        self.assertNotIn("sw_show", procs)
        self.assertNotIn("newprocesskensaku_frm_audit", procs)

    def test_sub_decl_pattern(self) -> None:
        files, procs = vrn.extract_mentions("Private Sub Ghost_Click()")
        self.assertEqual(files, set())
        self.assertIn("ghost_click", procs)

    def test_exit_sub_and_line_labels_ignored(self) -> None:
        text = "Exit Sub より後か · see Sub L4626 in notes"
        _files, procs = vrn.extract_mentions(text)
        self.assertNotIn("l4626", procs)


class VerifyTests(unittest.TestCase):
    def test_unknown_proc_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv_path = root / "mini_inventory.json"
            inv_path.write_text(
                json.dumps(sample_inventory()), encoding="utf-8"
            )
            bad = root / "note.md"
            bad.write_text(
                "# note\n\nHandler `DoesNotExist_Click` is fictional.\n",
                encoding="utf-8",
            )
            summary = vrn.verify(inv_path, [bad])
            self.assertFalse(summary["ok"])
            self.assertEqual(summary["unknown_proc_count"], 1)
            self.assertEqual(summary["unknown_procs"][0]["name"], "doesnotexist_click")

    def test_known_names_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv_path = root / "mini_inventory.json"
            inv_path.write_text(
                json.dumps(sample_inventory()), encoding="utf-8"
            )
            ok = root / "ok.md"
            ok.write_text(
                "# ok\n\n`Form1.frm` · `Form_Load` · `Command1_Click`\n",
                encoding="utf-8",
            )
            summary = vrn.verify(inv_path, [ok])
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["unknown_file_count"], 0)
            self.assertEqual(summary["unknown_proc_count"], 0)

    def test_cli_fail_and_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv_path = root / "mini_inventory.json"
            inv_path.write_text(
                json.dumps(sample_inventory()), encoding="utf-8"
            )
            bad = root / "bad.md"
            bad.write_text("`Missing_Click` here\n", encoding="utf-8")
            rc = vrn.main(
                ["--inventory", str(inv_path), "--reports", str(bad)]
            )
            self.assertEqual(rc, 1)

            good = root / "good.md"
            good.write_text("`Form_Load` in `Form1.frm`\n", encoding="utf-8")
            rc2 = vrn.main(
                ["--inventory", str(inv_path), "--reports", str(good)]
            )
            self.assertEqual(rc2, 0)


if __name__ == "__main__":
    unittest.main()
