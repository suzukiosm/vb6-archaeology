# AGENTS.md — 〈アプリ名〉

## 目的

〈VB6 資産〉を改変せず調査し、必要なら再実装する。

**セッション開始時の Read 順:** `AGENTS.md`（本ファイル）→ `docs/ai-onboarding.md` → [`docs/ai-dev-context.md`](docs/ai-dev-context.md)

調査 OS（方法論・汎用 tools）は `vb6-archaeology` キットに従う（利用はキット LICENSE＝許諾前提）。

## 正典の層（文書が食い違うときの優先）

| 優先 | 目的 | 信頼できる情報源 |
|---|---|---|
| 1 | VB6 コード事実 | `working/extracts/<stem>/` |
| 2 | 調査フロー・範囲 | `docs/flow/_master.md` · plans |
| 3 | 消費者アプリのセッション事実 | `docs/ai-dev-context.md` |
| 4 | 入口・規約・索引 | 本ファイル |
| 5 | 方法論 | `.cursor/rules/vb6-analysis.mdc` |

## Setup / Testing

- Python 3.10+（標準ライブラリのみ）
- ツール入口: `python -m tools <command>`（一覧は `python -m tools --help`）
- 設定検証: `python -m tools config-check`
- 自己点検: `python -m tools smoke`

## 不変条件

- 正本ディレクトリは読取専用（hooks）
- サイクル: 検証 → 理解 → 実装
- 事実と推定を分離。証拠なき推定は書かない
- inventory に無いファイル名・プロシージャ名をレポートに書かない

## ワークフロー索引

| 作業 | command |
|---|---|
| 抽出 | `/vb6-extract` |
| 構成 | `/vb6-inventory` |
| 深読み | `/frm-deep-read` |
| 実行時座標 | `/runtime-layout` |
| 理解 | `/vb6-comprehend` |
| 報告書 | `/vb6-report` |
| 照合 | `/vb6-verify-reports` |
