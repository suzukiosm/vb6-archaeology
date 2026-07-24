---
name: vb6-frm-deep-read
description: >-
  Deep-reads a VB6 .frm with tools/frm_deep_read.py to produce live-control
  skeletons and deep-read reports. Use when analyzing form controls, dead code,
  offscreen widgets, Show maps, or regenerating skeletons after tool changes.
---

# vb6-frm-deep-read

## 手順

```powershell
python tools/frm_deep_read.py <File>.frm --extract working\extracts\<stem>
python tools/runtime_layout.py --extract working\extracts\<stem>
```

## 出力

- `working/reports/<stem>_deep_read.md`（または指定名）
- `working/skeletons/<stem>-skeleton.json`

## 注意

- `--extract` は必須
- ツール改定後は影響 Form を再生成
- 設計時座標（Begin）と実行時座標（runtime_layout）は別物
- 保護ディレクトリには書かない
