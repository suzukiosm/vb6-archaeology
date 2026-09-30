"""Shared event-owner binding: inventory and deep-read must agree (synthetic VB6)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.frm_deep_read import (
    analyze_module_file,
    classify_controls,
    classify_events,
    extract_controls,
    extract_events,
)
from tools.lib.event_binding import resolve_event_owner, self_owners_for
from tools.vb6_inventory import _parse_bytes

FRM = [
    "VERSION 5.00",
    "Begin VB.Form F",
    "   Begin MSCommLib.MSComm MSComm1",
    "   End",
    "   Begin MSWinsockLib.Winsock Winsock1",
    "   End",
    "   Begin VB.CommandButton cmd_Save",
    "   End",
    "End",
    'Attribute VB_Name = "F"',
    "Private Sub Form_QueryUnload(Cancel As Integer, UnloadMode As Integer)",
    "End Sub",
    "Private Sub Form_Initialize()",
    "End Sub",
    "Private Sub MSComm1_OnComm()",
    "End Sub",
    "Private Sub Winsock1_DataArrival(ByVal bytesTotal As Long)",
    "End Sub",
    "Private Sub cmd_Save_Click()",
    "End Sub",
]


def _code_text(lines: list[str]) -> str:
    start = next(i for i, s in enumerate(lines) if s.startswith("Attribute VB_Name"))
    return "\n".join(lines[start:])


class ResolveOwnerTests(unittest.TestCase):
    def test_longest_owner_prefix_wins_and_case_is_ignored(self) -> None:
        got = resolve_event_owner("CMD_SAVE_Click", controls=["cmd", "cmd_Save"])
        self.assertEqual(got, {"owner": "CMD_SAVE", "event": "Click", "binding": "designer"})

    def test_self_owner_by_source_kind(self) -> None:
        self.assertEqual(self_owners_for(".CTL"), ("UserControl",))
        got = resolve_event_owner("Class_Terminate", self_owners=self_owners_for(".cls"))
        self.assertEqual(got["binding"], "self")
        self.assertIsNone(resolve_event_owner("Form_Load", self_owners=self_owners_for(".cls")))

    def test_withevents_owner(self) -> None:
        got = resolve_event_owner("mConn_WillExecute", with_events=["mConn"])
        self.assertEqual((got["owner"], got["event"], got["binding"]),
                         ("mConn", "WillExecute", "withevents"))

    def test_trailing_underscore_is_not_an_event(self) -> None:
        self.assertIsNone(resolve_event_owner("Form_", self_owners=["Form"]))


class DeepReadAgreesWithInventoryTests(unittest.TestCase):
    def test_events_outside_the_builtin_suffix_list_are_bound(self) -> None:
        _, controls = extract_controls(FRM)
        events = classify_events(extract_events(FRM), _code_text(FRM), "", controls, "F")
        by_name = {e["name"]: e for e in events}
        for name in ("Form_QueryUnload", "Form_Initialize", "MSComm1_OnComm",
                     "Winsock1_DataArrival", "cmd_Save_Click"):
            with self.subTest(name=name):
                self.assertEqual(by_name[name]["status"], "live")
                self.assertEqual(by_name[name]["binding"], "designer_candidate")
        self.assertEqual(by_name["MSComm1_OnComm"]["event_owner"], "MSComm1")
        self.assertEqual(by_name["cmd_Save_Click"]["event_name"], "Click")

    def test_control_with_only_a_custom_event_is_code_referenced(self) -> None:
        _, controls = extract_controls(FRM)
        code = _code_text(FRM)
        events = classify_events(extract_events(FRM), code, "", controls, "F")
        classify_controls(controls, code, code, events, "F")
        self.assertTrue(all(c["live"] for c in controls), [(c["name"], c["live"]) for c in controls])

    def test_inventory_marks_the_same_procedures_as_events(self) -> None:
        info = _parse_bytes("\r\n".join(FRM).encode("cp932"), Path("F.frm"))
        roles = {p["name"]: (p["role"], p.get("event_binding")) for p in info["procedures"]}
        self.assertEqual(roles["Form_QueryUnload"], ("event", "self"))
        self.assertEqual(roles["MSComm1_OnComm"], ("event", "designer"))
        self.assertEqual(roles["cmd_Save_Click"], ("event", "designer"))


class InventoryModuleKindsTests(unittest.TestCase):
    def roles(self, name: str, lines: list[str]) -> dict:
        info = _parse_bytes("\r\n".join(lines).encode("cp932"), Path(name))
        return {p["name"]: (p["role"], p.get("event_binding")) for p in info["procedures"]}

    def test_usercontrol_lifecycle_is_an_event_but_form_prefix_is_not(self) -> None:
        roles = self.roles("U.ctl", [
            "VERSION 5.00", "Begin VB.UserControl U", "End", 'Attribute VB_Name = "U"',
            "Private Sub UserControl_Initialize()", "End Sub",
            "Private Sub Form_Load()", "End Sub",
        ])
        self.assertEqual(roles["UserControl_Initialize"], ("event", "self"))
        self.assertEqual(roles["Form_Load"], ("general", None))

    def test_class_lifecycle_and_withevents_handlers(self) -> None:
        roles = self.roles("C.cls", [
            'Attribute VB_Name = "C"',
            "Private WithEvents mConn As ADODB.Connection",
            "Private Sub Class_Initialize()", "End Sub",
            "Private Sub mConn_WillExecute(Source As String)", "End Sub",
            "Public Sub Work()", "End Sub",
        ])
        self.assertEqual(roles["Class_Initialize"], ("event", "self"))
        self.assertEqual(roles["mConn_WillExecute"], ("event", "withevents"))
        self.assertEqual(roles["Work"], ("general", None))

    def test_module_deep_read_reports_class_entry_points(self) -> None:
        lines = ['Attribute VB_Name = "C"', "Private Sub Class_Initialize()", "End Sub",
                 "Public Sub Work()", "End Sub"]
        data = analyze_module_file(lines, Path("C.cls"), "C")
        by_name = {p["name"]: p for p in data["procedures"]}
        self.assertEqual(by_name["Class_Initialize"]["event_binding"], "self")
        self.assertNotIn("event_binding", by_name["Work"])


if __name__ == "__main__":
    unittest.main()
