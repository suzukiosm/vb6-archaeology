"""kit-improvement-ideas.md is the backlog of record."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ideas import format_ideas, parse_ideas  # noqa: E402

SAMPLE = """\
# キット改良アイデア

## 0. やらない（既存方針の再確認）

| 対象 | 理由 |
|---|---|
| 完全グラフ | 推定になる |
| Next.js | キット外 |

## 1. 今ある穴（事実）

| # | 穴 | 根拠 |
|---|---|---|
| F1 | ~~extract だけ~~ **採用済 2026-08-16** | parse_vbp |
| F3 | `.cls` に表面レポートが無い | frm_deep_read |

## 2. 優先提案

#### A. inventory — **採用済 2026-08-16**

done

#### Q. leftover idea

still open

## 3. 後回しでよい

| 案 | 理由 |
|---|---|
| `.vbg` | 需要が無い |

## 4. 採用の進め方

ignore
"""


class IdeasParseTests(unittest.TestCase):
    def test_splits_open_adopted_deferred_wont(self):
        data = parse_ideas(SAMPLE)
        self.assertEqual([r["id"] for r in data["holes_open"]], ["F3"])
        self.assertEqual([r["id"] for r in data["holes_adopted"]], ["F1"])
        self.assertEqual([r["id"] for r in data["proposals_open"]], ["Q"])
        self.assertEqual([r["id"] for r in data["proposals_adopted"]], ["A"])
        self.assertEqual(data["deferred"][0]["id"], ".vbg")
        self.assertNotIn("`", data["deferred"][0]["id"])
        self.assertEqual(len(data["wont"]), 2)
        text = format_ideas(data)
        self.assertIn("open holes=1 (F3)", text)
        self.assertIn("open proposals=1 (Q)", text)


class IdeasFileTests(unittest.TestCase):
    def test_repo_ideas_file_parses(self):
        path = Path(__file__).resolve().parents[1] / "docs" / "kit-improvement-ideas.md"
        data = parse_ideas(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["holes_adopted"]), 1)
        self.assertGreaterEqual(len(data["wont"]), 1)
        self.assertEqual(data["holes_open"], [])
        self.assertEqual(data["proposals_open"], [])


if __name__ == "__main__":
    unittest.main()
