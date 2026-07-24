---
name: vb6-comprehension
description: >-
  Layered, evidence-based comprehension workflow for an extracted VB6 project:
  builds understanding tick by tick on top of the facts inventory, with
  explicit checklists and scores. Use when the user asks to understand,
  analyze, or explain a VB6 app's behavior, data flow, or business logic.
---

# vb6-comprehension

VB6 アプリの「理解」を、証拠つき・段階的に積み上げるワークフロー。
成果は `working/reports/<stem>_comprehension.html`（および必要な補助レポート）。

## 不変条件

- 事実の土台は必ず `<stem>_inventory.*`。無ければ先に生成。
- 記述には証拠必須。書けない内容は書かない。
- 呼び出し関係・役割は「実際に読んだ Sub」の分だけ。正規表現一括推定はしない。
- ソースは CP932 で Python から読む。保護ディレクトリは読取専用。

## 層モデル

| 層 | 内容 | 典型成果物 |
|---|---|---|
| A 静的構造 | ファイル・プロシージャ・イベント | inventory、イベントカタログ |
| B データ契約 | MDB / DAT / 独自ファイル | schema / field map |
| C UI/操作 | モード変数、遷移、メニュー | modes レポート |
| D 実行依存 | EXE/COM/ネットワークパス | runtime deps |
| E システム境界 | 関連 VBP との責務 | boundary レポート |

## tick の進め方

1. 最弱の層・未読の主要 Sub を 1 つ選ぶ（Startup / 保存 / 印刷 / 検索優先）。
2. CP932 で読み、経路・入出力・分岐を証拠つきでまとめる。
3. comprehension に「tick N — 対象」を追記（テンプレ: `docs/templates/comprehension-tick.md`）。
4. スコアを動かすなら根拠を同セクションに書く。

## スコアの規律

- チェックリスト達成率のみ。100% ≠ アプリ完全理解。
