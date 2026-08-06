from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.runtime_layout import (
    BUILTIN_LAYOUT_SUB_SCORES,
    GAP_STATUS_UNREVIEWED,
    build_contextual_form_layout,
    build_form_show_layout,
    build_mdi_defaults,
    classify,
    effective_layout_sub_scores,
    existing_gap_status,
    extract_file,
    is_mdi_chrome_target,
    mdi_chrome_settings,
    resolve_picture1_form,
)

# Common consumer-shaped chrome (not kit defaults — tests patch load_config).
CONSUMER_MDI_CHROME = {
    "shell_forms": ["MDIForm1"],
    "control_names": ["Picture1", "FG1", "fg2"],
}


# Synthetic form names for placement tests (not kit defaults).
FORMS = {
    "Host": "Host.frm",
    "Form3": "Form3.frm",
    "Form7": "Form7.frm",
    "Form13": "Form13.frm",
    "Child": "Child.frm",
}


def assignment(
    *,
    target: str,
    file_vb: str,
    sub: str,
    prop: str,
    value: int,
    line: int,
    kind: str = "form_place",
    object_name: str | None = None,
) -> dict:
    obj = object_name or target
    return {
        "file": FORMS.get(file_vb, f"{file_vb}.frm"),
        "file_vb": file_vb,
        "line": line,
        "sub": sub,
        "object": obj,
        "target": target,
        "prop": prop,
        "expr": str(value),
        "value": value,
        "kind": kind,
        "near_show": [target],
        "source": f"{obj}.{prop} = {value}",
    }


ASSIGNMENTS = [
    assignment(
        target="Child",
        file_vb="Child",
        sub="Form_Load",
        prop="Width",
        value=12000,
        line=10,
        object_name="Me",
    ),
    assignment(
        target="Child",
        file_vb="Form7",
        sub="Command2_Click",
        prop="Left",
        value=3500,
        line=20,
    ),
    assignment(
        target="Child",
        file_vb="Form7",
        sub="Command2_Click",
        prop="Left",
        value=4000,
        line=21,
    ),
    assignment(
        target="Child",
        file_vb="Host",
        sub="OpenAlt_Click",
        prop="Left",
        value=1000,
        line=30,
    ),
    assignment(
        target="Form3",
        file_vb="Form3",
        sub="Form_Load",
        prop="Left",
        value=100,
        line=40,
        object_name="Me",
    ),
    assignment(
        target="Form3",
        file_vb="Form3",
        sub="Form_Load",
        prop="Top",
        value=200,
        line=41,
        object_name="Me",
    ),
    assignment(
        target="Form3",
        file_vb="Form3",
        sub="Form_Load",
        prop="Width",
        value=14500,
        line=42,
        object_name="Me",
    ),
    assignment(
        target="Form3",
        file_vb="Form3",
        sub="Form_Load",
        prop="Height",
        value=10650,
        line=43,
        object_name="Me",
    ),
    assignment(
        target="Form13",
        file_vb="Host",
        sub="Check3_Click",
        prop="Left",
        value=-50000,
        line=50,
        kind="offscreen_hide",
    ),
    assignment(
        target="Form13",
        file_vb="Host",
        sub="Check3_Click",
        prop="Top",
        value=6775,
        line=51,
    ),
]


def lookup(placements: list[dict], form: str, from_form: str, via: str) -> dict:
    return next(
        placement
        for placement in placements
        if placement["form"] == form
        and placement["from"] == from_form
        and placement["via"] == via
    )


class ContextualFormLayoutTests(unittest.TestCase):
    def test_contextual_layout_keeps_distinct_child_openers(self) -> None:
        placements = build_contextual_form_layout(ASSIGNMENTS, FORMS)

        self.assertEqual(
            lookup(placements, "Child", "Form7", "Command2_Click")["left"],
            4000,
        )
        self.assertEqual(
            lookup(placements, "Child", "Host", "OpenAlt_Click")["left"],
            1000,
        )

    def test_contextual_layout_merges_form_load_then_caller(self) -> None:
        placement = lookup(
            build_contextual_form_layout(ASSIGNMENTS, FORMS),
            "Form3",
            "Form3",
            "Form_Load",
        )

        self.assertEqual(placement["left"], 100)
        self.assertEqual(placement["top"], 200)
        self.assertEqual(placement["width"], 14500)
        self.assertEqual(placement["height"], 10650)
        self.assertEqual(
            {item["prop"] for item in placement["evidence"]},
            {"Left", "Top", "Width", "Height"},
        )

    def test_offscreen_hide_is_not_default_visible_placement(self) -> None:
        placements = build_contextual_form_layout(ASSIGNMENTS, FORMS)

        self.assertTrue(
            all(
                placement["left"] != -50000
                for placement in placements
                if placement["form"] == "Form13"
            )
        )


class LayoutSubScoresTests(unittest.TestCase):
    def test_empty_override_keeps_builtin_only(self) -> None:
        scores = effective_layout_sub_scores({})
        self.assertEqual(scores, BUILTIN_LAYOUT_SUB_SCORES)
        self.assertIn("form_load", scores)
        self.assertNotIn("stet_click", scores)

    def test_high_score_selects_configured_opener(self) -> None:
        forms = {"Child": "Child.frm", "Parent": "Parent.frm"}
        rows = [
            assignment(
                target="Child",
                file_vb="Parent",
                sub="Other_Click",
                prop="Left",
                value=1000,
                line=10,
            ),
            assignment(
                target="Child",
                file_vb="Parent",
                sub="OpenSpecial",
                prop="Left",
                value=5000,
                line=20,
            ),
        ]
        # 汎用のみ: Other_Click が *_click 加点で勝つ
        layout_default = build_form_show_layout(rows, forms, sub_scores={})
        self.assertEqual(layout_default["Child"]["left"], 1000)

        # 架空 Sub に高スコア → OpenSpecial が選ばれる
        layout_cfg = build_form_show_layout(
            rows, forms, sub_scores={"openspecial": 90}
        )
        self.assertEqual(layout_cfg["Child"]["left"], 5000)
        self.assertEqual(
            layout_cfg["Child"]["evidence"][0]["sub"],
            "OpenSpecial",
        )

    def test_form_load_beats_unlisted_click_with_builtins(self) -> None:
        forms = {"Child": "Child.frm", "Parent": "Parent.frm"}
        rows = [
            assignment(
                target="Child",
                file_vb="Parent",
                sub="Form_Load",
                prop="Left",
                value=111,
                line=5,
            ),
            assignment(
                target="Child",
                file_vb="Parent",
                sub="Other_Click",
                prop="Left",
                value=999,
                line=15,
            ),
        ]
        layout = build_form_show_layout(rows, forms, sub_scores={})
        self.assertEqual(layout["Child"]["left"], 111)


class MdiDefaultsConfigTests(unittest.TestCase):
    def test_build_mdi_defaults_from_config(self) -> None:
        form_layout = {
            "MDIForm1": {"left": 0, "height": 13550, "top": 0, "width": None}
        }
        with patch(
            "tools.runtime_layout.load_config",
            return_value={
                "mdi_defaults": {
                    "picture1HeightExpanded": 13000,
                    "picture1HeightCollapsed": 4095,
                },
                "mdi_chrome": CONSUMER_MDI_CHROME,
            },
        ):
            got = build_mdi_defaults(form_layout)
        self.assertEqual(
            got,
            {
                "left": 0,
                "height": 13550,
                "picture1HeightExpanded": 13000,
                "picture1HeightCollapsed": 4095,
            },
        )

    def test_build_mdi_defaults_uses_configured_shell(self) -> None:
        form_layout = {
            "MainShell": {"left": 10, "height": 9000, "top": 0, "width": None}
        }
        with patch(
            "tools.runtime_layout.load_config",
            return_value={
                "mdi_defaults": {
                    "picture1HeightExpanded": 8000,
                    "picture1HeightCollapsed": 2000,
                },
                "mdi_chrome": {
                    "shell_forms": ["MainShell"],
                    "control_names": ["Picture1"],
                },
            },
        ):
            got = build_mdi_defaults(form_layout)
        self.assertEqual(got["left"], 10)
        self.assertEqual(got["height"], 9000)

    def test_build_mdi_defaults_none_without_config(self) -> None:
        with patch("tools.runtime_layout.load_config", return_value={}):
            self.assertIsNone(build_mdi_defaults({"MDIForm1": {"left": 0}}))

    def test_build_mdi_defaults_none_without_picture1_heights(self) -> None:
        with patch(
            "tools.runtime_layout.load_config",
            return_value={"mdi_defaults": {"left": 0}},
        ):
            self.assertIsNone(build_mdi_defaults({}))


class GapStatusTests(unittest.TestCase):
    """Regenerating form_layout_gap.md must not erase the human 着手 column."""

    def _write_gap(self, reports: Path, status: str) -> None:
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "form_layout_gap.md").write_text(
            "| Form | file | geom | Visible | codeMoves | 主な対象 | 着手 |\n"
            "|---|---|---:|---:|---:|---|---|\n"
            f"| Form7 | `form7.frm` | 3 | 1 | 2 | Text1 | {status} |\n"
            f"| Form8 | `form8.frm` | 0 | 0 | 0 | — | {GAP_STATUS_UNREVIEWED} |\n",
            encoding="utf-8",
        )

    def test_written_status_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            self._write_gap(reports, "2026-08-05 配線済み")
            with patch("tools.runtime_layout.REPORTS", reports):
                kept = existing_gap_status()
        self.assertEqual(kept, {"Form7": "2026-08-05 配線済み"})

    def test_missing_report_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.runtime_layout.REPORTS", Path(tmp)):
                self.assertEqual(existing_gap_status(), {})


class Picture1ConfigTests(unittest.TestCase):
    def test_resolve_picture1_reads_config(self) -> None:
        with patch(
            "tools.runtime_layout.load_config",
            return_value={
                "picture1_height_by_sub": {
                    "open_child_click": "Child",
                    "open_child_click@mdiform1": "Child",
                }
            },
        ):
            self.assertEqual(
                resolve_picture1_form("Open_Child_Click", "MDIForm1"), "Child"
            )
            self.assertEqual(resolve_picture1_form("Open_Child_Click", None), "Child")
            self.assertIsNone(resolve_picture1_form("Unknown_Click", "MDIForm1"))

    def test_picture1_height_uses_config_when_near_show_empty(self) -> None:
        rows = [
            {
                "file": "MDIForm1.frm",
                "file_vb": "MDIForm1",
                "line": 10,
                "sub": "Open_Child_Click",
                "object": "MDIForm1.Picture1",
                "target": "MDIForm1.Picture1",
                "prop": "Height",
                "expr": "3500",
                "value": 3500,
                "kind": "mdi_chrome",
                "near_show": [],
                "source": "Picture1.Height = 3500",
            }
        ]
        forms = {"Child": "Child.frm", "MDIForm1": "MDIForm1.frm"}
        with patch(
            "tools.runtime_layout.load_config",
            return_value={
                "picture1_height_by_sub": {"open_child_click": "Child"},
                "mdi_chrome": CONSUMER_MDI_CHROME,
            },
        ):
            layout = build_form_show_layout(rows, forms, sub_scores={})
        self.assertEqual(layout["Child"]["picture1Height"], 3500)

    def test_fg_aliases_classify_as_mdi_chrome(self) -> None:
        with patch(
            "tools.runtime_layout.load_config",
            return_value={"mdi_chrome": CONSUMER_MDI_CHROME},
        ):
            self.assertEqual(
                classify("MDIForm1.fg2", "Height", "12000", 12000, "MDIForm1"),
                "mdi_chrome",
            )
            self.assertEqual(
                classify("FG1", "Width", "100", 100, "MDIForm1"),
                "mdi_chrome",
            )

    def test_empty_mdi_chrome_does_not_treat_picture1_as_chrome(self) -> None:
        with patch(
            "tools.runtime_layout.load_config",
            return_value={"mdi_chrome": {"shell_forms": [], "control_names": []}},
        ):
            self.assertEqual(
                classify("Picture1", "Height", "100", 100, "Host"),
                "control_move",
            )
            self.assertFalse(is_mdi_chrome_target("MDIForm1.Picture1"))

    def test_custom_shell_name_qualifies_bare_chrome_control(self) -> None:
        src = """\
Attribute VB_Name = "MainShell"
Option Explicit

Private Sub Form_Load()
    Banner.Height = 4095
End Sub
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "MainShell.frm"
            path.write_text(src, encoding="utf-8")
            with patch(
                "tools.runtime_layout.load_config",
                return_value={
                    "mdi_chrome": {
                        "shell_forms": ["MainShell"],
                        "control_names": ["Banner"],
                    }
                },
            ):
                rows = extract_file(path, "MainShell")
        chrome = [r for r in rows if r["kind"] == "mdi_chrome"]
        self.assertEqual(len(chrome), 1)
        self.assertEqual(chrome[0]["object"], "MainShell.Banner")
        self.assertEqual(chrome[0]["target"], "MainShell.Banner")

    def test_mdi_chrome_settings_reads_config(self) -> None:
        with patch(
            "tools.runtime_layout.load_config",
            return_value={
                "mdi_chrome": {
                    "shell_forms": ["ShellA", ""],
                    "control_names": ["Pic", "  "],
                }
            },
        ):
            shells, controls = mdi_chrome_settings()
        self.assertEqual(shells, ["ShellA"])
        self.assertEqual(controls, ["Pic"])


class RecentShowsSubBoundaryTests(unittest.TestCase):
    def test_show_context_does_not_cross_sub(self) -> None:
        """Sub またぎで隣 Sub の near_show に誤帰属しないこと。"""
        src = """\
Attribute VB_Name = "Host"
Option Explicit

Private Sub SubA_Click()
    FormX.Show
End Sub

Private Sub SubB_Click()
    Me.Left = 100
End Sub
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Host.frm"
            path.write_text(src, encoding="utf-8")
            rows = extract_file(path, "Host")
        left_rows = [r for r in rows if r["prop"] == "Left" and r["sub"] == "SubB_Click"]
        self.assertEqual(len(left_rows), 1)
        self.assertNotIn("FormX", left_rows[0]["near_show"])

    def test_show_context_stays_within_same_sub(self) -> None:
        src = """\
Attribute VB_Name = "Host"
Option Explicit

Private Sub OpenChild_Click()
    FormX.Show
    Me.Left = 200
End Sub
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Host.frm"
            path.write_text(src, encoding="utf-8")
            rows = extract_file(path, "Host")
        left_rows = [r for r in rows if r["prop"] == "Left"]
        self.assertEqual(len(left_rows), 1)
        self.assertIn("FormX", left_rows[0]["near_show"])


if __name__ == "__main__":
    unittest.main()
