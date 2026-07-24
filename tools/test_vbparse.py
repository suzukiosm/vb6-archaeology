"""Unit tests for lib.vbparse logical-line folding (synthetic input; no originals)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.vbparse import iter_logical_lines  # noqa: E402


class LogicalLineTests(unittest.TestCase):
    def test_plain_lines_map_one_to_one(self) -> None:
        lines = ["A = 1", "B = 2", "C = 3"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 3)
        for i, ll in enumerate(out, start=1):
            self.assertEqual(ll.phys_start, i)
            self.assertEqual(ll.phys_end, i)

    def test_continuation_is_folded_but_span_preserved(self) -> None:
        lines = [
            'Declare Function Foo Lib "k32" ( _',
            "    ByVal a As Long, _",
            "    ByVal b As Long) As Long",
            "X = 1",
        ]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 2)
        first = out[0]
        self.assertEqual(first.phys_start, 1)
        self.assertEqual(first.phys_end, 3)
        self.assertIn('Lib "k32"', first.text)
        self.assertIn("ByVal b As Long) As Long", first.text)
        self.assertEqual(out[1].phys_start, 4)

    def test_trailing_identifier_underscore_is_not_continuation(self) -> None:
        # "my_var" ends in underscore but has no preceding whitespace -> not a cont.
        lines = ["Dim my_var", "Y = 2"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 2)

    def test_dangling_continuation_does_not_crash(self) -> None:
        lines = ["Foo = 1 _"]
        out = iter_logical_lines(lines)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].phys_start, 1)


if __name__ == "__main__":
    unittest.main()
