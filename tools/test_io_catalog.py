"""Extract-wide I/O catalog: kinds, ignores, GoTo-skip attach."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.io_catalog import (
    attach_goto_skips,
    build_catalog,
    classify_io_statement,
    load_goto_skip_index,
    path_fragment,
    render_markdown,
    scan_source_text,
)


class ClassifyIoTests(unittest.TestCase):
    def test_five_kinds(self) -> None:
        self.assertEqual(
            classify_io_statement('Open "tmp.dat" For Output As #1'),
            "open",
        )
        self.assertEqual(classify_io_statement('Kill "tmp.bak"'), "kill")
        self.assertEqual(classify_io_statement('Call Kill "tmp.bak"'), "kill")
        self.assertEqual(
            classify_io_statement('Name "tmp.dat" As "tmp.bak"'),
            "name",
        )
        self.assertEqual(classify_io_statement("Get #1, , n"), "get")
        self.assertEqual(classify_io_statement("Put #1, , n"), "put")

    def test_ignores_comments_and_lookalikes(self) -> None:
        self.assertIsNone(classify_io_statement("' Open x As #1"))
        self.assertIsNone(classify_io_statement("Public Declare Function GetTickCount Lib \"k\" () As Long"))
        self.assertIsNone(classify_io_statement('Name = "caption"'))
        self.assertIsNone(classify_io_statement('Me.Name = "x"'))
        self.assertIsNone(classify_io_statement("Attribute VB_Name = \"Module1\""))
        self.assertIsNone(classify_io_statement("Close #1"))

    def test_open_variable_channel(self) -> None:
        self.assertEqual(
            classify_io_statement("Open App.Path & \"\\x.dat\" For Binary As #fn"),
            "open",
        )

    def test_path_fragment_prefers_file_like_quote(self) -> None:
        self.assertEqual(
            path_fragment('Open "tmp.dat" For Output As #1'),
            "tmp.dat",
        )
        self.assertEqual(path_fragment("Get #1, , n"), "")


class ScanLogicalLineTests(unittest.TestCase):
    def test_continuation_keeps_phys_start(self) -> None:
        text = (
            "Option Explicit\n"
            "Open \"tmp.dat\" _\n"
            "    For Output As #1\n"
        )
        entries = scan_source_text(text, "Module1.bas")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "open")
        self.assertEqual(entries[0]["line"], 2)
        self.assertEqual(entries[0]["file"], "Module1.bas")
        self.assertEqual(entries[0]["path_fragment"], "tmp.dat")

    def test_two_verbs_on_one_physical_line(self) -> None:
        text = 'Open "tmp.dat" For Output As #1: Kill "tmp.dat"\n'
        entries = scan_source_text(text, "Module1.bas")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["kind"], "open")
        self.assertEqual(entries[1]["kind"], "kill")
        self.assertEqual(entries[0]["line"], 1)
        self.assertEqual(entries[1]["line"], 1)
        self.assertEqual(entries[0]["file"], "Module1.bas")

    def test_label_is_not_classified_as_kill(self) -> None:
        text = "Kill:\n    x = 1\n"
        entries = scan_source_text(text, "Module1.bas")
        self.assertEqual(entries, [])


class GotoSkipAttachTests(unittest.TestCase):
    def test_attaches_same_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skel_dir = Path(tmp)
            (skel_dir / "form1-skeleton.json").write_text(
                json.dumps({
                    "form": {"name": "Form1"},
                    "goto_skipped_stmts": [
                        {
                            "sub": "Form_Load",
                            "goto_line": 10,
                            "label": "AfterOpen",
                            "stmt_line": 12,
                            "stmt_kind": "open",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            index = load_goto_skip_index(skel_dir, {"form1": "Form1.frm"})
            entries = [
                {
                    "file": "Form1.frm",
                    "line": 12,
                    "kind": "open",
                    "text": 'Open "skip.dat" For Input As #2',
                    "path_fragment": "skip.dat",
                    "goto_skip": None,
                },
                {
                    "file": "Module1.bas",
                    "line": 20,
                    "kind": "kill",
                    "text": 'Kill "tmp.bak"',
                    "path_fragment": "tmp.bak",
                    "goto_skip": None,
                },
            ]
            attach_goto_skips(entries, index)
        self.assertEqual(entries[0]["goto_skip"]["sub"], "Form_Load")
        self.assertEqual(entries[0]["goto_skip"]["goto_line"], 10)
        self.assertEqual(entries[0]["goto_skip"]["label"], "AfterOpen")
        self.assertIsNone(entries[1]["goto_skip"])

    def test_empty_extract_is_zero_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp) / "empty"
            extract.mkdir()
            data = build_catalog(extract, skeletons_dir=extract, repo_root=Path(tmp))
        self.assertEqual(data["entry_count"], 0)
        self.assertEqual(data["kind_counts"]["open"], 0)
        md = render_markdown(data)
        self.assertIn("件数: 0", md)


class CatalogExtractTests(unittest.TestCase):
    def test_scans_bas_and_attaches_form_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extract = root / "demo"
            extract.mkdir()
            (extract / "Module1.bas").write_text(
                'Attribute VB_Name = "Module1"\n'
                "Option Explicit\n"
                "Public Sub IoDemo()\n"
                '    Open "tmp.dat" For Output As #1\n'
                "    Put #1, , n\n"
                "    Get #1, , n\n"
                '    Name "tmp.dat" As "tmp.bak"\n'
                '    Kill "tmp.bak"\n'
                "End Sub\n",
                encoding="utf-8",
            )
            (extract / "Form1.frm").write_text(
                'Attribute VB_Name = "Form1"\n'
                "Private Sub Form_Load()\n"
                "    GoTo AfterOpen\n"
                '    Open "skip.dat" For Input As #2\n'
                "AfterOpen:\n"
                "End Sub\n",
                encoding="utf-8",
            )
            skel = root / "skeletons"
            skel.mkdir()
            (skel / "form1-skeleton.json").write_text(
                json.dumps({
                    "form": {"name": "Form1"},
                    "goto_skipped_stmts": [
                        {
                            "sub": "Form_Load",
                            "goto_line": 3,
                            "label": "AfterOpen",
                            "stmt_line": 4,
                            "stmt_kind": "open",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            data = build_catalog(extract, skeletons_dir=skel, repo_root=root)

        kinds = [e["kind"] for e in data["entries"]]
        self.assertEqual(kinds.count("open"), 2)
        self.assertEqual(kinds.count("kill"), 1)
        self.assertEqual(kinds.count("name"), 1)
        self.assertEqual(kinds.count("get"), 1)
        self.assertEqual(kinds.count("put"), 1)
        skipped = [e for e in data["entries"] if e["goto_skip"]]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["file"], "Form1.frm")
        self.assertEqual(skipped[0]["goto_skip"]["sub"], "Form_Load")
        md = render_markdown(data)
        self.assertIn("`Form1.frm`", md)
        self.assertIn("`Module1.bas`", md)
        self.assertIn("`Form_Load`", md)

    def test_module_skeleton_file_field_attaches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extract = root / "demo"
            extract.mkdir()
            (extract / "Module1.bas").write_text(
                'Attribute VB_Name = "Module1"\n'
                "Public Sub SkipOpen()\n"
                "    GoTo AfterSkip\n"
                '    Open "modskip.dat" For Input As #3\n'
                "AfterSkip:\n"
                "End Sub\n",
                encoding="utf-8",
            )
            skel = root / "skeletons"
            skel.mkdir()
            (skel / "module1-skeleton.json").write_text(
                json.dumps({
                    "kind": "module",
                    "file": "Module1.bas",
                    "vb_name": "Module1",
                    "goto_skipped_stmts": [
                        {
                            "sub": "SkipOpen",
                            "goto_line": 3,
                            "label": "AfterSkip",
                            "stmt_line": 4,
                            "stmt_kind": "open",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            data = build_catalog(extract, skeletons_dir=skel, repo_root=root)
        skipped = [e for e in data["entries"] if e["goto_skip"]]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["file"], "Module1.bas")
        self.assertEqual(skipped[0]["goto_skip"]["sub"], "SkipOpen")


if __name__ == "__main__":
    unittest.main()
