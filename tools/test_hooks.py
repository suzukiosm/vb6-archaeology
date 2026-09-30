"""Protection hooks: the kit's core invariant, exercised as Cursor runs them.

Both hooks read JSON on stdin and print a permission verdict, so the tests drive
the real scripts through subprocess instead of importing their helpers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = REPO_ROOT / ".cursor" / "hooks"

OFF_REPO_CONFIG = {
    "protected_source_dirs": [],
    "protected_path_markers": ["アイコー"],
    "default_source_dir": "",
}


def run_hook_bytes(script: str, raw: bytes, hooks_dir: Path | None = None) -> dict:
    hooks_dir = hooks_dir or HOOKS
    proc = subprocess.run(
        [sys.executable, str(hooks_dir / script)],
        input=raw,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError(f"{script} exited {proc.returncode}: {proc.stderr!r}")
    return json.loads(proc.stdout.decode("utf-8"))


def run_hook(script: str, payload: dict, hooks_dir: Path | None = None) -> dict:
    # Cursor on Windows prefixes the payload with a UTF-8 BOM; send it the same
    # way so a BOM-intolerant reader fails here instead of silently in the IDE.
    raw = b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return run_hook_bytes(script, raw, hooks_dir)


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

    def test_cursor_write_payload_shape_is_checked(self):
        # Shape recorded from Cursor's hooks log: tool_input.file_path + content.
        payload = {"tool_name": "Write",
                   "tool_input": {"file_path": r"h:\repo\source\mini_vbp\Form1.frm",
                                  "content": "日本語"}}
        self.assertEqual(run_hook("protect_source.py", payload)["permission"], "deny")

    def test_payload_without_bom_and_utf16_are_read(self):
        body = json.dumps({"tool_input": {"file_path": "source/x.frm"}})
        for raw in (body.encode("utf-8"), body.encode("utf-16")):
            with self.subTest(head=raw[:2]):
                self.assertEqual(run_hook_bytes("protect_source.py", raw)["permission"], "deny")

    def test_case_variant_of_protected_tree_is_denied(self):
        # Windows resolves Source\ and source\ to the same directory.
        self.assertEqual(write_verdict("H:/_APRI/vb6-archaeology/Source/mini_vbp/Form1.frm"), "deny")
        self.assertEqual(write_verdict(r"SOURCE\x.bas"), "deny")

    def test_unreadable_payload_fails_closed_and_names_the_bytes(self):
        verdict = run_hook_bytes("protect_source.py", b"{not json")
        self.assertEqual(verdict["permission"], "deny")
        self.assertIn("head=7b6e6f74", verdict["agent_message"])


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

    def test_allowlist_does_not_cover_chained_commands(self):
        self.assertEqual(
            shell_verdict(r"python -m tools fixture; Remove-Item -Recurse source\mini_vbp"), "ask"
        )
        self.assertEqual(
            shell_verdict(r"python -m tools fixture && del source\mini_vbp\Form1.frm"), "ask"
        )

    def test_allowlist_keeps_plain_fixture_spellings(self):
        self.assertEqual(shell_verdict(r"python .\tools\make_fixture.py"), "allow")
        self.assertEqual(shell_verdict("python -m tools fixture --help"), "allow")

    def test_copy_into_protected_tree_asks(self):
        self.assertEqual(shell_verdict(r"Copy-Item x.frm source\mini_vbp\Form1.frm -Force"), "ask")
        self.assertEqual(shell_verdict("cp x.frm source/mini_vbp/Form1.frm"), "ask")

    def test_git_worktree_rewrites_of_protected_tree_ask(self):
        self.assertEqual(shell_verdict("git checkout -- source/mini_vbp"), "ask")
        self.assertEqual(shell_verdict("git restore source/mini_vbp/Form1.frm"), "ask")
        self.assertEqual(shell_verdict("git diff -- source/mini_vbp"), "allow")

    def test_dotnet_file_writes_ask(self):
        self.assertEqual(shell_verdict(r"[IO.File]::WriteAllText('source\x.txt', 'y')"), "ask")

    def test_case_variant_of_protected_tree_asks(self):
        self.assertEqual(shell_verdict(r"Remove-Item -Recurse Source\mini_vbp"), "ask")
        self.assertEqual(shell_verdict('echo "x" > Source/notes.txt'), "ask")

    def test_unreadable_payload_asks(self):
        self.assertEqual(run_hook_bytes("guard_shell.py", b"{not json")["permission"], "ask")


class TestMarkersForOffRepoOriginals(unittest.TestCase):
    """Consumers keep originals on a share; the hooks read markers from config.

    The hooks derive the repo root from their own location, so the test stages a
    throwaway repo with a marker config and runs the real scripts from there.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.hooks_dir = root / ".cursor" / "hooks"
        self.hooks_dir.mkdir(parents=True)
        for script in ("protect_source.py", "guard_shell.py"):
            shutil.copy2(HOOKS / script, self.hooks_dir / script)
        (root / "archaeology.config.json").write_text(
            json.dumps(OFF_REPO_CONFIG, ensure_ascii=False), encoding="utf-8"
        )

    def verdict(self, script: str, payload: dict) -> str:
        return run_hook(script, payload, self.hooks_dir)["permission"]

    def test_write_to_marked_tree_outside_repo_is_denied(self):
        self.assertEqual(
            self.verdict(
                "protect_source.py",
                {"path": r"Z:\_Python\VB6_source\アイコー\納品書.frm"},
            ),
            "deny",
        )

    def test_write_inside_the_repo_is_still_allowed(self):
        self.assertEqual(
            self.verdict("protect_source.py", {"path": "working/extracts/x/Form1.frm"}),
            "allow",
        )

    def test_shell_mutation_of_marked_tree_asks(self):
        self.assertEqual(
            self.verdict(
                "guard_shell.py",
                {"command": r"Remove-Item Z:\_Python\VB6_source\アイコー\x.frm"},
            ),
            "ask",
        )


class TestSessionContext(unittest.TestCase):
    def test_mentions_runtime_layout_and_excerpt(self) -> None:
        out = run_hook("session_context.py", {})
        ctx = out.get("additional_context") or ""
        self.assertIn("/runtime-layout", ctx)
        self.assertIn("excerpt", ctx)
        self.assertIn("AGENTS.md", ctx)
        self.assertIn("python -m tools status", ctx)
        self.assertIn("stem=", ctx)
        self.assertIn("deep-read=", ctx)
        self.assertIn("verify=", ctx)


if __name__ == "__main__":
    unittest.main()
