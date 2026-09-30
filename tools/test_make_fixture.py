"""mini_vbp fixture stays a thin regression base (P3-O).

The constructs live in ``tools/make_fixture.py``. This module writes them to a
temp dir (never ``source/``) and checks them with the same parsers smoke uses.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import make_fixture  # noqa: E402
from tools.extract_vbp import companion_paths  # noqa: E402
from tools.frm_deep_read import (  # noqa: E402
    collect_goto_label_maps,
    find_goto_skipped_stmts,
)
from tools.io_catalog import scan_source_text  # noqa: E402
from tools.vb6_inventory import _parse_bytes, parse_surface, parse_vbp  # noqa: E402


def _write_fixture(root: Path) -> None:
    with patch.object(make_fixture, "OUT", root):
        code = make_fixture.main([])
    if code != 0:
        raise RuntimeError(f"make_fixture.main exited {code}")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.autocrlf=true", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


@unittest.skipUnless(shutil.which("git"), "git not installed")
class FixtureCheckoutTests(unittest.TestCase):
    def test_regenerate_after_checkout_leaves_git_status_clean(self):
        """Windows clones use core.autocrlf=true; fixture runs must not look like edits."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(make_fixture.REPO / ".gitattributes", root)
            fixture = root / "source" / "mini_vbp"
            _write_fixture(fixture)
            _git(root, "init", "-q")
            _git(root, "add", "-A")
            for path in fixture.iterdir():
                path.unlink()
            _git(root, "checkout-index", "--all", "--force", "--index")
            # Age the checkout so git trusts the cached sizes; a racily clean
            # entry is content-checked on every status and would hide the bug.
            past = time.time() - 60
            for path in fixture.iterdir():
                os.utime(path, (past, past))
            _git(root, "update-index", "-q", "--refresh")
            _write_fixture(fixture)
            status = _git(root, "status", "--porcelain", "--", "source")
            worktree_dirty = [line for line in status.splitlines() if line[1] != " "]
            self.assertEqual(worktree_dirty, [])


class FixtureContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _write_fixture(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_writes_usercontrol_and_companion(self):
        ctl = self.root / "MiniCtl.ctl"
        ctx = self.root / "MiniCtl.ctx"
        self.assertTrue(ctl.is_file())
        self.assertTrue(ctx.is_file())
        self.assertEqual(companion_paths(ctl), [ctx])
        vbp = parse_vbp(self.root / "mini_vbp.vbp")
        self.assertEqual(
            vbp["user_controls"],
            [{"ident": "MiniCtl", "file": "MiniCtl.ctl"}],
        )
        self.assertEqual(vbp["meta"]["Type"], "Exe")
        self.assertEqual(vbp["meta"]["CondComp"], "")
        self.assertEqual(vbp["meta"]["CompatibleMode"], "")
        self.assertEqual(vbp["meta"]["CompilationType"], "")

    def test_form1_has_forward_goto_on_error_and_gosub(self):
        lines = make_fixture.FRM.splitlines()
        maps = collect_goto_label_maps(lines)
        by_sub = {row["sub"]: row for row in maps}
        self.assertIn("Form_Load", by_sub)
        self.assertIn("Command1_Click", by_sub)
        load_kinds = {g["kind"] for g in by_sub["Form_Load"]["gotos"]}
        click_kinds = {g["kind"]: g["target"] for g in by_sub["Command1_Click"]["gotos"]}
        self.assertIn("unconditional", load_kinds)
        self.assertEqual(click_kinds["on_error"], "ErrH")
        self.assertEqual(click_kinds["gosub"], "AfterShow")
        skipped = find_goto_skipped_stmts(lines)
        self.assertTrue(
            any(hit["stmt_kind"] == "open" for hit in skipped),
            f"expected a forward-GoTo skipped Open, got {skipped}",
        )

    def test_iodemo_has_five_io_kinds(self):
        entries = scan_source_text(make_fixture.BAS, "Module1.bas")
        kinds = {row["kind"] for row in entries}
        self.assertEqual(kinds, {"open", "put", "get", "name", "kill"})

    def test_widget_surface_facts(self):
        surf = parse_surface(make_fixture.CLS.splitlines())
        # IDE-saved .cls: no Instancing line; the BEGIN block is kept raw.
        self.assertIsNone(surf["instancing"])
        self.assertEqual(surf["class_header"], {
            "MultiUse": -1, "Persistable": 0, "DataBindingBehavior": 0,
            "DataSourceBehavior": 0, "MTSTransactionMode": 0,
        })
        self.assertEqual([i["name"] for i in surf["implements"]], ["IPing"])
        self.assertEqual(surf["with_events"][0]["name"], "Bus")
        self.assertTrue(surf["vb_creatable"])
        self.assertFalse(surf["vb_predeclared_id"])
        self.assertIsNone(surf["vb_user_mem_id"])

    def test_widget_default_member_from_member_attribute(self):
        info = _parse_bytes(make_fixture.CLS.encode("cp932"), Path("Widget.cls"))
        ready = next(p for p in info["procedures"] if p["name"] == "Ready")
        self.assertEqual(ready["attributes"], {"VB_UserMemId": 0})
        self.assertEqual(info["surface"]["default_member"], "Ready")

    def test_form_predeclared_id(self):
        surf = parse_surface(make_fixture.FRM.splitlines())
        self.assertTrue(surf["vb_predeclared_id"])
        self.assertIsNone(surf["vb_user_mem_id"])


if __name__ == "__main__":
    unittest.main()
