# Flow master（キット）

**目標: VB6 資産を壊さず段階理解し、再現可能な調査成果を残す。**

再実装（Next.js 等）は消費者リポの任意レーン。ここでは調査レーンを正とする。

## 正典の層（矛盾時の優先）

| 優先 | 層 | 役割 | 正 |
|---|---|---|---|
| 1 | ソース | VB6 抽出コピー | `working/extracts/<stem>/`（正本は `source/` 等） |
| 2 | 仕様・範囲 | フェーズ・不変条件 | **本ファイル** + 消費者の plans |
| 3 | セッション事実（消費者アプリ） | 現状・次手 | `docs/ai-dev-context.md` |
| 4 | 入口 | パス・索引 | `AGENTS.md` |
| 5 | 方法論 | 事実/推定・検証 | `.cursor/rules/vb6-analysis.mdc` |

キット自体の保守メモは `docs/kit-dev-context.md`（層3ではない）。

## 調査レーン（標準）

1. 環境・キット自己点検（`/kit-smoke`）
2. 正本配置（`source/`）
3. VBP 抽出
4. inventory + verify
5. Startup / 主要 Form の deep-read
6. runtime_layout
7. comprehension ticks（層 A→E）
8. ギャップ再監査（完了不信）

各アプリの進捗チェックリストは消費者の `docs/ai-dev-context.md` に書く（本ファイルへ長く複製しない）。

## 不変条件

- 保護ディレクトリ（`archaeology.config.json`）は読取専用
- 抽出は `working/extracts/` のみ
- 解析成果は `working/reports/` / `docs/`
- 使い捨て解析の増殖禁止（`tools/` 改定）
- 推定に証拠必須

## 入口

- AI: `AGENTS.md` → `docs/ai-onboarding.md`
- ツール: `tools/README.md`
- 採用: `docs/adopting-in-a-project.md`
