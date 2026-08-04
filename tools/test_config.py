"""Config resolution, including repos whose VB6 originals live outside them."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config  # noqa: E402

OFF_REPO = {
    "protected_source_dirs": [],
    "protected_path_markers": ["アイコー"],
    "default_source_dir": "",
}


class TempRepo:
    """A repo root carrying just archaeology.config.json."""

    def __init__(self, data: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "archaeology.config.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def __enter__(self) -> Path:
        config.load_config.cache_clear()
        return self.root

    def __exit__(self, *exc):
        config.load_config.cache_clear()
        self.tmp.cleanup()


class TestOffRepoOriginals(unittest.TestCase):
    def test_empty_protected_list_is_not_replaced_by_the_default(self):
        with TempRepo(OFF_REPO) as root:
            self.assertEqual(config.protected_dir_names(root), [])

    def test_missing_key_still_falls_back_to_source(self):
        with TempRepo({"default_source_dir": "source"}) as root:
            self.assertEqual(config.protected_dir_names(root), ["source"])

    def test_markers_are_read_from_config(self):
        with TempRepo(OFF_REPO) as root:
            self.assertEqual(config.protected_path_markers(root), ["アイコー"])

    def test_marker_matches_a_path_segment_anywhere(self):
        with TempRepo(OFF_REPO) as root:
            hit = config.path_hits_protected_marker(
                r"Z:\_Python\VB6_source\アイコー\納品書.vbp", root
            )
            self.assertEqual(hit, "アイコー")

    def test_marker_does_not_match_a_substring(self):
        with TempRepo(OFF_REPO) as root:
            self.assertIsNone(
                config.path_hits_protected_marker("working/アイコー_notes/x.md", root)
            )

    def test_source_root_falls_back_when_nothing_is_in_repo(self):
        with TempRepo(OFF_REPO) as root:
            fallback = root / "elsewhere"
            fallback.mkdir()
            self.assertEqual(
                config.default_source_root(root, fallback=fallback), fallback.resolve()
            )

    def test_source_root_error_points_at_markers(self):
        with TempRepo(OFF_REPO) as root:
            with self.assertRaises(SystemExit) as ctx:
                config.default_source_root(root)
            self.assertIn("protected_path_markers", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
