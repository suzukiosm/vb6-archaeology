#!/usr/bin/env python3
"""Build a short reimplementation excerpt HTML from existing reports.

Surfaces: Form list, Show relations, GoTo skip counts (from skeletons),
unticked procedures. Agents use this instead of pasting entire
inventory/deep-read into chat.

    python -m tools excerpt
    python -m tools excerpt --inventory working/reports/mini_vbp_inventory.json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.config import load_config, reports_root, skeletons_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

TICK_TARGET_RE = re.compile(
    r'data-target="([^"#]+)#([^"]+)"',
    re.IGNORECASE,
)


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def find_inventory(reports: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit if explicit.is_file() else reports / explicit.name
        if not path.is_file():
            raise SystemExit(f"inventory not found: {path}")
        return path
    matches = sorted(reports.glob("*_inventory.json"))
    if not matches:
        raise SystemExit(
            f"no *_inventory.json under {reports} "
            "(run `python -m tools inventory` first)"
        )
    cfg = load_config()
    preferred = (cfg.get("default_extract") or "").strip()
    if preferred:
        for m in matches:
            if m.name.startswith(f"{preferred}_"):
                return m
    return matches[0]


def load_ticked(comprehension: Path) -> set[tuple[str, str]]:
    if not comprehension.is_file():
        return set()
    text = comprehension.read_text(encoding="utf-8", errors="replace")
    return {(m.group(1), m.group(2)) for m in TICK_TARGET_RE.finditer(text)}


def load_goto_counts(skeletons: Path) -> dict[str, dict[str, int]]:
    """Per-form GoTo skip / label-map counts from skeletons (candidates only)."""
    out: dict[str, dict[str, int]] = {}
    for path in sorted(skeletons.glob("*-skeleton.json")):
        if path.name == "runtime-layout.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        form = (data.get("form") or {}).get("name") or path.stem.replace(
            "-skeleton", ""
        )
        skips = data.get("goto_skipped_stmts") or []
        maps = data.get("goto_label_maps") or []
        subs_with_goto = sum(1 for g in maps if g.get("gotos"))
        out[form] = {
            "skip_stmts": len(skips),
            "subs_with_goto": subs_with_goto,
        }
    return out


def load_show_rows(skeletons: Path, vb_names: set[str]) -> list[dict]:
    """Collect outbound Show rows from *-skeleton.json show_map / show_style."""
    rows: list[dict] = []
    for path in sorted(skeletons.glob("*-skeleton.json")):
        if path.name == "runtime-layout.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        form = (data.get("form") or {}).get("name") or path.stem.replace(
            "-skeleton", ""
        )
        self_style = data.get("show_style") or {}
        if self_style:
            rows.append(
                {
                    "kind": "self",
                    "from_form": form,
                    "sub": "—",
                    "target": form,
                    "show_style": self_style.get("show_style", "unknown"),
                    "evidence": self_style.get("evidence") or "",
                    "line": "",
                }
            )
        for entry in data.get("show_map") or []:
            calls = entry.get("calls") or []
            if calls:
                for call in calls:
                    target = call.get("target") or ""
                    rows.append(
                        {
                            "kind": "show",
                            "from_form": form,
                            "sub": entry.get("sub") or "",
                            "target": target,
                            "show_style": call.get("show_style", "unknown"),
                            "evidence": call.get("arg")
                            or call.get("text")
                            or "",
                            "line": call.get("line") or entry.get("line") or "",
                            "known_target": target in vb_names if target else False,
                        }
                    )
            else:
                for target in entry.get("shows") or []:
                    rows.append(
                        {
                            "kind": "show",
                            "from_form": form,
                            "sub": entry.get("sub") or "",
                            "target": target,
                            "show_style": "unknown",
                            "evidence": "",
                            "line": entry.get("line") or "",
                            "known_target": target in vb_names,
                        }
                    )
    return rows


def load_show_rows_from_inventory(inventory: dict) -> list[dict]:
    """Use inventory Form show_style / show_calls when skeletons are absent."""
    rows: list[dict] = []
    vb_names = {
        (f.get("vb_name") or Path(f.get("file", "")).stem)
        for f in inventory.get("files") or []
        if f.get("type") == "form"
    }
    for f in inventory.get("files") or []:
        if f.get("type") != "form":
            continue
        form = f.get("vb_name") or Path(f.get("file", "")).stem
        self_style = f.get("show_style") or {}
        if self_style:
            rows.append(
                {
                    "kind": "self",
                    "from_form": form,
                    "sub": "—",
                    "target": form,
                    "show_style": self_style.get("show_style", "unknown"),
                    "evidence": self_style.get("evidence") or "",
                    "line": "",
                }
            )
        for call in f.get("show_calls") or []:
            target = call.get("target") or ""
            rows.append(
                {
                    "kind": "show",
                    "from_form": form,
                    "sub": "",
                    "target": target,
                    "show_style": call.get("show_style", "unknown"),
                    "evidence": call.get("arg") or call.get("text") or "",
                    "line": call.get("line") or "",
                    "known_target": target in vb_names if target else False,
                }
            )
    return rows


def merge_show_rows(skeleton_rows: list[dict], inventory_rows: list[dict]) -> list[dict]:
    """Prefer skeleton (live-filtered) Show rows; keep inventory self styles as fill."""
    if not skeleton_rows:
        return inventory_rows
    skel_shows = [r for r in skeleton_rows if r["kind"] == "show"]
    skel_self_forms = {r["from_form"] for r in skeleton_rows if r["kind"] == "self"}
    inv_self = [
        r
        for r in inventory_rows
        if r["kind"] == "self" and r["from_form"] not in skel_self_forms
    ]
    skel_self = [r for r in skeleton_rows if r["kind"] == "self"]
    if skel_shows:
        return skel_self + inv_self + skel_shows
    # Skeletons had only self styles — use inventory outbound
    inv_shows = [r for r in inventory_rows if r["kind"] == "show"]
    return skel_self + inv_self + inv_shows


def build_excerpt_html(
    inventory: dict,
    *,
    ticked: set[tuple[str, str]],
    show_rows: list[dict],
    stem: str,
    goto_counts: dict[str, dict[str, int]] | None = None,
) -> str:
    forms = [f for f in inventory.get("files") or [] if f.get("type") == "form"]
    goto_counts = goto_counts or {}

    form_rows = []
    goto_total = 0
    for f in forms:
        vb = f.get("vb_name") or ""
        inv_style = (f.get("show_style") or {}).get("show_style")
        self = next(
            (
                r
                for r in show_rows
                if r["kind"] == "self" and r["from_form"] == vb
            ),
            None,
        )
        style = inv_style or (self or {}).get("show_style", "unknown")
        gc = goto_counts.get(vb) or {}
        skip_n = int(gc.get("skip_stmts") or 0)
        goto_subs = int(gc.get("subs_with_goto") or 0)
        goto_total += skip_n
        if skip_n or goto_subs:
            goto_cell = f"{skip_n} skip / {goto_subs} Sub"
        else:
            goto_cell = "—"
        deep_key = vb.lower() if vb else ""
        deep_link = (
            f"<a href=\"./{_esc(deep_key)}_deep_read.md\">deep-read</a>"
            if deep_key
            else "—"
        )
        form_rows.append(
            "<tr>"
            f"<td>{_esc(f.get('file'))}</td>"
            f"<td><code>{_esc(vb)}</code></td>"
            f"<td>{_esc(f.get('form_kind'))}</td>"
            f"<td><code>{_esc(style)}</code></td>"
            f"<td>{_esc(goto_cell)}</td>"
            f"<td>{deep_link}</td>"
            f"<td>{_esc(f.get('control_count'))}</td>"
            f"<td>{_esc(len(f.get('procedures') or []))}</td>"
            "</tr>"
        )

    show_html = []
    for r in show_rows:
        if r["kind"] != "show":
            continue
        flag = ""
        if r.get("target") and not r.get("known_target"):
            flag = " <em>(target not in inventory forms)</em>"
        show_html.append(
            "<tr>"
            f"<td><code>{_esc(r['from_form'])}</code></td>"
            f"<td><code>{_esc(r['sub'])}</code></td>"
            f"<td>L{_esc(r['line'])}</td>"
            f"<td><code>{_esc(r['target'])}</code>{flag}</td>"
            f"<td><code>{_esc(r['show_style'])}</code></td>"
            f"<td>{_esc(r.get('evidence') or '—')}</td>"
            "</tr>"
        )

    unticked = []
    for f in inventory.get("files") or []:
        file_name = f.get("file") or ""
        for proc in f.get("procedures") or []:
            name = proc.get("name") or ""
            if (file_name, name) in ticked:
                continue
            unticked.append(
                "<tr>"
                f"<td>{_esc(file_name)}</td>"
                f"<td><code>{_esc(name)}</code></td>"
                f"<td>{_esc(proc.get('role'))}</td>"
                f"<td>L{_esc(proc.get('line_start'))}-{_esc(proc.get('line_end'))}</td>"
                "</tr>"
            )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<title>reimpl excerpt — {_esc(stem)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 960px; }}
  h1 {{ font-size: 1.25rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: .75rem 0 1.5rem; }}
  th, td {{ border: 1px solid #e5e7eb; padding: .35rem .5rem; text-align: left;
            vertical-align: top; font-size: .9rem; }}
  th {{ background: #f8fafc; }}
  code {{ font-size: .85em; }}
  .meta {{ color: #64748b; font-size: .9rem; }}
  .note {{ background: #fffbeb; border: 1px solid #fcd34d; padding: .6rem .8rem;
           border-radius: .4rem; }}
</style>
</head>
<body>
<h1>再実装向け抜粋 — <code>{_esc(stem)}</code></h1>
<p class="meta">Form 一覧 · Show 関係 · GoTo 飛び越え件数 · 未 tick。詳細は inventory / deep-read / comprehension を正とする。</p>
<p class="note">調査完了 ≠ 製品 UI 完了。出荷前は
<code>docs/reimplementation-handoff.md</code> を通す。<br/>
<code>show_style</code> はヒューリスティック候補（断定しない）。
機械は <code>navigate</code> を出さない — <code>unknown</code> ≠ フルページ遷移。<br/>
GoTo 列は skeleton の飛び越え<strong>候補</strong>件数（デッド確定ではない）。deep-read を開いて確認する。
{" GoTo skip 合計: " + str(goto_total) + "。" if goto_total else ""}</p>

<h2>Form 一覧（{len(forms)}）</h2>
<table>
<thead><tr><th>file</th><th>VB_Name</th><th>kind</th><th>self show_style</th><th>GoTo</th><th>詳細</th><th>Ctrl</th><th>Proc</th></tr></thead>
<tbody>
{''.join(form_rows) or '<tr><td colspan="8">（form なし）</td></tr>'}
</tbody>
</table>

<h2>Show 関係（skeleton show_map）</h2>
<table>
<thead><tr><th>from</th><th>Sub</th><th>L</th><th>target</th><th>show_style</th><th>evidence</th></tr></thead>
<tbody>
{''.join(show_html) or '<tr><td colspan="6">（show_map なし — deep-read を先に実行）</td></tr>'}
</tbody>
</table>

<h2>未 tick プロシージャ（{len(unticked)} / inventory {inventory.get('proc_total', '?')}）</h2>
<table>
<thead><tr><th>file</th><th>name</th><th>role</th><th>lines</th></tr></thead>
<tbody>
{''.join(unticked) or '<tr><td colspan="4">すべて tick 済み、または comprehension なし</td></tr>'}
</tbody>
</table>

<p class="meta">生成: <code>python -m tools excerpt</code> · 閲覧: <code>python -m tools serve</code> →
<a href="./{_esc(stem)}_reimpl_excerpt.html">{_esc(stem)}_reimpl_excerpt.html</a>
· 動的: <a href="/excerpt?stem={_esc(stem)}">/excerpt?stem={_esc(stem)}</a></p>
</body>
</html>
"""


def write_excerpt(
    *,
    inventory_path: Path,
    reports: Path | None = None,
    skeletons: Path | None = None,
    out: Path | None = None,
) -> Path:
    reports = reports or reports_root()
    skeletons = skeletons or skeletons_root()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    stem = inventory.get("stem") or inventory_path.name.replace("_inventory.json", "")
    comprehension = reports / f"{stem}_comprehension.html"
    ticked = load_ticked(comprehension)
    forms = [f for f in inventory.get("files") or [] if f.get("type") == "form"]
    vb_names = {
        (f.get("vb_name") or Path(f.get("file", "")).stem) for f in forms
    }
    skel_rows = load_show_rows(skeletons, vb_names)
    inv_rows = load_show_rows_from_inventory(inventory)
    show_rows = merge_show_rows(skel_rows, inv_rows)
    goto_counts = load_goto_counts(skeletons)
    # Prefer inventory self style on the Form table when present
    inv_self = {
        r["from_form"]: r["show_style"]
        for r in inv_rows
        if r["kind"] == "self"
    }
    for r in show_rows:
        if r["kind"] == "self" and r["from_form"] in inv_self:
            r["show_style"] = inv_self[r["from_form"]]
    html_text = build_excerpt_html(
        inventory,
        ticked=ticked,
        show_rows=show_rows,
        stem=stem,
        goto_counts=goto_counts,
    )
    dest = out or (reports / f"{stem}_reimpl_excerpt.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html_text, encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Build a short reimplementation excerpt HTML"
    )
    ap.add_argument("--inventory", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    reports = reports_root()
    inv = find_inventory(reports, args.inventory)
    dest = write_excerpt(inventory_path=inv, reports=reports, out=args.out)
    print(f"excerpt -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
