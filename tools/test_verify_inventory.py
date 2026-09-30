"""Unit tests for verify_inventory.count_ends (synthetic; no originals)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import contextlib
import io
import json
from unittest.mock import patch

from tools import verify_inventory as verify
from tools.vb6_inventory import build_report, parse_procedures
from tools.verify_inventory import count_ends, duplicate_procedures, span_problems


class CountEndsTests(unittest.TestCase):
    def _write(self, src: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Module1.bas"
            path.write_text(src, encoding="ascii")
            return count_ends(path)

    def test_line_start_end_sub(self) -> None:
        src = "Public Sub Alpha()\n    x = 1\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_end_after_colon_is_counted(self) -> None:
        src = "Public Sub Alpha()\n    x = 1: End Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_label_is_not_an_end(self) -> None:
        src = "Public Sub Alpha()\nFoo:\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_rem_end_is_not_counted(self) -> None:
        src = "Public Sub Alpha()\n    Rem End Sub\nEnd Sub\n"
        self.assertEqual(self._write(src), 1)

    def test_usual_two_procs_match_line_start_ends(self) -> None:
        src = (
            "Public Sub Alpha()\n"
            "    x = 1\n"
            "End Sub\n"
            "Private Function Beta() As Long\n"
            "    Beta = 1\n"
            "End Function\n"
        )
        self.assertEqual(self._write(src), 2)

    def test_colon_end_matches_parse_procedures(self) -> None:
        src = "Attribute VB_Name = \"M\"\nPublic Sub Alpha()\n    x = 1: End Sub\n"
        procs, _ = parse_procedures(src.splitlines())
        self.assertEqual(len(procs), 1)
        self.assertNotIn("unterminated", procs[0])
        self.assertEqual(self._write(src), len(procs))


class IndependentCheckTests(unittest.TestCase):
    def run_verify(self, sources: dict[str, str], inventory_edit=None) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vbp = "Type=Exe\n" + "".join(f"Module={Path(n).stem}; {n}\n" for n in sources)
            (root / "P.vbp").write_text(vbp, encoding="ascii")
            for name, text in sources.items():
                (root / name).write_text(text, encoding="ascii")
            data = build_report(root, root / "P.vbp", use_cache=False)
            if inventory_edit:
                inventory_edit(data)
            inv = root / "P_inventory.json"
            inv.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(verify, "reports_root", return_value=root), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = verify.main([str(inv)])
            return code, json.loads((root / "P_verify.json").read_text(encoding="utf-8"))

    def test_clean_module_has_no_warnings(self) -> None:
        code, result = self.run_verify({"M.bas": 'Attribute VB_Name = "M"\nPublic Sub A()\nEnd Sub\n'})
        self.assertEqual((code, result["warnings"]), (0, []))

    def test_plain_count_flags_a_procedure_the_inventory_lost(self) -> None:
        def drop(data):
            data["files"][0]["procedures"] = data["files"][0]["procedures"][:1]

        code, result = self.run_verify(
            {"M.bas": 'Attribute VB_Name = "M"\nSub A()\nEnd Sub\nSub B()\nEnd Sub\n'}, drop)
        self.assertEqual(code, 1)
        self.assertIn({"file": "M.bas", "kind": "independent_header_count",
                       "procedures": 1, "raw_headers": 2}, result["warnings"])

    def test_if_branch_duplicates_warn(self) -> None:
        code, result = self.run_verify({"M.bas": 'Attribute VB_Name = "M"\n#If X Then\nSub Log()\nEnd Sub\n'
                                                 "#Else\nSub Log()\nEnd Sub\n#End If\n"})
        self.assertEqual(code, 0)
        self.assertEqual([w["kind"] for w in result["warnings"]], ["duplicate_procedure"])

    def test_overlapping_spans_fail(self) -> None:
        def overlap(data):
            data["files"][0]["procedures"][0]["line_end"] = 6

        code, result = self.run_verify(
            {"M.bas": 'Attribute VB_Name = "M"\nSub A()\nEnd Sub\nSub B()\nEnd Sub\n'}, overlap)
        self.assertEqual(code, 1)
        self.assertEqual(result["mismatches"][0]["error"], "overlapping spans")

    def test_helpers(self) -> None:
        procs = [{"name": "A", "kind": "Sub", "line_start": 5, "line_end": 3}]
        self.assertEqual(span_problems("M.bas", procs)[0]["error"], "inverted span")
        self.assertEqual(duplicate_procedures("M.bas", procs * 2)[0]["lines"], [5, 5])


if __name__ == "__main__":
    unittest.main()
