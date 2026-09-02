# tools

**[English](#english)** · **[日本語](#japanese)**

Reusable analysis utilities. Do not add one-off `working/_*.py` — extend this directory.
VB6 text is **CP932**. Do not write into protected source dirs.

Entry: `AGENTS.md` · `docs/ai-onboarding.md` · `docs/workflow.md`

## CLI

```powershell
python -m tools --help          # command list (canonical summaries)
python -m tools <command> --help
python -m tools --version
python -m tools demo            # extract → inventory → excerpt → serve
```

`tools/cli.py` `COMMANDS` is the summary source of truth (`test_cli.py` checks every
`main` and `--help`). This table lists names only so it cannot drift from help text.
`python tools/<name>.py` still works.

## Commands

| command | module |
|---|---|
| `demo` | `demo.py` |
| `extract` | `extract_vbp.py` |
| `inventory` | `vb6_inventory.py` |
| `verify` | `verify_inventory.py` |
| `verify-names` | `verify_report_names.py` |
| `verify-show` | `verify_show.py` |
| `deep-read` | `frm_deep_read.py` |
| `deep-read-all` | `frm_deep_read_all.py` |
| `layout` | `runtime_layout.py` |
| `comprehend` | `comprehension_scaffold.py` |
| `excerpt` | `reimpl_excerpt.py` |
| `io-catalog` | `io_catalog.py` |
| `status` | `status.py` |
| `ideas` | `ideas.py` |
| `lines` | `frm_lines.py` |
| `scan-chars` | `scan_control_chars.py` |
| `config-check` | `lib/config_schema.py` |
| `serve` | `serve_reports.py` |
| `fixture` | `make_fixture.py` |
| `smoke` | `kit_smoke.py` |

`demo` does **not** add ticks and is **not** `smoke` / `serve --live-get`.
`serve` prints the URL it actually bound; if `reports_http_port` is taken it falls back.

When you add a command, update `cli.py` `COMMANDS` and the table above in the same change.

---

## English

### Shared libraries

| module | role |
|---|---|
| `lib/config.py` | `archaeology.config.json`, protected dirs, decode |
| `lib/config_schema.py` | JSON Schema validation (stdlib only) |
| `lib/console.py` | UTF-8 stdout/stderr so Japanese captions survive a non-CP932 console |
| `lib/vbparse.py` | `_` continuations and colon split (physical line numbers kept) |
| `lib/cache.py` | content-addressed parse cache (`working/.cache/`) |
| `lib/report_html.py` | light-theme CSS for report HTML (no dark-mode inversion) |

### Typical usage

```powershell
python -m tools demo
# or the long cycle:
python -m tools config-check
python -m tools fixture
python -m tools extract "source\mini_vbp\mini_vbp.vbp"
python -m tools inventory working\extracts\mini_vbp
python -m tools verify
python -m tools excerpt
python -m tools serve
```

Open the URL `serve` / `demo` prints. Do not use `file://`.

Verify order: `verify` (End counts) → `verify-names` (name set) → `verify-show` (show_style; range gaps are warnings).
If extraction is wrong, fix the tool here — do not add `working/_verify_*.py`.

### Change rules

1. Missing extraction / false positives: fix tools in this directory
2. After a parser change, regenerate affected reports / skeletons
3. Update `COMMANDS` and the table above
4. App-specific logic belongs in the consumer repo `tools/`

### Config notes

Canon: `schema/archaeology.config.schema.json` (`python -m tools config-check`).

- `protected_source_dirs` — in-repo read-only names. **Empty is valid** (originals live outside the repo)
- `protected_path_markers` — path segments that are read-only wherever they appear
- `default_extract` — extract name when `--extract` is omitted
- `reports_http_port` — default 8765; `serve` falls back and prints the real URL
- `mdi_chrome` / `layout_sub_scores` / `optional_assign_markers` — kit defaults are empty or generic; app names stay in the consumer config
- `--extract` with no flag uses the sole folder under `working/extracts/` (error if several)

Inventory extras: `--jobs N`, `--no-cache`, `--skip-parent-common`. Bump `vb6_inventory.PARSER_VERSION` when parse behaviour changes.
Comprehension: ticks insert before `<!-- TICKS:END -->`; `--add-tick` refuses names absent from the inventory; `--unticked` / `--suggest` never write.

### Tests

```powershell
python -m tools smoke
```

Unittest only (repo root on `PYTHONPATH`):

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tools -p "test_*.py" -v
```

`test_cli.py` also checks that every `COMMANDS` name appears as `` `name` `` in this file.
`test_demo.py` — `--no-serve` pipeline, no auto-tick, next-command on failure.
`test_serve_reports.py` — landing, `--live-get`, occupied-port fallback.

No customer originals required (synthetic / temp dirs).

### Origin

Generic parts from `VB6_source`. App-specific tools are not in this kit.
Terms: repo-root `LICENSE` (grant required).

---

## 日本語

使い捨て `working/_*.py` を増やさず、ここに置いて改定する。
VB6 テキストは **CP932**（`lib/config.py` / `archaeology.config.json`）。
保護ディレクトリへは書込しない。

コマンド要約の正は `python -m tools --help`（上の表は名前とモジュールだけ）。

### 共有ライブラリ

| モジュール | 用途 |
|---|---|
| `lib/config.py` | `archaeology.config.json` 読込、保護 dir、デコード |
| `lib/config_schema.py` | `schema/archaeology.config.schema.json` による設定検証（stdlib のみ） |
| `lib/console.py` | stdout/stderr を UTF-8 化（各 `main()` 冒頭で呼ぶ。日本語 Caption を非 CP932 コンソールへ出せるように） |
| `lib/vbparse.py` | `_` 行連結とコロン文分割（物理行番号を保持） |
| `lib/cache.py` | 内容アドレス指定の解析キャッシュ（`working/.cache/`） |
| `lib/report_html.py` | レポート HTML のライトテーマ固定（ダークモードで表が空に見えないように） |

### 使い方（代表）

```powershell
python -m tools demo
# 調査サイクルを手で踏むとき:
python -m tools config-check
python -m tools fixture
python -m tools extract "source\mini_vbp\mini_vbp.vbp"
python -m tools inventory working\extracts\mini_vbp
python -m tools verify
python -m tools verify-names --inventory working\reports\mini_vbp_inventory.json
python -m tools verify-show --inventory working\reports\mini_vbp_inventory.json
python -m tools deep-read Form1.frm --extract working\extracts\mini_vbp
python -m tools deep-read Widget.cls --extract working\extracts\mini_vbp
python -m tools ideas
python -m tools layout --extract working\extracts\mini_vbp
python -m tools comprehend --add-tick Command1_Click@Form1.frm --layer C
python -m tools comprehend --unticked
python -m tools comprehend --suggest
python -m tools io-catalog --extract working\extracts\mini_vbp
python -m tools lines working\extracts\mini_vbp\Form1.frm 1-20
python -m tools scan-chars
python -m tools status
python -m tools excerpt
python -m tools serve
```

`demo` は tick しない。`serve --live-get`（smoke 用の一時ポート GET）とは別。
`serve` / `demo` が印刷した URL が正（8765 が占有なら空きポートへ落ちる）。`file://` は使わない。

`verify` は照合結果を `working/reports/<stem>_verify.json` に残す（`status` が読む。無ければ `not persisted`）。

検証の順: まず `verify`（End 数）→ `verify-names`（名前集合）→ `verify-show`（show_style。範囲差は警告）。
名前照合の足りない抽出は本ツールを改定する（`working/_verify_*.py` を増やさない）。

### 改定ルール

1. 足りない抽出・誤検知は本ディレクトリのツールを直す
2. 直したら影響レポート / skeleton を再生成
3. 本 README の表と `cli.py` の `COMMANDS` を更新
4. アプリ固有ロジックは消費者リポの `tools/` へ（キットを汚さない）

### 設定メモ

設定の正は `schema/archaeology.config.schema.json`（`python -m tools config-check` で検証）。

- `protected_source_dirs` — リポ内の読取専用ディレクトリ名。**空も正当**（正本がリポ外の構成）
- `protected_path_markers` — どこに現れても読取専用にするパス断片（共有ドライブ上の正本など）。hooks と `extract` が参照する
- `default_extract` — `--extract` 省略時に使う extract 名（複数 extract を持つ消費者向け）
- `scan_roots` / `scan_skip_dirs` — `scan-chars` の走査対象。保護ディレクトリとマーカーは自動で除外される
- `mdi_defaults` — 消費者専用。設定時のみ `runtime-layout.json` に `mdiDefaults` を出す
- `mdi_chrome` — 消費者専用。`shell_forms`（MDI シェル VB_Name）と `control_names`（chrome コントロール）。**キット既定は空**。layout の `mdi_chrome` 分類・Bare 正規化・Picture1.Height 帰属に使う。よくある例: `["MDIForm1"]` + `["Picture1","FG1","fg2"]`
- `geometry_hints` で親フォーム相対式を数値化できる（任意）
- `layout_sub_scores` — `layout` の開経路優先 Sub → int スコア（キーは小文字）
  - キット既定: `form_load` / `mdiform_load` のみ（builtin とマージ）
  - 名前非依存: 未登録の `*_click` は form_show で小さな加点、codeMoves では下限スコア
  - **アプリ固有の開経路 Sub は消費者 config に書く**（キットへ還元しない）
  - 使用したスコアは `runtime_layout.json` / `runtime-layout.json` / MD に出力
- `deep_read_name_map` で `deep-read` / `deep-read-all` の出力キー特例を指定できる（任意。既定は VB_Name 小文字）
- `picture1_height_by_sub` — `layout` が `near_show` 空のとき Picture1.Height の帰属 Form を決める（消費者のみ）
- `verify_report_allow_files` — `verify-names` が inventory 外ファイル名を許可するリスト（消費者のみ）
- `optional_assign_markers` — 消費者固有の代入マーカー（例: `PARA`）。**キット既定は空**。deep-read の任意スキャンに使う（必須節ではない）
- `skeletons_dir` 既定は `working/skeletons`（消費者は web lib 等へ変更可）
- `reports_http_port` 既定は 8765（占有時は `serve` が空きポートへフォールバックし、印刷した URL が正。`--port` でも上書き可）
- `--extract` 未指定時は `working/extracts/` 下一意ならそれを使う（複数ならエラー）

### inventory の性能・拡張オプション

- `--jobs N` — ファイルを N 並列で解析（既定 1＝逐次）。大規模ツリーで有効。VBP 記載順は維持。
- `--no-cache` — 内容ハッシュキャッシュ（`working/.cache/`）を無効化。
  - 既定はキャッシュ有効。SHA-256（パーサ版＋拡張子＋バイト列）キーで未変更ファイルの再解析をskip（`.frm`/`.bas` は別エントリ）。
  - パーサ挙動を変えたら `vb6_inventory.PARSER_VERSION` を上げて自動無効化する。
- `--skip-parent-common` — VBP パスが親ディレクトリを2段以上辿るもの（`..\..\` 系）をスキップ。共有ライブラリ参照を棚卸しから外す任意オプション（既定オフ）。
- 棚卸し対象:
  - VBP: **Form / Module / Class / UserControl / PropertyPage / UserDocument / Designer**、`RelatedDoc=` / `ResFile32=`（一覧のみ）、`Object=`（OCX 等）、Version / Command32 / HelpFile / Type / CondComp / CompatibleMode / CompilationType / CompatibleEXE32 / AutoIncrementVer などメタ（生文字列）
  - プロシージャ: Sub/Function/Property + **引数・戻り値**、Declare、モジュールレベル Const/Enum/Type/Event（`iter_statements`。`End` 照合は verify と同じ文単位。`Const A = 1, B = 2` は複数件）
  - 表面: Implements / WithEvents / Instancing / Attribute も `iter_statements`
- パス欠落の `Form=` / `Module=` / `Class=` は一覧に入れず `warnings` に出す（JSON / MD / HTML / CLI サマリ）。
- HTML レポートは検索ボックス（ファイル名 / VB_Name / プロシージャ / 宣言名）と全開閉ボタン付き。
- Form の `show_calls`（`Foo.Show` / `Me.Show` / 単独 `Show`）を転置して `show_inbound` / `show_unresolved` を出す（新しい呼び出しは推定しない。`Me` / 空 target は unresolved）。
- Form の `lifetime_calls`（`Load` / `Unload` 文面。転置しない）。
- VBP キーの正: `docs/reference/vbp-keys.md`。

### comprehension scaffold の契約

- 骨格は `<!-- TICKS -->` … `<!-- TICKS:END -->` を持ち、tick は末尾マーカーの直前に挿入される
- **既存の記述は上書きしない**（`--force` を明示したときだけ骨格を作り直す）
- `--add-tick <Proc>[@<File>]` は inventory の名前集合に無ければ失敗する。同名が複数なら `@<File>` を要求する
- 達成率はレポート内の `data-status` から実行時に集計される（数字を手書きしない）

### テスト

キット全体の自己点検（推奨）:

```powershell
python -m tools smoke
```

unittest のみ（リポ根で。`tools.*` import 用に `PYTHONPATH` を根へ）:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tools -p "test_*.py" -v
```

- `test_cli.py` — 全コマンドの `main` 実在・`--help`・未知コマンドの終了コード・本 README に `` `command` `` があること
- `test_config_schema.py` — 同梱 config の妥当性、型不一致・未知キー・範囲外ポートの検出
- `test_config.py` — 正本がリポ外の構成（`protected_source_dirs: []` + マーカー）の解決
- `test_comprehension_scaffold.py` — 骨格の冪等性、人手記述の保全、inventory 外の名前を拒否
- `test_hooks.py` — 保護 hooks の deny / ask / allowlist / 偽陽性（`resources` を `source` と誤認しない）
- `test_console.py` — cp1252 コンソール（英語 Windows 相当）でも日本語 Caption を出力して落ちない
- `test_runtime_layout.py` — Show 経路の文脈解決・Sub 境界で `recent_shows` クリア · `.cls` 走査（合成データ）
- `test_frm_deep_read.py` — `ancestor_hidden`（死んだ非表示コンテナ配下）· `menu_tree`（デザイナ親子）· `.cls` 表面 · `unobserved` / フォント除外 / 任意代入マーカー
- `test_ideas.py` — `kit-improvement-ideas.md` の open/adopted 集計
- `test_show_style.py` — show_style ヒューリスティック · Show 転置 · excerpt 配線
- `test_verify_report_names.py` — inventory 名集合照合（偽 Sub で fail / 既知名で pass）
- `test_verify_show.py` — inventory vs deep-read show_style（self/call 食い違いは hard、inventory_only は警告）
- `test_vbparse.py` — 行連結畳み込み・コロン分割・ラベル kind
- `test_inventory.py` — proc/Declare/Property シグネチャ、Const/Enum/Type/Event、Class=/Object=/meta（Type / CondComp / CompatibleMode 等）、`warnings`、`--skip-parent-common`、End 数不変条件、表面 VB_PredeclaredId / VB_UserMemId
- `test_cache.py` — 内容ハッシュキー・保存/読込
- `test_build_report.py` — 並列＝逐次の一致・VBP 順維持・HTML 検索 TOC
- `test_status.py` — 成果物の有無・件数、複数 extract、`default_extract`、verify 永続化
- `test_io_catalog.py` — I/O 5 種の分類、コメント/`GetTickCount`/`Name =` 除外、GoTo 飛び越え突合
- `test_serve_reports.py` — ランディング分類 + `--live-get`（`/` と `/excerpt` が 200）+ ポート占有時のフォールバック
- `test_demo.py` — `--no-serve` で inventory/excerpt を書き、tick しない。失敗時は `next:` を出す
- `test_extract_vbp.py` — 同 stem 同伴（`.frx` / `.ctx` 等）。中身は解析しない

いずれも特定顧客アプリの正本は不要（合成データ／一時ディレクトリ）。

### 由来と非対象

`VB6_source` で培った汎用部を移植。
伝票 DAT・特定 Form・Next.js 配線などアプリ固有ツールは含まない。
利用条件はリポ直下 `LICENSE`（許諾前提）。
