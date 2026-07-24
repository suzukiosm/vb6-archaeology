# AI 開発コンテキスト — 〈アプリ名〉

セッション開始時に Read。推測で埋めない。長い現状はここに書き、`AGENTS.md` へ複製しない。

## 1. ゴール（一本）

**〈対象 .vbp〉を段階的に理解する。**  
（再実装する場合）→ `working/web/` 等へ確定事実のみ反映。

- Startup: 〈Form / VB_Name〉
- 対象範囲: 〈VBP 全体 / 一部〉

## 2. やり方

サイクル: **検証 → 理解 → 実装**（ツール再利用・改定込み）

## 3. 触ってよい／いけない

| 領域 | 規則 |
|---|---|
| 正本（例: `source/`。別名は config） | 読取専用 |
| `working/extracts/` | 切り出しコピー |
| `working/reports/` · `docs/` | 調査成果 |
| `tools/` | 再利用解析の正 |
| 再実装ディレクトリ | 確定事実のみ |

## 4. 入口

| 用途 | パス |
|---|---|
| エージェント入口 | `AGENTS.md` |
| フロー | `docs/flow/_master.md` |
| 方法論 | `.cursor/rules/vb6-analysis.mdc` |
| 構成事実 | `working/reports/<stem>_inventory.*` |
| 理解 | `working/reports/<stem>_comprehension.html` |

## 5. ツール

`tools/README.md` を正とする。

## 6. 現状（事実）

- 抽出: 〈済 / 未〉
- inventory: 〈済 / 未〉
- deep-read: 〈Form 一覧〉
- 到達不能と分かった Form: 〈証拠パス〉

## 7. 主経路（証拠つき）

- …

## 8. 次手

1. …
2. …
