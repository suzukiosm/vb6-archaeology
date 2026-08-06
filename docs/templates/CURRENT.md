# CURRENT — セッション手渡し正本（上書き）

消費者リポで `working/CURRENT.md` にコピーし、**常に上書き更新**する。  
長い経緯は `docs/ai-dev-context.md` へ。本ファイルは「今この瞬間の正」だけ。

キットは本ファイルを生成・更新しない。エージェントがフェーズ境界で手で直す。

---

## Phase

〈調査 | 理解 tick | 再実装配線 | 製品 UI 仕上げ | 停止〉

## Stop（どちらの Stop か明示）

| 種別 | 状態 | 条件（キット / 消費者） |
|---|---|---|
| 調査 Stop | 〈未 / 達〉 | 合意チェックリスト · ユーザー「止め」 · 証拠不足（[`workflow.md`](../workflow.md)） |
| 製品 UI Stop | 〈未 / 達〉 | [`reimplementation-handoff.md`](../reimplementation-handoff.md) のチェックリスト |

混同しない。調査 Stop 済みでも製品 UI Stop は別判定。

## Focus（今の 1 本）

- 対象: 〈Form / Sub / ファイル〉
- 次の dual: 〈コマンド or 精読対象〉
- ブロック: 〈無し / 正本不足 / 要ユーザー確認〉

## Evidence pointers（パスのみ）

- extract: `working/extracts/〈stem〉/`
- inventory: `working/reports/〈stem〉_inventory.*`
- comprehension: `working/reports/〈stem〉_comprehension.html`
- layout: `working/reports/runtime_layout.*`
- 直近 tick: 〈Tick N — Proc〉

## Show / 製品メモ（任意・短く）

- 着手 Form の `show_style`: 〈mdi_child | modal_overlay | navigate | 未確認〉
- `product_ui_notes` で隠す／言い換えるもの: 〈…〉

## Compact 手順（フェーズ境界）

1. 本ファイルの Phase / Stop / Focus だけ書き換える（履歴を追記しない）
2. 残したい事実は `docs/ai-dev-context.md` の該当節へ移す
3. チャットを新規にする場合は、次エージェントに「`working/CURRENT.md` を Read」とだけ渡す
4. 任意: `python -m tools loop show`（消費者に loop がある場合）で入口を再確認

詳細コンテキスト: `docs/ai-dev-context.md` · 採用: [`../adopting-in-a-project.md`](../adopting-in-a-project.md)
