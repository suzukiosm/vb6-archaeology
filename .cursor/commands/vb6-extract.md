# vb6-extract

指定された `.vbp` を `working/extracts/<stem>/` へ切り出す。

手順は skill `vb6-vbp-extract`（`.cursor/skills/vb6-vbp-extract/SKILL.md`）を読み、それに従うこと。

- 引数: 対象 `.vbp` のパス。未指定ならユーザーに確認する。
- 実行: `python tools/extract_vbp.py "<vbp path>"`
- 完了条件: `_extract_report.json` の `missing` が空であること。
- 保護ディレクトリには一切書き込まない。
