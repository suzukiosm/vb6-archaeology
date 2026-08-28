"""inventory vs deep-read show_style: warn, do not pick a winner."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.verify_show import (  # noqa: E402
    compare_form,
    compare_inventory,
    flatten_show_map,
    format_summary,
)


def _form(
    *,
    file: str = "Form1.frm",
    vb_name: str = "Form1",
    style: str = "unknown",
    calls: list[dict] | None = None,
) -> dict:
    return {
        "file": file,
        "vb_name": vb_name,
        "type": "form",
        "show_style": {"show_style": style},
        "show_calls": calls or [],
    }


def _skel(*, style: str = "unknown", calls: list[dict] | None = None) -> dict:
    rows = []
    if calls:
        rows.append({"sub": "Command1_Click", "calls": calls})
    return {"show_style": {"show_style": style}, "show_map": rows}


class FlattenTests(unittest.TestCase):
    def test_attaches_sub(self):
        flat = flatten_show_map(
            {
                "show_map": [
                    {
                        "sub": "Command1_Click",
                        "calls": [{"target": "Form12", "line": 10, "show_style": "modal_overlay"}],
                    }
                ]
            }
        )
        self.assertEqual(flat[0]["sub"], "Command1_Click")
        self.assertEqual(flat[0]["target"], "Form12")


class CompareFormTests(unittest.TestCase):
    def test_match_is_empty(self):
        call = {
            "target": "Form12",
            "arg": "vbModal",
            "show_style": "modal_overlay",
            "line": 10,
        }
        self.assertEqual(
            compare_form(_form(style="mdi_child", calls=[call]), _skel(style="mdi_child", calls=[call])),
            [],
        )

    def test_self_style_is_hard(self):
        findings = compare_form(_form(style="unknown"), _skel(style="mdi_child"))
        self.assertEqual(findings[0]["kind"], "self_style")
        self.assertEqual(findings[0]["inventory"], "unknown")
        self.assertEqual(findings[0]["deep_read"], "mdi_child")

    def test_inventory_only_is_warning_kind(self):
        call = {"target": "Form12", "show_style": "unknown", "line": 20}
        findings = compare_form(_form(calls=[call]), _skel())
        self.assertEqual(findings[0]["kind"], "inventory_only")
        self.assertEqual(findings[0]["line"], 20)

    def test_call_style_is_hard(self):
        inv = {"target": "Form12", "show_style": "modal_overlay", "line": 10}
        dr = {"target": "Form12", "show_style": "unknown", "line": 10}
        findings = compare_form(_form(calls=[inv]), _skel(calls=[dr]))
        self.assertEqual(findings[0]["kind"], "call_style")

    def test_deep_read_only_is_hard(self):
        call = {"target": "Ghost", "show_style": "unknown", "line": 3}
        findings = compare_form(_form(), _skel(calls=[call]))
        self.assertEqual(findings[0]["kind"], "deep_read_only")

    def test_missing_skeleton(self):
        findings = compare_form(_form(), None)
        self.assertEqual(findings[0]["kind"], "missing_skeleton")

    def test_me_show_is_excluded_from_compare(self):
        me = {"target": "Me", "show_style": "unknown", "line": 4}
        findings = compare_form(_form(calls=[me]), _skel())
        self.assertEqual(findings, [])
        findings_both = compare_form(_form(), _skel(calls=[me]))
        self.assertEqual(findings_both, [])
        self.assertNotIn("self_style", [f["kind"] for f in findings])
        self.assertNotIn("deep_read_only", [f["kind"] for f in findings_both])

    def test_empty_target_show_is_excluded_from_compare(self):
        bare = {"target": "", "show_style": "modal_overlay", "line": 5}
        self.assertEqual(compare_form(_form(calls=[bare]), _skel()), [])


class CompareInventoryTests(unittest.TestCase):
    def test_ok_with_inventory_only_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            skel_dir = Path(tmp)
            (skel_dir / "form1-skeleton.json").write_text(
                json.dumps(_skel()), encoding="utf-8"
            )
            data = {
                "stem": "demo",
                "files": [
                    _form(calls=[{"target": "Form12", "show_style": "unknown", "line": 9}]),
                    {"file": "Mod.bas", "type": "module"},
                ],
            }
            result = compare_inventory(data, skel_dir, {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["warning_count"], 1)
        self.assertEqual(result["hard_count"], 0)
        self.assertIn("warnings=1", format_summary(result))

    def test_hard_mismatch_is_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            skel_dir = Path(tmp)
            (skel_dir / "form1-skeleton.json").write_text(
                json.dumps(_skel(style="mdi_child")), encoding="utf-8"
            )
            result = compare_inventory({"files": [_form(style="unknown")]}, skel_dir, {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["hard_count"], 1)
        self.assertIn("FOUND", format_summary(result))

    def test_name_map_locates_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            skel_dir = Path(tmp)
            (skel_dir / "backupday-skeleton.json").write_text(
                json.dumps(_skel(style="mdi_child")), encoding="utf-8"
            )
            data = {
                "files": [
                    _form(file="BackupDay.frm", vb_name="Form12", style="mdi_child"),
                ]
            }
            result = compare_inventory(data, skel_dir, {"Form12": "backupday"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["compared"], 1)
        self.assertEqual(result["findings"], [])


if __name__ == "__main__":
    unittest.main()
