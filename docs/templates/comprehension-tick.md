# Tick 〈N〉 — 〈対象プロシージャ〉

> HTML レポートの枠は `python -m tools comprehend --add-tick <Proc>[@<File>]` が作る。
> 本ファイルは「何を書けば tick として成立するか」の基準。

- 対象: `working/extracts/<stem>/<file>` / `〈Sub名〉` / 行 〈start〉–〈end〉
- 層: A 静的 | B データ | C UI | D 実行依存 | E 境界
- 種別: 事実の整理 | 読解（推定）

## 事実

- …
- GoTo: 〈なし / deep-read「飛び越え候補」「ラベル地図」を確認。飛び越え区間をソース順で読んでいない〉

## 読解（推定）— 証拠必須

- 主張: …
- 証拠: `ファイル` / `Sub` / 行 or 引用
- 反証・例外: …
- （GoTo があるとき）飛び越え区間の扱い: 〈実行されない候補として除外 / 条件付きで残す / 未確認〉

## 入出力

- 読む: …
- 書く: …
- 呼ぶ: …（精読で確認した分のみ）

## product_ui_notes（任意・製品面）

調査で見えたが **製品 UI では隠す／言い換える／出さない**もの。空なら節ごと省略可。

- 隠す: 〈VB Caption / MsgBox 文言 / 拠点名 / debug meta〉
- 言い換える: 〈調査用語 → オペレータ向け〉
- Show: 〈`mdi_child` | `modal_overlay` | `navigate` | 未確認〉（[`../reimplementation-handoff.md`](../reimplementation-handoff.md)）

## スコア更新（任意）

- チェックリスト項目: …
- 今回確認できたこと: …
- 未確認のまま残すこと: …
