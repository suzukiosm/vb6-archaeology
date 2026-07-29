from __future__ import annotations

import unittest

from tools.frm_deep_read import annotate_hidden_ancestor


def ctrl(
    name: str,
    *,
    kind: str = "VB.Label",
    parent: str | None = None,
    visible: bool = True,
    live: bool = False,
    left: int = 0,
    top: int = 0,
    width: int = 100,
    height: int = 100,
) -> dict:
    return {
        "kind": kind,
        "name": name,
        "parent": parent,
        "visible": visible,
        "live": live,
        "abs_left": left,
        "abs_top": top,
        "width": width,
        "height": height,
        "line": 1,
        "caption": "",
        "index": None,
    }


class AncestorHiddenTests(unittest.TestCase):
    def test_dead_invisible_frame_marks_children(self) -> None:
        controls = [
            ctrl(
                "FrameDead",
                kind="VB.Frame",
                visible=False,
                live=False,
                width=2000,
                height=1000,
            ),
            ctrl("LabelHidden", parent="FrameDead", left=120, top=360),
        ]
        annotate_hidden_ancestor(controls)
        child = controls[1]
        self.assertTrue(child.get("ancestor_hidden"))
        self.assertEqual(child.get("ancestor_hidden_by"), "FrameDead")

    def test_live_invisible_frame_does_not_mark_children(self) -> None:
        controls = [
            ctrl(
                "FrameLive",
                kind="VB.Frame",
                visible=False,
                live=True,
                width=2000,
                height=1000,
            ),
            ctrl("LabelOk", parent="FrameLive", left=120, top=360),
        ]
        annotate_hidden_ancestor(controls)
        self.assertFalse(controls[1].get("ancestor_hidden"))


if __name__ == "__main__":
    unittest.main()
