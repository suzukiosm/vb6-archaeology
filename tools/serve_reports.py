#!/usr/bin/env python3
"""Serve the reports directory over local HTTP.

Report HTML pulls sibling assets, so `file://` viewing is unreliable; always go
through a loopback HTTP server.

    python -m tools serve
    python -m tools serve --port 8790
    python -m tools serve --check      # validate directory, print URL, exit

Dynamic view (no pre-generation required):

    http://127.0.0.1:8765/excerpt
    http://127.0.0.1:8765/excerpt?stem=mini_vbp
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402


class ReportsHandler(SimpleHTTPRequestHandler):
    """Static reports dir plus `/excerpt` reimplementation summary."""

    def do_GET(self) -> None:  # noqa: N802 — stdlib name
        parsed = urlparse(self.path)
        if parsed.path in ("/excerpt", "/excerpt.html", "/_reimpl.html"):
            self._serve_excerpt(parse_qs(parsed.query))
            return
        super().do_GET()

    def _serve_excerpt(self, query: dict[str, list[str]]) -> None:
        # Late import keeps --check fast when excerpt deps are unused.
        from reimpl_excerpt import find_inventory, write_excerpt

        root = Path(self.directory)
        stem = (query.get("stem") or [None])[0]
        try:
            if stem:
                inv = find_inventory(root, Path(f"{stem}_inventory.json"))
            else:
                inv = find_inventory(root, None)
            # Build into memory via write to a temp name under reports, then read —
            # write_excerpt already targets reports; reuse for consistent HTML.
            dest = write_excerpt(inventory_path=inv, reports=root)
            body = dest.read_bytes()
        except SystemExit as exc:
            msg = str(exc) or "excerpt failed"
            payload = msg.encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        except Exception as exc:  # noqa: BLE001 — surface to browser
            payload = f"excerpt error: {exc}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
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
    print(f"reimpl excerpt: {url}excerpt")
    if args.check:
        return 0

    handler = partial(ReportsHandler, directory=str(root))
    with ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print("Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
