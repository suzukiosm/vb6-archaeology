---
name: frm-deep-read
description: Deep-read a VB6 .frm into a report plus a live-control skeleton, separating live controls from dead and hidden ones.
---

# frm-deep-read

`.frm` を深読みし、skeleton / レポートを（再）生成する。

手順は skill `vb6-frm-deep-read` を読むこと。

- 引数: `.frm` 名と `--extract`（例: `Form1.frm` + `working/extracts/mini_vbp`）
- 出力キーは **VB_Name 小文字**（`deep_read_name_map` で上書き可）。ファイル stem ではない
- 実行例:
  ```powershell
  python -m tools deep-read Form1.frm --extract working\extracts\<stem>
  python -m tools deep-read-all --extract working\extracts\<stem>
  ```
- 実行時座標は別ステップ（`/runtime-layout`）。ここでは扱わない
- ツール改定後は影響 Form を再生成する
