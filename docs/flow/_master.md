# Flow master（キット）

**目標: VB6 資産を壊さず段階理解し、再現可能な調査成果を残す。**

再実装（Next.js 等）は消費者リポの任意レーン。ここでは調査レーンを正とする。

## 正典の層（文書が食い違うときの優先）

矛盾したら上の行を採用する。列「信頼できる情報源」がその層の正本パス。

| 優先 | 目的 | 信頼できる情報源 | 補足 |
|---|---|---|---|
| 1 | VB6 コード事実 | `working/extracts/<stem>/` | 正本は `source/` 等・読取専用。分析は抽出コピーを見る |
| 2 | 調査フロー・範囲 | **本ファイル** + 消費者の plans | 工程順序・不変条件 |
| 3 | 消費者アプリのセッション事実 | `docs/ai-dev-context.md` | 現状・次手。新規は `docs/templates/` から |
| 4 | 入口・規約・索引 | `AGENTS.md` | 長い現状は ai-dev-context へ |
| 5 | 方法論（事実/推定の切り方） | `.cursor/rules/vb6-analysis.mdc` · `docs/methodology.md` | 手順の正は層2 |

キット自体の保守メモは `docs/kit-dev-context.md`（層3ではない）。

## 調査レーン（標準）

1. 環境・キット自己点検（`/kit-smoke` = `python -m tools smoke`）
2. 設定検証（`python -m tools config-check`）
3. 正本配置（`source/`）
4. VBP 抽出
5. inventory + verify
6. Startup / 主要 Form の deep-read（GoTo 飛び越え候補・ラベル地図を含む）。`.bas`/`.cls` は表面レポート
7. runtime layout（`/runtime-layout`）— デザイナ座標だけで確定しない
8. comprehension ticks（層 A→E。枠は `python -m tools comprehend --add-tick`。未 tick は `--unticked` / `--suggest`）
9. 名前集合の照合（`python -m tools verify-names`）
10. show_style 照合（`python -m tools verify-show`。inventory=全文 / deep-read=ライブ Sub。どちらが正かは決めない）
11. 再実装向け抜粋（`python -m tools excerpt` · serve `/excerpt`）
12. 横断 I/O カタログ（`python -m tools io-catalog`。業務意味なし）
13. パイプライン進捗（`python -m tools status`。成果物の有無・件数のみ）
14. ギャップ再監査（完了不信）· 製品面は `docs/reimplementation-handoff.md`

各アプリの進捗チェックリストは消費者の `docs/ai-dev-context.md` に書く（本ファイルへ長く複製しない）。

## 不変条件

- 保護ディレクトリ（`archaeology.config.json`）は読取専用
- 抽出は `working/extracts/` のみ
- UTF-8 読取コピーは `working/readable/`（任意。分析の正は extracts）
- 解析成果は `working/reports/` / `docs/`
- 使い捨て解析の増殖禁止（`tools/` 改定 + `cli.py` の `COMMANDS` 更新）
- 推定に証拠必須。inventory に無い名前はレポートに書かない

## 入口

- AI: `AGENTS.md` → `docs/ai-onboarding.md`
- ツール: `tools/README.md`
- 採用: `docs/adopting-in-a-project.md`
