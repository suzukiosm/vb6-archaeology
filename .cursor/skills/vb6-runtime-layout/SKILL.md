---
name: vb6-runtime-layout
description: >-
  Catalogs runtime Left/Top/Width/Height/Visible assignments in VB6 code with
  runtime_layout.py, so geometry comes from executed code paths rather than the
  designer block. Use when asked where a form or control actually appears, why a
  control moves at runtime, or before reimplementing a screen.
---

# vb6-runtime-layout

デザイナ（`Begin` ブロック）の座標は初期値にすぎない。実行時に上書きする代入を拾って、
**どの経路で開いたときにどこへ出るか**を確定する。

## 前提

- 対象は `working/extracts/<stem>/` に抽出済み
- deep-read 済みだと突き合わせが早い（必須ではない）

## 手順

```powershell
python -m tools layout --extract working\extracts\<stem>
```

出力:

- `working/reports/runtime_layout.md` — 代入一覧・開経路・コード側の移動
- `<skeletons_dir>/runtime-layout.json` — 再実装へ渡す中間成果（既定 `working/skeletons/`）

## 読み方

| 出力 | 意味 |
|---|---|
| `formPlacements` | Show 文脈から解決した「その経路での配置」 |
| `codeControlMoves` | コードがコントロールを動かす／出し入れする箇所 |
| `layout_sub_scores` | 開経路 Sub の優先度（採用値はレポートに出力される） |

## 注意

- `--extract` 未指定時は `working/extracts/` 下が一意ならそれを使う
- Show 文脈は Sub 境界でリセットされる。別 Sub の Show を根拠にしない
- 開経路スコアの既定は `form_load` / `mdiform_load` のみ。**アプリ固有の開経路 Sub は消費者 config にだけ書く**（キットへ還元しない）
- MDI chrome（シェル名・Picture1/FG 等）は `mdi_chrome`。**キット既定は空**。消費者 config に書く
- 座標式が親フォーム相対のときは `geometry_hints` を与えると数値化できる
- 設計時座標と実行時座標が食い違うときは、両方をレポートに残す（片方を消さない）
