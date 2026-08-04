---
name: runtime-layout
description: Catalog runtime Left/Top/Width/Height/Visible assignments so form geometry comes from code paths, not from the designer block alone.
---

# runtime-layout

コード中の実行時ジオメトリ代入（Left / Top / Width / Height / Visible）を棚卸しし、開経路つきで出力する。

手順は skill `vb6-runtime-layout` を読み、それに従うこと。

- 実行: `python -m tools layout --extract working\extracts\<stem>`
- 出力: `working/reports/runtime_layout.md` · `<skeletons_dir>/runtime-layout.json`
- deep-read（`.frm` 単体のデザイナ値）とは別レイヤ。**両方見るまで座標を確定しない**
- 開経路スコアは `layout_sub_scores`。アプリ固有の開経路 Sub は消費者 config にだけ書く
