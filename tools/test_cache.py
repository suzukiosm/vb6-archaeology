"""Unit tests for the content-hash parse cache (isolated temp repo root)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cache  # noqa: E402
from lib.config import load_config  # noqa: E402


class ContentKeyTests(unittest.TestCase):
    def test_key_changes_with_content(self) -> None:
        a = cache.content_key(b"hello", "v1")
        b = cache.content_key(b"world", "v1")
        self.assertNotEqual(a, b)

    def test_key_changes_with_version(self) -> None:
        a = cache.content_key(b"hello", "v1")
        b = cache.content_key(b"hello", "v2")
        self.assertNotEqual(a, b)

    def test_same_input_same_key(self) -> None:
        self.assertEqual(
            cache.content_key(b"hello", "v1"), cache.content_key(b"hello", "v1")
        )


class StoreLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        load_config.cache_clear()  # config is lru_cached; isolate temp root
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        load_config.cache_clear()

    def test_roundtrip(self) -> None:
        key = cache.content_key(b"abc", "v1")
        self.assertIsNone(cache.load(key, repo_root=self.root))
        cache.store(key, {"n": 1, "s": "ほげ"}, repo_root=self.root)
        got = cache.load(key, repo_root=self.root)
        self.assertEqual(got, {"n": 1, "s": "ほげ"})

    def test_miss_on_unknown_key(self) -> None:
        self.assertIsNone(cache.load("deadbeef", repo_root=self.root))


if __name__ == "__main__":
    unittest.main()
