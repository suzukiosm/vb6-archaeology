# frm-deep-read

`.frm` を `tools/frm_deep_read.py` で深読みし、skeleton / レポートを（再）生成する。

手順は skill `vb6-frm-deep-read` を読むこと。

- 引数: `.frm` 名と `--extract`（例: `Form1.frm` + `working/extracts/mini_vbp`）
- 実行例:
  ```powershell
  python tools/frm_deep_read.py Form1.frm --extract working\extracts\<stem>
  python tools/runtime_layout.py --extract working\extracts\<stem>
  ```
- ツール改定後は影響 Form を再生成する
