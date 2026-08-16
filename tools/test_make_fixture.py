"""mini_vbp fixture stays a thin regression base (P3-O).

The constructs live in ``tools/make_fixture.py``. This module writes them to a
temp dir (never ``source/``) and checks them with the same parsers smoke uses.
"""

from __future__ import annotations

import sys
import tempfile
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
from tools.vb6_inventory import parse_surface, parse_vbp  # noqa: E402


def _write_fixture(root: Path) -> None:
    with patch.object(make_fixture, "OUT", root):
        code = make_fixture.main([])
    if code != 0:
        raise RuntimeError(f"make_fixture.main exited {code}")


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
        self.assertEqual(surf["instancing"], 5)
        self.assertEqual([i["name"] for i in surf["implements"]], ["IPing"])
        self.assertEqual(surf["with_events"][0]["name"], "Bus")
        self.assertTrue(surf["vb_creatable"])


if __name__ == "__main__":
    unittest.main()
