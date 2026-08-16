#!/usr/bin/env python3
"""Serve the reports directory over local HTTP.

Report HTML pulls sibling assets, so `file://` viewing is unreliable; always go
through a loopback HTTP server.

    python -m tools serve
    python -m tools serve --port 8790
    python -m tools serve --check      # validate directory, print URL, exit

    http://127.0.0.1:8765/             # landing (inventory / excerpt / io-catalog / …)
    http://127.0.0.1:8765/excerpt
    http://127.0.0.1:8765/excerpt?stem=mini_vbp
"""

from __future__ import annotations

import argparse
import html
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

LANDING_SECTIONS: tuple[tuple[str, str], ...] = (
    ("excerpt", "excerpt"),
    ("inventory", "inventory"),
    ("comprehension", "comprehension"),
    ("layout", "layout"),
    ("io_catalog", "io-catalog"),
    ("deep_read", "deep-read"),
)
LAYOUT_NAMES = frozenset(
    {"runtime_layout.md", "runtime_layout.json", "form_layout_gap.md"}
)
FILE_URI_NOTE = "file:// では開きません。この HTTP サーバ経由で開いてください。"


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def classify_report(name: str) -> str | None:
    """Map a reports-dir filename to a landing section, or None."""
    lower = name.lower()
    if lower.endswith(("_inventory.html", "_inventory.md", "_inventory.json")):
        return "inventory"
    if lower.endswith("_comprehension.html"):
        return "comprehension"
    if lower.endswith("_reimpl_excerpt.html"):
        return "excerpt"
    if lower in LAYOUT_NAMES:
        return "layout"
    if lower.endswith(("_io_catalog.md", "_io_catalog.json")):
        return "io_catalog"
    if lower.endswith("_deep_read.md"):
        return "deep_read"
    return None


def _link_sort_key(name: str) -> tuple[int, str]:
    ext = Path(name).suffix.lower()
    rank = {".html": 0, ".md": 1, ".json": 2}.get(ext, 9)
    return (rank, name.lower())


def list_report_entries(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in root.iterdir():
        names.append(path.name + ("/" if path.is_dir() else ""))
    return sorted(names, key=str.lower)


def grouped_reports(root: Path) -> dict[str, list[str]]:
    groups = {key: [] for key, _title in LANDING_SECTIONS}
    for name in list_report_entries(root):
        if name.endswith("/"):
            continue
        section = classify_report(name)
        if section is not None:
            groups[section].append(name)
    for key in groups:
        groups[key].sort(key=_link_sort_key)
    return groups


def render_landing(root: Path) -> str:
    """Facts-only index: known report kinds, then the raw directory list."""
    groups = grouped_reports(root)
    all_names = list_report_entries(root)
    blocks: list[str] = []
    for key, title in LANDING_SECTIONS:
        items = []
        if key == "excerpt":
            items.append('<li><a href="/excerpt"><code>/excerpt</code></a>（動的）</li>')
        for name in groups[key]:
            items.append(f'<li><a href="/{_esc(name)}"><code>{_esc(name)}</code></a></li>')
        if key != "excerpt" and not groups[key]:
            items.append("<li>（なし）</li>")
        blocks.append(
            f"<h2>{_esc(title)}</h2>\n<ul>\n" + "\n".join(items) + "\n</ul>"
        )
    dir_items = (
        "\n".join(
            f'<li><a href="/{_esc(name)}"><code>{_esc(name)}</code></a></li>'
            for name in all_names
        )
        or "<li>（空）</li>"
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<title>vb6-archaeology reports</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 52rem; }}
  h1 {{ font-size: 1.25rem; }}
  h2 {{ font-size: 1.05rem; margin-top: 1.4rem; }}
  ul {{ padding-left: 1.2rem; }}
  .note {{ background: #fffbeb; border: 1px solid #fcd34d; padding: .6rem .8rem;
           border-radius: .4rem; }}
  .meta {{ color: #64748b; font-size: .9rem; }}
  code {{ font-size: .85em; }}
</style>
</head>
<body>
<h1>レポート</h1>
<p class="note">{_esc(FILE_URI_NOTE)}</p>
<p class="meta">存在する成果物へのリンクだけ。無い種類は「なし」。呼び出し関係は推定しない。</p>
{chr(10).join(blocks)}
<h2>ディレクトリ</h2>
<ul>
{dir_items}
</ul>
</body>
</html>
"""


class ReportsHandler(SimpleHTTPRequestHandler):
    """Landing at ``/``, static reports dir, plus ``/excerpt``."""

    def do_GET(self) -> None:  # noqa: N802 — stdlib name
        parsed = urlparse(self.path)
        if parsed.path in ("/", ""):
            self._serve_landing()
            return
        if parsed.path in ("/excerpt", "/excerpt.html", "/_reimpl.html"):
            self._serve_excerpt(parse_qs(parsed.query))
            return
        super().do_GET()

    def _serve_landing(self) -> None:
        body = render_landing(Path(self.directory)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
    print(f"landing: {url}")
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
