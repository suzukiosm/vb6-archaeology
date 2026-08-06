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

1. 骨格が無ければ作る: `python -m tools comprehend`
2. 最弱の層・未読の主要プロシージャを 1 つ選ぶ（Startup / 保存 / 印刷 / 検索優先）。
3. 枠を追記する:

   ```powershell
   python -m tools comprehend --add-tick <Proc>[@<File>] --layer <A-E>
   ```

   inventory に無い名前は**ツールが拒否する**。拒否されたら名前を疑い、手書きで押し通さない。
   同名が複数ファイルにあるときは `@<File>` で特定する。
4. CP932 で本文を読み、追記された枠の「事実」「読解（推定）」「入出力」を埋める。
   任意で `product_ui_notes`（製品面で隠す／言い換えるもの · Show）も埋める。
   Sub に GoTo があるときは deep-read の飛び越え候補・ラベル地図を先に見る
   （テンプレ: `docs/templates/comprehension-tick.md`）。
5. チェックリストの `data-status` を動かすなら、根拠を同じ tick に書く。
6. 書いたら名前集合を照合する: `python -m tools verify-names`
7. 手渡し・CURRENT 更新前の短い一覧: `python -m tools excerpt` または serve `/excerpt`

製品面チェック: `docs/reimplementation-handoff.md`。

## スコアの規律

- チェックリスト達成率のみ。100% ≠ アプリ完全理解。
- 調査 Stop と製品 UI Stop は別（`docs/templates/CURRENT.md`）。
- 達成率はレポート内の `data-status` から自動計算される。数字を手で書き換えない。
