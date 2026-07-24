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
| `frm_deep_read.py` | .frm 深読み | `*_deep_read.md` + `working/skeletons/*-skeleton.json` |
| `runtime_layout.py` | コード部の実行時座標 | `runtime_layout.md` / `runtime-layout.json` |
| `make_fixture.py` | スモーク用ミニ VBP（CP932） | `source/mini_vbp/` |

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
python tools/frm_deep_read.py Form1.frm --extract working\extracts\mini_vbp
python tools/runtime_layout.py --extract working\extracts\mini_vbp
```

## 改定ルール

1. 足りない抽出・誤検知は本ディレクトリのツールを直す
2. 直したら影響レポート / skeleton を再生成
3. 本 README の表を更新
4. アプリ固有ロジックは消費者リポの `tools/` へ（キットを汚さない）

## 設定メモ

- `archaeology.config.json` の `geometry_hints` で親フォーム相対式を数値化できる（任意）
- `skeletons_dir` 既定は `working/skeletons`（消費者は web lib 等へ変更可）

## inventory の性能・拡張オプション

- `--jobs N` — ファイルを N 並列で解析（既定 1＝逐次）。大規模ツリーで有効。VBP 記載順は維持。
- `--no-cache` — 内容ハッシュキャッシュ（`working/.cache/`）を無効化。
  - 既定はキャッシュ有効。SHA-256（パーサ版＋バイト列）キーで未変更ファイルの再解析をskip。
  - パーサ挙動を変えたら `vb6_inventory.PARSER_VERSION` を上げて自動無効化する。
- 棚卸し対象: Sub/Function/Property/Declare に加え、モジュールレベルの **Const / Enum / Type / Event**（プロシージャ内ローカルは除外）。
- HTML レポートは検索ボックス（ファイル名 / VB_Name / プロシージャ / 宣言名）と全開閉ボタン付き。

## 共有ライブラリ（追加）

| モジュール | 用途 |
|---|---|
| `lib/vbparse.py` | `_` 行連結の畳み込み（物理行番号を保持する logical line） |
| `lib/cache.py` | 内容アドレス指定の解析キャッシュ（`working/.cache/`） |

## テスト

```powershell
python -m unittest discover -s tools -p "test_*.py" -v
```

- `test_runtime_layout.py` — Show 経路の文脈解決（合成データ）
- `test_vbparse.py` — 行連結畳み込みと物理行番号の保持
- `test_inventory.py` — proc/Declare 抽出、Const/Enum/Type/Event、End 数不変条件
- `test_cache.py` — 内容ハッシュキー・保存/読込
- `test_build_report.py` — 並列＝逐次の一致・VBP 順維持

いずれも特定顧客アプリの正本は不要（合成データ／一時ディレクトリ）。

## 由来と非対象

`VB6_source` で培った汎用部を移植。  
伝票 DAT・特定 Form・Next.js 配線などアプリ固有ツールは含まない。  
利用条件はリポ直下 `LICENSE`（許諾前提）。
