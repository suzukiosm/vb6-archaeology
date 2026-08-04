"""Protection hooks: the kit's core invariant, exercised as Cursor runs them.

Both hooks read JSON on stdin and print a permission verdict, so the tests drive
the real scripts through subprocess instead of importing their helpers.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / ".cursor" / "hooks"


def run_hook(script: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError(f"{script} exited {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def write_verdict(path: str) -> str:
    return run_hook("protect_source.py", {"tool_input": {"path": path}})["permission"]


def shell_verdict(command: str) -> str:
    return run_hook("guard_shell.py", {"command": command})["permission"]


class TestProtectSource(unittest.TestCase):
    def test_write_into_protected_tree_is_denied(self):
        self.assertEqual(write_verdict("source/mini_vbp/Form1.frm"), "deny")

    def test_windows_path_into_protected_tree_is_denied(self):
        self.assertEqual(write_verdict(r"H:\_APRI\vb6-archaeology\source\notes.md"), "deny")

    def test_write_into_extracts_is_allowed(self):
        self.assertEqual(write_verdict("working/extracts/mini_vbp/Form1.frm"), "allow")

    def test_similar_directory_name_is_not_protected(self):
        self.assertEqual(write_verdict("working/resources/theme.css"), "allow")

    def test_deny_message_names_the_offending_path(self):
        verdict = run_hook("protect_source.py", {"path": "source/x.frm"})
        self.assertEqual(verdict["permission"], "deny")
        self.assertIn("source/x.frm", verdict["agent_message"])


class TestGuardShell(unittest.TestCase):
    def test_delete_inside_protected_tree_asks(self):
        self.assertEqual(shell_verdict(r"Remove-Item source\mini_vbp\Form1.frm"), "ask")

    def test_redirect_into_protected_tree_asks(self):
        self.assertEqual(shell_verdict('echo "x" > source/notes.txt'), "ask")

    def test_fixture_regeneration_is_allowlisted(self):
        self.assertEqual(shell_verdict("python tools/make_fixture.py"), "allow")

    def test_fixture_subcommand_is_allowlisted(self):
        self.assertEqual(shell_verdict("python -m tools fixture"), "allow")

    def test_reading_protected_tree_is_allowed(self):
        self.assertEqual(shell_verdict("python -m tools lines source/mini_vbp/Form1.frm 1-20"), "allow")

    def test_mutating_working_tree_is_allowed(self):
        self.assertEqual(shell_verdict(r"Remove-Item working\reports\old.md"), "allow")

    def test_similar_directory_name_is_not_guarded(self):
        self.assertEqual(shell_verdict("Remove-Item working/resources/theme.css"), "allow")


if __name__ == "__main__":
    unittest.main()
