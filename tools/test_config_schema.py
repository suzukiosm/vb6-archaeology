"""Config schema validation: the shipped config plus consumer misconfigurations."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config_schema import REPO_ROOT, check_config, validate  # noqa: E402

SCHEMA = json.loads(
    (REPO_ROOT / "schema" / "archaeology.config.schema.json").read_text(encoding="utf-8")
)

VALID = {
    "$schema": "./schema/archaeology.config.schema.json",
    "protected_source_dirs": ["vb6_originals"],
    "default_source_dir": "vb6_originals",
    "extracts_dir": "working/extracts",
    "reports_dir": "working/reports",
    "skeletons_dir": "working/web/src/lib",
    "encoding": "cp932",
    "encoding_fallbacks": ["utf-8-sig"],
    "reports_http_port": 8765,
    "geometry_hints": {"MDIForm1": {"left": 0, "top": 0, "height": 13550, "width": 0}},
    "deep_read_name_map": {"MDIForm1": "mdi"},
    "layout_sub_scores": {"form_load": 80, "stet_click": 75},
    "picture1_height_by_sub": {"hyouji": "Form7"},
    "verify_report_allow_files": ["shared.bas"],
    "notes": {"consumer": "app tree"},
}


def problems(overrides: dict) -> list[str]:
    data = {**VALID, **overrides}
    return validate(data, SCHEMA)


class TestConfigSchema(unittest.TestCase):
    def test_shipped_config_is_valid(self):
        self.assertEqual(check_config(REPO_ROOT / "archaeology.config.json"), [])

    def test_consumer_shaped_config_is_valid(self):
        self.assertEqual(problems({}), [])

    def test_score_map_rejects_string_values(self):
        found = problems({"layout_sub_scores": {"stet_click": "75"}})
        self.assertEqual(len(found), 1)
        self.assertIn("layout_sub_scores.stet_click", found[0])
        self.assertIn("integer", found[0])

    def test_unknown_key_is_reported(self):
        found = problems({"reports_dirs": "working/reports"})
        self.assertTrue(any("reports_dirs" in p for p in found))

    def test_required_keys_are_reported(self):
        data = dict(VALID)
        del data["protected_source_dirs"]
        found = validate(data, SCHEMA)
        self.assertTrue(any("protected_source_dirs" in p for p in found))

    def test_empty_protected_list_is_rejected(self):
        found = problems({"protected_source_dirs": []})
        self.assertTrue(any("at least 1 item" in p for p in found))

    def test_port_out_of_range_is_rejected(self):
        found = problems({"reports_http_port": 70000})
        self.assertTrue(any("<= 65535" in p for p in found))

    def test_invalid_json_reports_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "archaeology.config.json"
            bad.write_text('{"protected_source_dirs": ["source",]}', encoding="utf-8")
            found = check_config(bad)
            self.assertTrue(any("invalid JSON" in p for p in found))


if __name__ == "__main__":
    unittest.main()
