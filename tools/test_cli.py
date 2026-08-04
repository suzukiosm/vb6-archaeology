"""Unified CLI: command table, help, version, unknown-command handling."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import __version__  # noqa: E402
from tools.cli import COMMANDS, dispatch, main  # noqa: E402


def run(argv: list[str]) -> tuple[int, str, str]:
    """Run the CLI in-process, returning (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse --help / usage errors
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def test_every_command_module_exposes_main(self):
        for name, command in COMMANDS.items():
            with self.subTest(command=name):
                module = import_module(command.module)
                self.assertTrue(
                    callable(getattr(module, "main", None)),
                    f"{command.module}.main is missing",
                )

    def test_every_command_help_exits_zero(self):
        for name in COMMANDS:
            with self.subTest(command=name):
                code, out, _ = run([name, "--help"])
                self.assertEqual(code, 0)
                self.assertIn("usage", out.lower())

    def test_root_help_lists_all_commands(self):
        code, out, _ = run([])
        self.assertEqual(code, 0)
        for name in COMMANDS:
            self.assertIn(name, out)

    def test_version_matches_package(self):
        code, out, _ = run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)

    def test_unknown_command_exits_two_with_suggestion(self):
        code, _, err = run(["inventry"])
        self.assertEqual(code, 2)
        self.assertIn("unknown command", err)
        self.assertIn("inventory", err)


class TestLegacyMainSignature(unittest.TestCase):
    """Consumer repos carry tools written before this CLI; both shapes dispatch."""

    def test_main_without_argv_receives_sys_argv(self):
        seen: dict[str, list[str]] = {}

        class Legacy:
            @staticmethod
            def main() -> int:
                seen["argv"] = list(sys.argv)
                return 0

        code = dispatch("legacy", Legacy, ["--flag", "value"])
        self.assertEqual(code, 0)
        self.assertEqual(seen["argv"], ["python -m tools legacy", "--flag", "value"])

    def test_main_with_argv_receives_the_arguments(self):
        seen: dict[str, list[str]] = {}

        class Modern:
            @staticmethod
            def main(argv=None) -> int:
                seen["argv"] = list(argv or [])
                return 0

        self.assertEqual(dispatch("modern", Modern, ["a", "b"]), 0)
        self.assertEqual(seen["argv"], ["a", "b"])

    def test_sys_argv_is_restored(self):
        before = list(sys.argv)

        class Legacy:
            @staticmethod
            def main() -> int:
                return 0

        dispatch("legacy", Legacy, [])
        self.assertEqual(sys.argv, before)


if __name__ == "__main__":
    unittest.main()
