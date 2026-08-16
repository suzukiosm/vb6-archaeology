"""__version__ must match the latest dated heading in CHANGELOG.md."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import __version__  # noqa: E402
from tools.lib.version import (  # noqa: E402
    changelog_latest_version,
    changelog_latest_version_from_file,
)

REPO = Path(__file__).resolve().parents[1]


class ChangelogVersionTests(unittest.TestCase):
    def test_skips_unreleased_and_returns_first_tag(self):
        text = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n\n"
            "## [0.2.0] - 2026-08-16\n\n"
            "## [0.1.0] - 2026-08-05\n"
        )
        self.assertEqual(changelog_latest_version(text), "0.2.0")

    def test_accepts_heading_without_date(self):
        self.assertEqual(changelog_latest_version("## [1.4.0]\n"), "1.4.0")

    def test_raises_when_only_unreleased(self):
        with self.assertRaises(ValueError):
            changelog_latest_version("## [Unreleased]\n\n- something\n")

    def test_package_version_matches_changelog(self):
        tagged = changelog_latest_version_from_file(REPO / "CHANGELOG.md")
        self.assertEqual(
            __version__,
            tagged,
            f"tools.__version__ ({__version__}) != CHANGELOG latest tag ({tagged})",
        )


if __name__ == "__main__":
    unittest.main()
