from __future__ import annotations

import unittest

from tools.runtime_layout import build_contextual_form_layout


# VB_Name keys match residual Show-path heuristics in runtime_layout.py;
# filenames are kit-generic (not a specific customer VBP).
FORMS = {
    "Denpyou": "Denpyou.frm",
    "Form3": "Form3.frm",
    "Form7": "Form7.frm",
    "Form13": "Form13.frm",
    "statas": "statas.frm",
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
        "file": FORMS[file_vb],
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
        target="statas",
        file_vb="statas",
        sub="Form_Load",
        prop="Width",
        value=12000,
        line=10,
        object_name="Me",
    ),
    assignment(
        target="statas",
        file_vb="Form7",
        sub="Command2_Click",
        prop="Left",
        value=3500,
        line=20,
    ),
    assignment(
        target="statas",
        file_vb="Form7",
        sub="Command2_Click",
        prop="Left",
        value=4000,
        line=21,
    ),
    assignment(
        target="statas",
        file_vb="Denpyou",
        sub="stet_Click",
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
        file_vb="Denpyou",
        sub="Check3_Click",
        prop="Left",
        value=-50000,
        line=50,
        kind="offscreen_hide",
    ),
    assignment(
        target="Form13",
        file_vb="Denpyou",
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
    def test_contextual_layout_keeps_distinct_statas_openers(self) -> None:
        placements = build_contextual_form_layout(ASSIGNMENTS, FORMS)

        self.assertEqual(
            lookup(placements, "statas", "Form7", "Command2_Click")["left"],
            4000,
        )
        self.assertEqual(
            lookup(placements, "statas", "Denpyou", "stet_Click")["left"],
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


if __name__ == "__main__":
    unittest.main()
