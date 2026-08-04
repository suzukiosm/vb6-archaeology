#!/usr/bin/env python3
"""Serve the reports directory over local HTTP.

Report HTML pulls sibling assets, so `file://` viewing is unreliable; always go
through a loopback HTTP server.

    python -m tools serve
    python -m tools serve --port 8790
    python -m tools serve --check      # validate directory, print URL, exit
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, reports_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    ap = argparse.ArgumentParser(description="Serve working/reports over local HTTP")
    ap.add_argument("--port", type=int, default=int(cfg.get("reports_http_port") or 8765))
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument(
        "--directory",
        type=Path,
        default=None,
        help="Directory to serve (default: reports_dir from archaeology.config.json)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Validate the directory and print the URL without serving",
    )
    args = ap.parse_args(argv)

    root = args.directory or reports_root()
    if not root.is_dir():
        print(
            f"reports dir missing: {root} (run `python -m tools inventory` first)",
            file=sys.stderr,
        )
        return 1

    url = f"http://{args.bind}:{args.port}/"
    print(f"serving {root} at {url}")
    if args.check:
        return 0

    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    with ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print("Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
