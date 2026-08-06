#!/usr/bin/env python3
"""Single entry point for the kit CLI.

    python -m tools <command> [args...]
    python -m tools --help
    python -m tools inventory --help

Each command delegates to the matching module's ``main(argv)``; the underlying
``python tools/<name>.py`` invocations keep working unchanged.
"""

from __future__ import annotations

import difflib
import inspect
import sys
from importlib import import_module
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO), str(REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools import __version__  # noqa: E402
from tools.lib.console import enable_utf8_stdio  # noqa: E402


class Command(NamedTuple):
    module: str
    summary: str


# Ordered as the standard investigation cycle, then helpers, then kit self-check.
COMMANDS: dict[str, Command] = {
    "extract": Command(
        "tools.extract_vbp",
        "Copy a .vbp and the files it references into working/extracts/",
    ),
    "inventory": Command(
        "tools.vb6_inventory",
        "Build the canonical facts-only inventory (json/md/html)",
    ),
    "verify": Command(
        "tools.verify_inventory",
        "Verify inventory End-statement counts against the sources",
    ),
    "verify-names": Command(
        "tools.verify_report_names",
        "Verify report file/procedure names against the inventory name set",
    ),
    "deep-read": Command(
        "tools.frm_deep_read",
        "Deep-read one .frm into a report plus a live-control skeleton",
    ),
    "deep-read-all": Command(
        "tools.frm_deep_read_all",
        "Run deep-read across every .frm in an extract",
    ),
    "layout": Command(
        "tools.runtime_layout",
        "Catalog runtime Left/Top/Width/Height/Visible assignments",
    ),
    "comprehend": Command(
        "tools.comprehension_scaffold",
        "Create the comprehension report skeleton and append evidence ticks",
    ),
    "excerpt": Command(
        "tools.reimpl_excerpt",
        "Build a short reimplementation excerpt (forms / Show / unticked)",
    ),
    "lines": Command(
        "tools.frm_lines",
        "Print CP932 source lines with physical line numbers",
    ),
    "scan-chars": Command(
        "tools.scan_control_chars",
        "Detect control characters injected by PowerShell backtick escapes",
    ),
    "config-check": Command(
        "tools.lib.config_schema",
        "Validate archaeology.config.json against the bundled JSON Schema",
    ),
    "serve": Command(
        "tools.serve_reports",
        "Serve working/reports over local HTTP (file:// does not work)",
    ),
    "fixture": Command(
        "tools.make_fixture",
        "Regenerate the CP932 smoke fixture under source/mini_vbp/",
    ),
    "smoke": Command(
        "tools.kit_smoke",
        "Kit self-check: fixture pipeline + unit tests",
    ),
}

USAGE = f"""usage: python -m tools <command> [args...]

vb6-archaeology {__version__} — investigate VB6 without touching the originals.

commands:
{{commands}}

Run `python -m tools <command> --help` for command options.
Agents: read AGENTS.md then docs/ai-onboarding.md before using these."""


def format_help() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [f"  {name:<{width}}  {cmd.summary}" for name, cmd in COMMANDS.items()]
    return USAGE.format(commands="\n".join(lines))


def unknown_command(name: str) -> int:
    print(f"unknown command: {name}", file=sys.stderr)
    close = difflib.get_close_matches(name, list(COMMANDS), n=3, cutoff=0.4)
    if close:
        print(f"did you mean: {', '.join(close)}", file=sys.stderr)
    print("run `python -m tools --help` for the command list", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(format_help())
        return 0
    if args[0] in ("-V", "--version", "version"):
        print(f"vb6-archaeology {__version__}")
        return 0

    name = args[0]
    command = COMMANDS.get(name)
    if command is None:
        return unknown_command(name)

    return dispatch(name, import_module(command.module), args[1:])


def dispatch(name: str, module, args: list[str]) -> int:
    """Call a tool's main, accepting either main(argv) or a legacy main().

    Consumer repos carry dozens of app-specific tools written before this CLI
    existed; tolerating the older signature means adopting the kit does not
    require rewriting every one of them.
    """
    entry = module.main
    saved = sys.argv
    # argparse derives usage strings from sys.argv[0]; without this every
    # delegated command would advertise itself as `__main__.py`.
    sys.argv = [f"python -m tools {name}", *args]
    try:
        if inspect.signature(entry).parameters:
            return int(entry(args) or 0)
        return int(entry() or 0)
    finally:
        sys.argv = saved


if __name__ == "__main__":
    raise SystemExit(main())
