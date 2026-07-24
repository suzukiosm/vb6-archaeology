#!/usr/bin/env python3
"""Deterministic VB6 project inventory: VBP -> files -> procedures.

Reads an extracted VBP (CP932) and lists, per source file, every procedure
definition found at line start. No call-graph guessing; only facts:
  - VBP metadata (Startup, Title, form/module list in VBP order)
  - per file: VB_Name, form kind, controls (from the .frm header)
  - per procedure: kind, visibility, line range, event-handler classification

Outputs <stem>_inventory.json / .md / .html into working/reports/.
Read-only on sources.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.config import decode_vb6_bytes, reports_root  # noqa: E402
from lib.vbparse import iter_logical_lines  # noqa: E402

PROC_RE = re.compile(
    r"^(?:(Public|Private|Friend)\s+)?(?:Static\s+)?"
    r"(Sub|Function|Property\s+(?:Get|Let|Set))\s+([A-Za-z_]\w*)",
    re.IGNORECASE,
)
DECLARE_RE = re.compile(
    r"^(?:(Public|Private)\s+)?Declare\s+(Sub|Function)\s+(\w+)\s+Lib\s+\"([^\"]+)\"",
    re.IGNORECASE,
)
END_RE = re.compile(r"^End\s+(Sub|Function|Property)\b", re.IGNORECASE)
CONTROL_RE = re.compile(r"^\s*Begin\s+([\w.]+)\s+(\w+)")
VBNAME_RE = re.compile(r'^Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)


def decode(raw: bytes) -> str:
    """Config-driven decode (cp932 primary + fallbacks from archaeology.config.json)."""
    return decode_vb6_bytes(raw)


def parse_vbp(vbp_path: Path) -> dict:
    text = decode(vbp_path.read_bytes())
    forms: list[str] = []
    modules: list[dict] = []
    meta: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Form="):
            name = line.split("=", 1)[1].strip()
            if name not in forms:
                forms.append(name)
        elif line.startswith("Module="):
            ident, _, fname = line.split("=", 1)[1].partition(";")
            modules.append({"module": ident.strip(), "file": fname.strip()})
        elif line.startswith(("Startup=", "Title=", "ExeName32=", "IconForm=", "Name=")):
            key, _, val = line.partition("=")
            meta[key] = val.strip('"')
    return {"forms": forms, "modules": modules, "meta": meta}


def parse_form_header(lines: list[str]) -> tuple[str | None, list[dict]]:
    """Return (form kind e.g. VB.Form / VB.MDIForm, controls) from a .frm header."""
    form_kind: str | None = None
    controls: list[dict] = []
    for line in lines:
        if VBNAME_RE.match(line):
            break  # header ends where attributes/code begin
        m = CONTROL_RE.match(line)
        if not m:
            continue
        cls, name = m.group(1), m.group(2)
        if form_kind is None:
            form_kind = cls
        else:
            controls.append({"class": cls, "name": name})
    return form_kind, controls


def parse_procedures(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Return (procedures, declares).

    Line numbers are physical (1-based). ``_`` continuations are folded so that
    multi-line ``Declare`` signatures capture the full Lib target, while the
    reported ``line`` stays the physical line where the statement begins.
    """
    procs: list[dict] = []
    declares: list[dict] = []
    logical = iter_logical_lines(lines)
    in_header = bool(logical) and logical[0].text.startswith("VERSION")
    open_proc: dict | None = None
    for ll in logical:
        stripped = ll.text
        if in_header:
            if VBNAME_RE.match(stripped):
                in_header = False
            continue
        dm = DECLARE_RE.match(stripped)
        if dm and open_proc is None:
            declares.append(
                {
                    "name": dm.group(3),
                    "kind": dm.group(2).capitalize(),
                    "visibility": (dm.group(1) or "Public").capitalize(),
                    "lib": dm.group(4),
                    "line": ll.phys_start,
                }
            )
            continue
        if open_proc is None:
            pm = PROC_RE.match(stripped)
            # a Declare line also matches PROC_RE via "Sub|Function"? no: Declare comes first
            if pm and not stripped.lower().startswith("declare"):
                kind = re.sub(r"\s+", " ", pm.group(2)).title()
                open_proc = {
                    "name": pm.group(3),
                    "kind": kind,
                    "visibility": (pm.group(1) or "Public").capitalize(),
                    "line_start": ll.phys_start,
                }
        else:
            if END_RE.match(stripped):
                open_proc["line_end"] = ll.phys_end
                open_proc["lines"] = ll.phys_end - open_proc["line_start"] + 1
                procs.append(open_proc)
                open_proc = None
    if open_proc is not None:  # unterminated (should not happen in valid VB6)
        open_proc["line_end"] = len(lines)
        open_proc["lines"] = len(lines) - open_proc["line_start"] + 1
        open_proc["unterminated"] = True
        procs.append(open_proc)
    return procs, declares


def classify_events(procs: list[dict], control_names: set[str], is_form: bool) -> None:
    prefixes = {n.lower() for n in control_names}
    if is_form:
        prefixes |= {"form", "mdiform"}
    for p in procs:
        name = p["name"]
        owner = None
        # longest matching "<owner>_" prefix wins (owners may contain underscores)
        for i in range(len(name) - 1, 0, -1):
            if name[i] == "_" and name[:i].lower() in prefixes:
                owner = name[:i]
                break
        if owner is not None:
            p["role"] = "event"
            p["event_owner"] = owner
            p["event_name"] = name[len(owner) + 1 :]
        else:
            p["role"] = "general"


def inventory_file(path: Path) -> dict:
    lines = decode(path.read_bytes()).splitlines()
    vb_name = None
    for line in lines:
        m = VBNAME_RE.match(line)
        if m:
            vb_name = m.group(1)
            break
    is_form = path.suffix.lower() == ".frm"
    form_kind, controls = parse_form_header(lines) if is_form else (None, [])
    procs, declares = parse_procedures(lines)
    classify_events(procs, {c["name"] for c in controls}, is_form)
    return {
        "file": path.name,
        "vb_name": vb_name,
        "form_kind": form_kind,
        "total_lines": len(lines),
        "control_count": len(controls),
        "controls": controls,
        "declares": declares,
        "procedures": procs,
    }


def build_report(extract_dir: Path, vbp_path: Path) -> dict:
    vbp = parse_vbp(vbp_path)
    files: list[dict] = []
    missing: list[str] = []
    ordered = [(f, "form") for f in vbp["forms"]] + [
        (m["file"], "module") for m in vbp["modules"]
    ]
    for fname, ftype in ordered:
        p = extract_dir / fname
        if not p.is_file():
            missing.append(fname)
            continue
        info = inventory_file(p)
        info["type"] = ftype
        files.append(info)
    listed = {f["file"].lower() for f in files} | {m.lower() for m in missing}
    extras = sorted(
        p.name
        for p in extract_dir.iterdir()
        if p.suffix.lower() in (".frm", ".bas", ".cls") and p.name.lower() not in listed
    )
    return {
        "vbp": vbp_path.name,
        "stem": vbp_path.stem,
        "extract_dir": str(extract_dir.resolve()),
        "meta": vbp["meta"],
        "file_count": len(files),
        "proc_total": sum(len(f["procedures"]) for f in files),
        "files": files,
        "missing_in_extract": missing,
        "not_in_vbp": extras,
    }


def write_markdown(report: dict, out: Path) -> None:
    meta = report["meta"]
    L = [
        f"# {report['vbp']} インベントリ（VBP → ファイル → プロシージャ）",
        "",
        f"- Startup: `{meta.get('Startup', '?')}` / Title: `{meta.get('Title', '?')}` / Exe: `{meta.get('ExeName32', '?')}`",
        f"- ファイル: **{report['file_count']}**（VBP 記載順） / プロシージャ合計: **{report['proc_total']}**",
        "- 行頭のプロシージャ定義のみを機械抽出（呼び出し推定なし）。行番号は抽出コピーの実ファイル基準。",
        "",
    ]
    if report["missing_in_extract"]:
        L.append(f"- ⚠ VBP に記載だが抽出フォルダに無い: {', '.join(report['missing_in_extract'])}")
    if report["not_in_vbp"]:
        L.append(f"- ⚠ 抽出フォルダにあるが VBP 未記載: {', '.join(report['not_in_vbp'])}")
    L.append("")
    L.append("## 目次")
    L.append("")
    L.append("| # | ファイル | 種別 | VB_Name | 行数 | コントロール | プロシージャ |")
    L.append("|---:|---|---|---|---:|---:|---:|")
    for i, f in enumerate(report["files"], 1):
        kind = f["form_kind"] or ("Module" if f["type"] == "module" else "?")
        L.append(
            f"| {i} | `{f['file']}` | {kind} | `{f['vb_name'] or '?'}` "
            f"| {f['total_lines']:,} | {f['control_count'] or '-'} | {len(f['procedures'])} |"
        )
    L.append("")
    for f in report["files"]:
        kind = f["form_kind"] or "Module"
        L.append(f"## {f['file']} — `{f['vb_name'] or '?'}`（{kind}, {f['total_lines']:,} 行）")
        L.append("")
        events = [p for p in f["procedures"] if p["role"] == "event"]
        general = [p for p in f["procedures"] if p["role"] == "general"]
        if events:
            L.append(f"### イベントハンドラ（{len(events)}）")
            L.append("")
            L.append("| コントロール | イベント | プロシージャ | 行 | 規模 |")
            L.append("|---|---|---|---|---:|")
            for p in sorted(events, key=lambda x: (x["event_owner"].lower(), x["event_name"].lower())):
                L.append(
                    f"| `{p['event_owner']}` | {p['event_name']} | `{p['name']}` "
                    f"| {p['line_start']}–{p['line_end']} | {p['lines']} |"
                )
            L.append("")
        if general:
            L.append(f"### Sub / Function（{len(general)}）")
            L.append("")
            L.append("| 種別 | 名前 | 可視性 | 行 | 規模 |")
            L.append("|---|---|---|---|---:|")
            for p in general:
                L.append(
                    f"| {p['kind']} | `{p['name']}` | {p['visibility']} "
                    f"| {p['line_start']}–{p['line_end']} | {p['lines']} |"
                )
            L.append("")
        if f["declares"]:
            L.append(f"### API 宣言（Declare, {len(f['declares'])}）")
            L.append("")
            for d in f["declares"]:
                L.append(f"- `{d['name']}` ({d['kind']}, {d['lib']}) — L{d['line']}")
            L.append("")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_html(report: dict, out: Path) -> None:
    meta = report["meta"]
    e = html.escape

    def proc_rows(procs: list[dict], event: bool) -> str:
        rows = []
        for p in procs:
            loc = f"{p['line_start']}–{p['line_end']}"
            if event:
                rows.append(
                    f"<tr><td><code>{e(p['event_owner'])}</code></td>"
                    f"<td>{e(p['event_name'])}</td><td><code>{e(p['name'])}</code></td>"
                    f"<td>{loc}</td><td class='num'>{p['lines']}</td></tr>"
                )
            else:
                rows.append(
                    f"<tr><td>{e(p['kind'])}</td><td><code>{e(p['name'])}</code></td>"
                    f"<td>{e(p['visibility'])}</td><td>{loc}</td>"
                    f"<td class='num'>{p['lines']}</td></tr>"
                )
        return "".join(rows)

    toc_rows = []
    sections = []
    for i, f in enumerate(report["files"], 1):
        kind = f["form_kind"] or ("Module" if f["type"] == "module" else "?")
        anchor = f"f{i}"
        toc_rows.append(
            f"<tr><td class='num'>{i}</td>"
            f"<td><a href='#{anchor}'><code>{e(f['file'])}</code></a></td>"
            f"<td>{e(kind)}</td><td><code>{e(f['vb_name'] or '?')}</code></td>"
            f"<td class='num'>{f['total_lines']:,}</td>"
            f"<td class='num'>{f['control_count'] or '-'}</td>"
            f"<td class='num'>{len(f['procedures'])}</td></tr>"
        )
        events = sorted(
            (p for p in f["procedures"] if p["role"] == "event"),
            key=lambda x: (x["event_owner"].lower(), x["event_name"].lower()),
        )
        general = [p for p in f["procedures"] if p["role"] == "general"]
        blocks = []
        if events:
            blocks.append(
                f"<h4>イベントハンドラ（{len(events)}）</h4>"
                "<table><tr><th>コントロール</th><th>イベント</th><th>プロシージャ</th>"
                "<th>行</th><th>規模</th></tr>" + proc_rows(events, True) + "</table>"
            )
        if general:
            blocks.append(
                f"<h4>Sub / Function（{len(general)}）</h4>"
                "<table><tr><th>種別</th><th>名前</th><th>可視性</th><th>行</th>"
                "<th>規模</th></tr>" + proc_rows(general, False) + "</table>"
            )
        if f["declares"]:
            items = "".join(
                f"<li><code>{e(d['name'])}</code>（{e(d['kind'])}, {e(d['lib'])}）L{d['line']}</li>"
                for d in f["declares"]
            )
            blocks.append(f"<h4>API 宣言（{len(f['declares'])}）</h4><ul>{items}</ul>")
        sections.append(
            f"<details id='{anchor}'><summary><b>{e(f['file'])}</b> — "
            f"<code>{e(f['vb_name'] or '?')}</code>（{e(kind)}, {f['total_lines']:,} 行, "
            f"proc {len(f['procedures'])}）</summary>" + "".join(blocks) + "</details>"
        )

    warns = []
    if report["missing_in_extract"]:
        warns.append("VBP 記載だが抽出に無い: " + ", ".join(map(e, report["missing_in_extract"])))
    if report["not_in_vbp"]:
        warns.append("抽出にあるが VBP 未記載: " + ", ".join(map(e, report["not_in_vbp"])))
    warn_html = "".join(f"<p class='warn'>⚠ {w}</p>" for w in warns)

    doc = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>{e(report['vbp'])} インベントリ</title>
<style>
body{{font-family:"Segoe UI",Meiryo,sans-serif;margin:2rem auto;max-width:1100px;line-height:1.5;color:#222}}
table{{border-collapse:collapse;margin:.5rem 0 1rem;width:100%}}
th,td{{border:1px solid #ccc;padding:.25rem .5rem;font-size:.85rem;text-align:left}}
th{{background:#f0f2f5}}
td.num{{text-align:right}}
code{{background:#f4f4f4;padding:0 .2rem}}
details{{border:1px solid #ddd;border-radius:6px;margin:.4rem 0;padding:.3rem .8rem}}
summary{{cursor:pointer;padding:.3rem 0}}
.warn{{color:#a00}}
.meta{{color:#555}}
</style></head><body>
<h1>{e(report['vbp'])} インベントリ（VBP → ファイル → プロシージャ）</h1>
<p class="meta">Startup: <code>{e(meta.get('Startup', '?'))}</code> ／ Title: <code>{e(meta.get('Title', '?'))}</code> ／ Exe: <code>{e(meta.get('ExeName32', '?'))}</code><br>
ファイル {report['file_count']}（VBP 記載順） ／ プロシージャ合計 {report['proc_total']}。
行頭のプロシージャ定義のみを機械抽出（呼び出し推定なし）。行番号は working/extracts の実ファイル基準。</p>
{warn_html}
<h2>目次</h2>
<table><tr><th>#</th><th>ファイル</th><th>種別</th><th>VB_Name</th><th>行数</th><th>Ctrl</th><th>Proc</th></tr>
{''.join(toc_rows)}</table>
<h2>ファイル別詳細</h2>
{''.join(sections)}
</body></html>
"""
    out.write_text(doc, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VB6 project inventory (facts only)")
    parser.add_argument("extract_dir", type=Path)
    parser.add_argument("--vbp", type=Path, default=None, help="default: sole *.vbp in extract_dir")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    root = args.extract_dir if args.extract_dir.is_absolute() else REPO_ROOT / args.extract_dir
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    vbp = args.vbp
    if vbp is None:
        cands = list(root.glob("*.vbp"))
        if len(cands) != 1:
            raise SystemExit(f"expected exactly one .vbp in {root}, found {len(cands)}")
        vbp = cands[0]

    report = build_report(root, vbp)

    out_dir = args.out_dir or reports_root()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = vbp.stem
    json_path = out_dir / f"{stem}_inventory.json"
    md_path = out_dir / f"{stem}_inventory.md"
    html_path = out_dir / f"{stem}_inventory.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(report, md_path)
    write_html(report, html_path)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "md": str(md_path),
                "html": str(html_path),
                "files": report["file_count"],
                "procs": report["proc_total"],
                "missing_in_extract": report["missing_in_extract"],
                "not_in_vbp": report["not_in_vbp"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
