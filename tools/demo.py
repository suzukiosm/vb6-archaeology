#!/usr/bin/env python3
"""One-command fixture tour: extract → inventory → excerpt → serve.

Does not add comprehension ticks, does not build a call graph, and does not
write originals (regenerating the kit fixture is the existing exception).
The HTTP server is the same long-lived ``serve`` — not ``serve --live-get``.

    python -m tools demo
    python -m tools demo --no-serve
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO), str(REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.config import extracts_root, load_config, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402
from tools.extract_vbp import main as extract_main  # noqa: E402
from tools.make_fixture import main as fixture_main  # noqa: E402
from tools.reimpl_excerpt import write_excerpt  # noqa: E402
from tools.serve_reports import main as serve_main  # noqa: E402
from tools.vb6_inventory import main as inventory_main  # noqa: E402

DEFAULT_VBP = REPO / "source" / "mini_vbp" / "mini_vbp.vbp"


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def run_step(label: str, fn, argv: list[str], next_cmd: str) -> int:
    """Run one tool main. On failure print the next command to type."""
    try:
        code = int(fn(argv) or 0)
    except SystemExit as exc:
        code = _exit_code(exc)
    if code:
        print(
            f"demo failed at {label} (exit {code}). next: {next_cmd}",
            file=sys.stderr,
            flush=True,
        )
        return code
    return 0


def ensure_fixture(vbp: Path) -> int:
    if vbp.is_file():
        return 0
    if vbp.resolve() != DEFAULT_VBP.resolve():
        print(
            f"demo failed at extract (vbp not found: {vbp}). "
            f"next: python -m tools extract \"{vbp}\"",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print("fixture VBP missing; running python -m tools fixture", flush=True)
    return run_step(
        "fixture",
        fixture_main,
        [],
        "python -m tools fixture",
    )


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    cfg = load_config()
    default_port = int(cfg.get("reports_http_port") or 8765)
    ap = argparse.ArgumentParser(
        description=(
            "Fixture tour: extract → inventory → excerpt → serve. "
            "Does not tick. Does not replace smoke --live-get."
        )
    )
    ap.add_argument(
        "--vbp",
        type=Path,
        default=None,
        help="VBP to extract (default: source/mini_vbp/mini_vbp.vbp)",
    )
    ap.add_argument(
        "--extract-out",
        type=Path,
        default=None,
        help="Extract directory (default: working/extracts/<vbp-stem>)",
    )
    ap.add_argument(
        "--reports",
        type=Path,
        default=None,
        help="Reports directory (default: working/reports)",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=default_port,
        help="Loopback port for serve (falls back if taken; printed URL wins)",
    )
    ap.add_argument(
        "--no-serve",
        action="store_true",
        help="Build reports and exit (do not start the HTTP server)",
    )
    args = ap.parse_args(argv)

    vbp = args.vbp or DEFAULT_VBP
    if not vbp.is_absolute():
        vbp = (REPO / vbp).resolve()
    else:
        vbp = vbp.resolve()

    fixture_code = ensure_fixture(vbp)
    if fixture_code:
        return fixture_code

    extract_out = args.extract_out
    if extract_out is None:
        extract_out = extracts_root() / vbp.stem
    elif not extract_out.is_absolute():
        extract_out = REPO / extract_out
    extract_out = extract_out.resolve()

    reports = args.reports
    if reports is None:
        reports = reports_root()
    elif not reports.is_absolute():
        reports = REPO / reports
    reports = reports.resolve()

    extract_cli = f'python -m tools extract "{vbp}" --out "{extract_out}"'
    code = run_step(
        "extract",
        extract_main,
        [str(vbp), "--out", str(extract_out)],
        extract_cli,
    )
    if code:
        return code

    inv_cli = f'python -m tools inventory "{extract_out}" --out-dir "{reports}"'
    code = run_step(
        "inventory",
        inventory_main,
        [str(extract_out), "--out-dir", str(reports), "--no-cache"],
        inv_cli,
    )
    if code:
        return code

    inv_json = reports / f"{vbp.stem}_inventory.json"
    excerpt_out = reports / f"{vbp.stem}_reimpl_excerpt.html"
    excerpt_cli = (
        f'python -m tools excerpt --inventory "{inv_json}" --out "{excerpt_out}"'
    )
    try:
        dest = write_excerpt(
            inventory_path=inv_json, reports=reports, out=excerpt_out
        )
        print(f"excerpt -> {dest}", flush=True)
        excerpt_code = 0
    except SystemExit as exc:
        excerpt_code = _exit_code(exc)
    except OSError as exc:
        print(f"excerpt error: {exc}", file=sys.stderr, flush=True)
        excerpt_code = 1
    if excerpt_code:
        print(
            f"demo failed at excerpt (exit {excerpt_code}). next: {excerpt_cli}",
            file=sys.stderr,
            flush=True,
        )
        return excerpt_code

    serve_cli = f'python -m tools serve --directory "{reports}" --port {args.port}'
    print(f"reports ready under {reports}", flush=True)
    print(f"next: {serve_cli}", flush=True)
    if args.no_serve:
        return 0
    return serve_main(
        ["--directory", str(reports), "--port", str(args.port)]
    )


if __name__ == "__main__":
    raise SystemExit(main())
