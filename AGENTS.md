# AGENTS.md — vb6-archaeology

## このリポは何か

**VB6 を壊さず理解するオペレーティングシステム（キット）**。

- 正本ツリーへの書込を禁止したまま、VBP を切り出し・棚卸し・深読み・証拠つき理解まで進める
- 個別アプリの業務知識はここに載せない（消費者リポの `docs/ai-dev-context.md` 側）
- 再実装（Next.js 等）は任意レーン。本キットの必須ゴールは **正確な理解と再現可能な調査**
- 利用・複製は [LICENSE](LICENSE)（source-available・許諾前提）に従う

**セッション開始時の Read 順:**

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
| `tools/` | 再利用解析（使い捨て `working/_*.py` を増やさない） |
| `docs/` | 方法論・採用手順・テンプレ |
| `.cursor/` | rules / skills / commands / hooks |
| `archaeology.config.json` | 保護ディレクトリ名・出力先・`geometry_hints` |

## 技術前提

- VB6 テキストは多くの場合 **CP932**。内容判断は Python（`tools/lib/config.py`）経由
- Cursor `Read` は日本語ソースを化かすことがある → 化けた文字列を根拠にしない
- レポート HTML は `file://` 不可 → ローカル HTTP（既定 8765）

## 標準サイクル

**検証 → 理解 →（任意）実装**

1. `/vb6-extract` — 正本から `working/extracts/<stem>/`
2. `/vb6-inventory` — 事実のみの構成正
3. `/frm-deep-read` · `runtime_layout.py` — Form 深読み・実行時座標
4. `/vb6-comprehend` — 証拠つき tick 理解
5. `/vb6-report` — 報告書の作成・訂正
6. （任意）消費者リポで再実装。確定事実のみ反映

詳細: `docs/workflow.md` · ツール索引: `tools/README.md`

## 不変条件

- `protected_source_dirs`（キット既定 `source/`）へは **書込・移動・改名・削除禁止**（hooks 強制）
- 例外: `python tools/make_fixture.py` のみフィクスチャ再生成を許可（shell allowlist）
- 推定（役割・呼び出し・業務意味）は **証拠必須**。正規表現一括の callgraph は作らない
- 「100%」「done」はチェックリスト達成のみ。アプリ全体理解と混同しない
- ツールが足りなければ **`tools/` を改定して再実行**（ワンショット増殖禁止）

## Commands（定型入口）

| 作業 | command |
|---|---|
| VBP 切り出し | `/vb6-extract` |
| 構成レポート | `/vb6-inventory` |
| Form 深読み | `/frm-deep-read` |
| 理解 tick | `/vb6-comprehend` |
| 報告書 | `/vb6-report` |
| inventory 照合 | `/vb6-verify-reports` |
| レポート閲覧 | `/serve-reports` |
| キット自己点検 | `/kit-smoke` |

## 由来

方法論とコアツールは `VB6_source`（作業指示書再実装リポ）で培ったものを汎用化。  
アプリ固有ツール（伝票 DAT・Form7 条件等）は本キットに含めない。
