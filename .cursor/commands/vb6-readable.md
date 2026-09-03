---
name: vb6-readable
description: Write a UTF-8 sidecar of an extract (same physical lines) for Cursor Read. Does not modify the extract.
---

# vb6-readable

抽出コピー（CP932）は触らず、同じ物理行の UTF-8 ツリーを `working/readable/<stem>/` に出す。

```powershell
python -m tools readable
python -m tools readable --extract working\extracts\<stem>
```

- 分析の正は `working/extracts/<stem>/`（inventory / deep-read / `lines`）
- readable は Cursor Read 専用。整形・コメント追加はしない
- `.frx` / `.ctx` 等の同伴バイナリはスキップ
- 出力レポート: `working/readable/<stem>/_readable_report.json`
