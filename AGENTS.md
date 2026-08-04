# AGENTS.md — vb6-archaeology

**VB6 を壊さず理解するオペレーティングシステム（キット）。** 正本ツリーへの書込を禁止したまま、
VBP を切り出し・棚卸し・深読み・証拠つき理解まで進める。

## Setup

- Python **3.10+**（標準ライブラリのみ。pip 依存を増やさない）
- 単一入口: `python -m tools <command>`（`python tools/<name>.py` も動く）
- コマンド一覧: `python -m tools --help`

## Commands

| 作業 | コマンド | Cursor command |
|---|---|---|
| VBP 切り出し | `python -m tools extract "<vbp>"` | `/vb6-extract` |
| 構成レポート | `python -m tools inventory <extract_dir>` | `/vb6-inventory` |
| End 数照合 | `python -m tools verify <inventory.json>` | `/vb6-verify-reports` |
| 名前集合照合 | `python -m tools verify-names --inventory <inventory.json>` | `/vb6-verify-reports` |
| Form 深読み | `python -m tools deep-read <File>.frm --extract <dir>` | `/frm-deep-read` |
| 実行時座標 | `python -m tools layout --extract <dir>` | `/runtime-layout` |
| 理解 tick | `python -m tools comprehend --add-tick <Proc>` | `/vb6-comprehend` |
| 報告書 | （skill `vb6-accurate-reports`） | `/vb6-report` |
| レポート閲覧 | `python -m tools serve` | `/serve-reports` |
| 設定検証 | `python -m tools config-check` | — |
| 自己点検 | `python -m tools smoke` | `/kit-smoke` |

## Testing

キットを変更したら次を緑にする（CI も同じ入口）:

```powershell
python -m tools smoke
```

フィクスチャパイプライン（config-check → extract → inventory → verify → deep-read →
layout → comprehend → scan-chars）＋ `tools/` 配下の unittest。詳細は `CONTRIBUTING.md` · `tools/README.md`。

## DO NOT

- `protected_source_dirs`（キット既定 `source/`）へ**書込・移動・改名・削除しない**。hooks が拒否する
  - 例外は `python -m tools fixture`（= `tools/make_fixture.py`）のみ
- **Cursor `Read` で化けた日本語を根拠にしない**。VB6 テキストは CP932。内容判断は `python -m tools lines` か Python 経由
- 推定（役割・呼び出し・業務意味）を**証拠なしで書かない**。正規表現一括の callgraph は作らない
- inventory に無いファイル名・プロシージャ名をレポートに書かない（`comprehend --add-tick` は拒否する）
- 使い捨て `working/_*.py` を増やさない。足りなければ **`tools/` を改定して再実行**する
- 「100%」「done」はチェックリスト達成のみ。アプリ全体理解と混同しない
- レポート HTML を `file://` で開かない（`python -m tools serve`）

## セッション開始時の Read 順

1. 本ファイル（`AGENTS.md`）
2. [`docs/ai-onboarding.md`](docs/ai-onboarding.md)（必読・詳細）
3. 対象アプリがあるなら消費者の `docs/ai-dev-context.md`
4. キット自体を直すときだけ [`docs/kit-dev-context.md`](docs/kit-dev-context.md)

## 正典の層（矛盾時）

| 優先 | 役割 | 正 |
|---|---|---|
| 1 | VB6 ソース（抽出コピー） | `working/extracts/<stem>/`（正本は `source/` 等・読取専用） |
| 2 | フロー・範囲 | `docs/flow/_master.md` |
| 3 | セッション事実（消費者アプリ） | `docs/ai-dev-context.md`（テンプレ: `docs/templates/`） |
| 4 | 入口（本ファイル） | パス・規約・索引。長い現状は ai-dev-context へ |
| 5 | 方法論 | `.cursor/rules/vb6-analysis.mdc` · `docs/methodology.md` |

キット保守メモは層3ではない → `docs/kit-dev-context.md`。

## ディレクトリ早見

| パス | 役割 |
|---|---|
| `source/` | 読取専用の VB6 正本（キット既定。別名は config で指定） |
| `working/extracts/` | VBP 切り出しコピー（分析用） |
| `working/reports/` | inventory / deep_read / comprehension 等 |
| `working/skeletons/` | Form skeleton JSON（再実装に渡す中間成果） |
| `tools/` | 再利用解析 + CLI（`python -m tools`） |
| `docs/` | 方法論・採用手順・テンプレ |
| `schema/` | `archaeology.config.json` の JSON Schema |
| `.cursor/` | rules / skills / commands / hooks |
| `archaeology.config.json` | 保護ディレクトリ名・出力先・`geometry_hints` |

## 標準サイクル

**検証 → 理解 →（任意）実装**

1. `/vb6-extract` — 正本から `working/extracts/<stem>/`
2. `/vb6-inventory` — 事実のみの構成正
3. `/frm-deep-read` · `/runtime-layout` — Form 深読み・実行時座標
4. `/vb6-comprehend` — 証拠つき tick 理解
5. `/vb6-report` — 報告書の作成・訂正
6. （任意）消費者リポで再実装。確定事実のみ反映

詳細: `docs/workflow.md` · ツール索引: `tools/README.md`

## 由来・条件

方法論とコアツールは `VB6_source`（作業指示書再実装リポ）で培ったものを汎用化。
アプリ固有ツール（伝票 DAT・Form7 条件等）は本キットに含めない。
利用・複製は [LICENSE](LICENSE)（source-available・許諾前提）に従う。
キット保守・公開方針のメモは [`docs/kit-dev-context.md`](docs/kit-dev-context.md)。
