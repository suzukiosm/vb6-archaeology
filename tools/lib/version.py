"""Version contract: package __version__ matches the latest CHANGELOG tag."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHANGELOG = REPO / "CHANGELOG.md"

# Keep a Changelog dated heading, e.g. "## [0.2.0] - 2026-08-16"
_TAG_HEADING = re.compile(
    r"^## \[(\d+\.\d+\.\d+)\](?:\s+-\s+\d{4}-\d{2}-\d{2})?\s*$"
)


def changelog_latest_version(text: str) -> str:
    """Return the first dated version heading. ``[Unreleased]`` is skipped."""
    for line in text.splitlines():
        match = _TAG_HEADING.match(line.strip())
        if match:
            return match.group(1)
    raise ValueError("CHANGELOG.md has no dated version heading (e.g. ## [0.2.0] - YYYY-MM-DD)")


def changelog_latest_version_from_file(path: Path | None = None) -> str:
    """Read CHANGELOG.md (UTF-8) and return the latest tagged version."""
    target = path or CHANGELOG
    return changelog_latest_version(target.read_text(encoding="utf-8"))
