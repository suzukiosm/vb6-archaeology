# tools — 再利用解析ユーティリティ

使い捨て `working/_*.py` を増やさず、ここに置いて改定する。  
VB6 テキストは **CP932**（`lib/config.py` / `archaeology.config.json`）。  
保護ディレクトリへは書込しない。

入口: `AGENTS.md` · `docs/ai-onboarding.md` · `docs/workflow.md`

## コア（調査サイクル）

| ツール | 用途 | 主な出力 |
|---|---|---|
| `extract_vbp.py` | VBP 切り出し（`Reference=` スキップ） | `working/extracts/<stem>/` + `_extract_report.json` |
| `vb6_inventory.py` | 構成事実のみ | `working/reports/<stem>_inventory.{json,md,html}` |
| `verify_inventory.py` | End 文カウント照合 | stdout JSON + `count mismatches: none` |
| `verify_report_names.py` | inventory 名集合 ↔ レポート言及照合 | stdout JSON + `name mismatches: none` |
| `frm_deep_read.py` | .frm 深読み（単体解析。`ancestor_hidden` 付与） | `*_deep_read.md` + `working/skeletons/*-skeleton.json` |
| `frm_deep_read_all.py` | 抽出内の全 .frm を一括 deep_read | 同上（キーは VB_Name 小文字 / `deep_read_name_map`） |
| `runtime_layout.py` | コード部の実行時座標 | `runtime_layout.md` / `runtime-layout.json` |
| `frm_lines.py` | CP932 ソースの行番号つき表示 | stdout |
| `scan_control_chars.py` | PS バッククォート由来の制御文字検出 | stdout（hits=0 で exit 0） |
| `make_fixture.py` | スモーク用ミニ VBP（CP932） | `source/mini_vbp/` |
| `kit_smoke.py` | キット自己点検（fixture パイプライン + unittest） | stdout（失敗時非ゼロ） |

## 共有ライブラリ

| モジュール | 用途 |
|---|---|
| `lib/config.py` | `archaeology.config.json` 読込、保護 dir、デコード |

## 使い方（代表）

```powershell
python tools/make_fixture.py
python tools/extract_vbp.py "source\mini_vbp\mini_vbp.vbp"
python tools/vb6_inventory.py working\extracts\mini_vbp
python tools/verify_inventory.py
python tools/verify_report_names.py --inventory working\reports\mini_vbp_inventory.json
python tools/frm_deep_read.py Form1.frm --extract working\extracts\mini_vbp
python tools/runtime_layout.py --extract working\extracts\mini_vbp
python tools/frm_lines.py working\extracts\mini_vbp\Form1.frm 1-20
python tools/scan_control_chars.py
```

検証の順: まず `verify_inventory.py`（End 数）→ 次に `verify_report_names.py`（名前集合）。  
名前照合の足りない抽出は本ツールを改定する（`working/_verify_*.py` を増やさない）。

## 改定ルール

1. 足りない抽出・誤検知は本ディレクトリのツールを直す
2. 直したら影響レポート / skeleton を再生成
3. 本 README の表を更新
4. アプリ固有ロジックは消費者リポの `tools/` へ（キットを汚さない）

## 設定メモ

- `archaeology.config.json` の `geometry_hints` で親フォーム相対式を数値化できる（任意）
- `layout_sub_scores` — `runtime_layout.py` の開経路優先 Sub → int スコア（キーは小文字）
  - キット既定: `form_load` / `mdiform_load` のみ（builtin とマージ）
  - 名前非依存: 未登録の `*_click` は form_show で小さな加点、codeMoves では下限スコア
  - **アプリ固有の開経路 Sub は消費者 config に書く**（キットへ還元しない）
  - 使用したスコアは `runtime_layout.json` / `runtime-layout.json` / MD に出力
- `deep_read_name_map` で `frm_deep_read_all.py` の出力キー特例を指定できる（任意）
- `skeletons_dir` 既定は `working/skeletons`（消費者は web lib 等へ変更可）
- `--extract` 未指定時は `working/extracts/` 下一意ならそれを使う（複数ならエラー）

## inventory の性能・拡張オプション

- `--jobs N` — ファイルを N 並列で解析（既定 1＝逐次）。大規模ツリーで有効。VBP 記載順は維持。
- `--no-cache` — 内容ハッシュキャッシュ（`working/.cache/`）を無効化。
  - 既定はキャッシュ有効。SHA-256（パーサ版＋拡張子＋バイト列）キーで未変更ファイルの再解析をskip（`.frm`/`.bas` は別エントリ）。
  - パーサ挙動を変えたら `vb6_inventory.PARSER_VERSION` を上げて自動無効化する。
- `--skip-parent-common` — VBP パスが親ディレクトリを2段以上辿るもの（`..\..\` 系）をスキップ。共有ライブラリ参照を棚卸しから外す任意オプション（既定オフ）。
- 棚卸し対象:
  - VBP: **Form / Module / Class**、`Object=`（OCX 等）、Version / Command32 / HelpFile などメタ
  - プロシージャ: Sub/Function/Property + **引数・戻り値**、Declare、モジュールレベル Const/Enum/Type/Event
- パス欠落の `Form=` / `Module=` / `Class=` は一覧に入れず `warnings` に出す（JSON / MD / HTML / CLI サマリ）。
- HTML レポートは検索ボックス（ファイル名 / VB_Name / プロシージャ / 宣言名）と全開閉ボタン付き。
- VBP キーの正: `docs/reference/vbp-keys.md`。

## 共有ライブラリ（追加）

| モジュール | 用途 |
|---|---|
| `lib/vbparse.py` | `_` 行連結の畳み込み（物理行番号を保持する logical line） |
| `lib/cache.py` | 内容アドレス指定の解析キャッシュ（`working/.cache/`） |

## テスト

キット全体の自己点検（推奨）:

```powershell
python tools/kit_smoke.py
```

unittest のみ（リポ根で。`tools.*` import 用に `PYTHONPATH` を根へ）:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tools -p "test_*.py" -v
```

- `test_runtime_layout.py` — Show 経路の文脈解決・Sub 境界で `recent_shows` クリア（合成データ）
- `test_frm_deep_read.py` — `ancestor_hidden`（死んだ非表示コンテナ配下）
- `test_verify_report_names.py` — inventory 名集合照合（偽 Sub で fail / 既知名で pass）
- `test_vbparse.py` — 行連結畳み込みと物理行番号の保持
- `test_inventory.py` — proc/Declare/Property シグネチャ、Const/Enum/Type/Event、Class=/Object=/meta、`warnings`、`--skip-parent-common`、End 数不変条件
- `test_cache.py` — 内容ハッシュキー・保存/読込
- `test_build_report.py` — 並列＝逐次の一致・VBP 順維持・HTML 検索 TOC

いずれも特定顧客アプリの正本は不要（合成データ／一時ディレクトリ）。

## 由来と非対象

`VB6_source` で培った汎用部を移植。  
伝票 DAT・特定 Form・Next.js 配線などアプリ固有ツールは含まない。  
利用条件はリポ直下 `LICENSE`（許諾前提）。
