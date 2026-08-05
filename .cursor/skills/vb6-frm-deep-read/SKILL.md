---
name: vb6-frm-deep-read
description: >-
  Deep-reads a VB6 .frm to produce live-control skeletons and deep-read
  reports. Use when analyzing form controls, dead code, offscreen widgets, Show
  maps, or regenerating skeletons after tool changes.
---

# vb6-frm-deep-read

## 手順

```powershell
python -m tools deep-read <File>.frm --extract working\extracts\<stem>
python -m tools deep-read-all --extract working\extracts\<stem>
```

実行時座標は別レイヤ。`vb6-runtime-layout` skill（`/runtime-layout`）で扱う。

## 出力

出力キー `out_key` = `deep_read_name_map[VB_Name]` または **VB_Name の小文字**（ファイル stem ではない）。

- `working/reports/<out_key>_deep_read.md`
- `working/skeletons/<out_key>-skeleton.json`

例: `BackupDay.frm` で `Attribute VB_Name = "Form12"` → `form12_deep_read.md` / `form12-skeleton.json`。

## 注意

- `--extract` 未指定時は `working/extracts/` 下一意なら自動解決
- ツール改定後は影響 Form を再生成
- 設計時座標（Begin）と実行時座標（`/runtime-layout`）は別物
- イベント 0 件を孤立と即断しない（`.frm` 単体解析。外部からの参照は見えない）
- Open 列挙をソース順＝実行順と読まない（「GoTo で飛び越えられる Open（候補）」節）
- 保護ディレクトリには書かない
