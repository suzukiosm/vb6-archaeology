#!/usr/bin/env python3
"""Build the comprehension report skeleton and append evidence ticks.

The comprehension report is the one artifact that used to be written entirely by
hand, which is where hallucinated procedure names creep in. This tool keeps the
structure fixed and refuses to add a tick whose target is absent from the
inventory name set, so every tick heading is anchored to a real procedure.

    python -m tools comprehend
    python -m tools comprehend --add-tick Form_Load
    python -m tools comprehend --add-tick Command1_Click@Form1.frm --layer C

Existing prose is never rewritten: new ticks are inserted just before the
`<!-- TICKS:END -->` marker.
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

from lib.config import reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

TICKS_BEGIN = "<!-- TICKS -->"
TICKS_END = "<!-- TICKS:END -->"
TICK_ATTR_RE = re.compile(r'data-tick="(\d+)"')

LAYERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "A": (
        "静的構造",
        (
            "inventory を生成し End 数照合が通っている",
            "全ファイルの役割区分（Form / Module / Class）を把握した",
            "イベントプロシージャの一覧を把握した",
        ),
    ),
    "B": (
        "データ契約",
        (
            "参照する外部データ（DB / データファイル）を列挙した",
            "主要レコードの項目対応を証拠つきで書いた",
        ),
    ),
    "C": (
        "UI・操作",
        (
            "起動フォームと初期表示の経路を確認した",
            "モード変数と分岐を確認した",
            "生きているメニュー・ボタンと死んでいるものを区別した",
        ),
    ),
    "D": (
        "実行依存",
        (
            "外部 EXE / COM / ネットワークパス依存を列挙した",
            "実行時レイアウト（座標・可視性）を確認した",
        ),
    ),
    "E": (
        "システム境界",
        (
            "関連プロジェクトとの責務分担を確認した",
            "本プロジェクト単体では判断できない箇所を明示した",
        ),
    ),
}

STYLE = """
:root { color-scheme: light dark; }
body { font-family: "Segoe UI", "Yu Gothic UI", sans-serif; line-height: 1.7;
       margin: 0 auto; max-width: 60rem; padding: 2rem 1.5rem; }
h1 { margin-bottom: .2rem; }
.meta { color: #6b7280; font-size: .9rem; }
.rules { background: #f8fafc; border-left: 4px solid #64748b; padding: .8rem 1rem; }
.progress { font-weight: 600; }
ul.checklist { list-style: none; padding-left: 0; }
ul.checklist li { border-bottom: 1px solid #e5e7eb; padding: .35rem 0; }
ul.checklist li::before { content: "[ ] "; font-family: monospace; }
ul.checklist li[data-status="done"]::before { content: "[x] "; }
ul.checklist li[data-status="partial"]::before { content: "[~] "; }
section.tick { border: 1px solid #e5e7eb; border-radius: .5rem;
               margin: 1.2rem 0; padding: .8rem 1.2rem; }
section.tick h3 { margin: .2rem 0 .6rem; }
.src { color: #6b7280; font-size: .85rem; font-weight: 400; }
code { background: #f1f5f9; border-radius: .25rem; padding: 0 .25rem; }
@media (prefers-color-scheme: dark) {
  .rules { background: #1f2937; }
  code, ul.checklist li { background: transparent; }
}
""".strip()

SCRIPT = """
document.addEventListener('DOMContentLoaded', () => {
  const items = document.querySelectorAll('ul.checklist li');
  const done = document.querySelectorAll('ul.checklist li[data-status="done"]');
  const ticks = document.querySelectorAll('section.tick');
  const pct = items.length ? Math.round((done.length / items.length) * 100) : 0;
  document.getElementById('progress').textContent =
    `チェックリスト ${done.length}/${items.length} (${pct}%) · tick ${ticks.length} 件`;
});
""".strip()


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def resolve_inventory(arg: Path | None) -> Path:
    if arg is not None:
        path = arg if arg.is_absolute() else REPO_ROOT / arg
        if not path.is_file():
            raise SystemExit(f"inventory not found: {path}")
        return path.resolve()
    root = reports_root()
    candidates = sorted(root.glob("*_inventory.json")) if root.is_dir() else []
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise SystemExit(
            f"no *_inventory.json under {root}; run `python -m tools inventory` first"
        )
    names = ", ".join(p.name for p in candidates)
    raise SystemExit(f"multiple inventories ({names}); pass --inventory <path>")


def load_inventory(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "files" not in data:
        raise SystemExit(f"not an inventory JSON: {path}")
    return data


def find_procedure(data: dict, proc: str, file_hint: str | None) -> dict:
    """Locate a procedure in the inventory, or fail with the reason."""
    wanted = proc.strip().lower()
    hint = (Path(file_hint).name.lower() if file_hint else None)
    matches: list[dict] = []
    for entry in data.get("files") or []:
        fname = str(entry.get("file") or "")
        base = Path(fname).name.lower()
        if hint and base != hint and Path(base).stem != Path(hint).stem:
            continue
        for record in entry.get("procedures") or []:
            if str(record.get("name", "")).strip().lower() == wanted:
                matches.append({**record, "file": Path(fname).name})
    if not matches:
        scope = f" in {file_hint}" if file_hint else ""
        raise SystemExit(
            f"'{proc}' is not in the inventory{scope}. "
            "Ticks may only target procedures the inventory lists "
            f"({Path(str(data.get('vbp') or 'inventory')).name}); "
            "regenerate the inventory if the source really has it."
        )
    if len(matches) > 1:
        files = ", ".join(sorted({m["file"] for m in matches}))
        raise SystemExit(
            f"'{proc}' exists in several files ({files}); "
            f"disambiguate with --add-tick {proc}@<file>"
        )
    return matches[0]


def render_checklist() -> str:
    blocks = []
    for key, (title, items) in LAYERS.items():
        rows = "\n".join(
            f'      <li data-layer="{key}" data-status="todo">{esc(item)}</li>'
            for item in items
        )
        blocks.append(
            f"    <h3>層 {key} — {esc(title)}</h3>\n"
            f'    <ul class="checklist">\n{rows}\n    </ul>'
        )
    return "\n".join(blocks)


def render_skeleton(data: dict, inventory_path: Path) -> str:
    stem = str(data.get("stem") or inventory_path.stem.replace("_inventory", ""))
    file_count = data.get("file_count", 0)
    proc_total = data.get("proc_total", 0)
    inv_rel = inventory_path.name
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{esc(stem)} — comprehension</title>
<style>
{STYLE}
</style>
</head>
<body>
<h1>{esc(stem)} — comprehension</h1>
<p class="meta">
  事実の土台: <code>{esc(inv_rel)}</code>
  （{esc(file_count)} files / {esc(proc_total)} procedures）·
  生成: <code>python -m tools comprehend</code>
</p>
<p class="progress" id="progress">チェックリスト集計中…</p>

<div class="rules">
  <strong>記入規律</strong>
  <ul>
    <li>事実と推定を混ぜない。推定には証拠（ファイル・プロシージャ・行）を必ず添える。</li>
    <li>inventory に無い名前は書かない。tick 追加はこのツール経由で行う。</li>
    <li>達成率はチェックリストの進捗であって、アプリの完全理解ではない。</li>
  </ul>
</div>

<h2>チェックリスト</h2>
<p class="meta">進めた項目の <code>data-status</code> を <code>todo</code> → <code>partial</code> → <code>done</code> に変える。</p>
{render_checklist()}

<h2>Ticks</h2>
{TICKS_BEGIN}
{TICKS_END}

<script>
{SCRIPT}
</script>
</body>
</html>
"""


def render_tick(number: int, record: dict, layer: str) -> str:
    name = record.get("name", "")
    file_name = record.get("file", "")
    start, end = record.get("line_start"), record.get("line_end")
    where = f"{file_name} L{start}-{end}" if start and end else file_name
    layer_title = LAYERS.get(layer, ("", ()))[0]
    return f"""<section class="tick" data-tick="{number}" data-layer="{esc(layer)}" data-target="{esc(file_name)}#{esc(name)}">
  <h3>Tick {number} — <code>{esc(name)}</code> <span class="src">{esc(where)} · 層 {esc(layer)} {esc(layer_title)}</span></h3>
  <h4>事実</h4>
  <ul><li>（CP932 で本文を読み、確定した内容だけ書く）</li></ul>
  <h4>読解（推定）— 証拠必須</h4>
  <ul>
    <li>主張: </li>
    <li>証拠: <code>{esc(file_name)}</code> L{esc(start or "?")}-{esc(end or "?")}</li>
    <li>反証・例外: </li>
  </ul>
  <h4>入出力</h4>
  <ul>
    <li>読む: </li>
    <li>書く: </li>
    <li>呼ぶ: （精読で確認した分のみ）</li>
  </ul>
  <h4>product_ui_notes（任意・製品面）</h4>
  <ul>
    <li>隠す: （VB Caption / MsgBox / 拠点名 / debug meta など。無ければ「なし」）</li>
    <li>言い換える: </li>
    <li>Show: mdi_child | modal_overlay | navigate | 未確認</li>
  </ul>
</section>"""


def next_tick_number(text: str) -> int:
    numbers = [int(m) for m in TICK_ATTR_RE.findall(text)]
    return max(numbers) + 1 if numbers else 1


def insert_tick(text: str, tick_html: str, report: Path) -> str:
    if TICKS_END not in text:
        raise SystemExit(
            f"{report.name} has no {TICKS_END} marker; "
            "it was not generated by `python -m tools comprehend`"
        )
    return text.replace(TICKS_END, f"{tick_html}\n{TICKS_END}", 1)


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Scaffold the comprehension report and append evidence ticks"
    )
    ap.add_argument("--inventory", type=Path, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Report path (default: <reports_dir>/<stem>_comprehension.html)",
    )
    ap.add_argument(
        "--add-tick",
        metavar="PROC[@FILE]",
        help="Append a tick for an inventory procedure",
    )
    ap.add_argument("--layer", choices=sorted(LAYERS), default="A")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing report skeleton (discards written prose)",
    )
    args = ap.parse_args(argv)

    inventory_path = resolve_inventory(args.inventory)
    data = load_inventory(inventory_path)
    stem = str(data.get("stem") or inventory_path.stem.replace("_inventory", ""))
    report = args.out or (reports_root() / f"{stem}_comprehension.html")
    if not report.is_absolute():
        report = REPO_ROOT / report

    report.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if args.force or not report.is_file():
        report.write_text(render_skeleton(data, inventory_path), encoding="utf-8")
        created = True
        print(f"skeleton {'rewritten' if args.force else 'created'}: {report}")
    elif not args.add_tick:
        print(f"skeleton kept (already written): {report}")

    if args.add_tick:
        target, _, file_hint = args.add_tick.partition("@")
        record = find_procedure(data, target, file_hint or None)
        text = report.read_text(encoding="utf-8")
        number = next_tick_number(text)
        text = insert_tick(text, render_tick(number, record, args.layer), report)
        report.write_text(text, encoding="utf-8")
        print(f"tick {number} added: {record['file']}#{record['name']} -> {report}")
    elif not created:
        print("nothing to add (pass --add-tick PROC to append a tick)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
