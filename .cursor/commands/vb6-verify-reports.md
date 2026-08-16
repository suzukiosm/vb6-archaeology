---
name: vb6-verify-reports
description: Cross-check existing reports against the inventory (End counts, name sets, and show_style) and fix mismatches at the source.
---

# vb6-verify-reports

`working/reports/` の既存レポートが `<stem>_inventory.json` の名前集合と矛盾していないか照合する。

1. End 文カウント（件数）:
   ```powershell
   python -m tools verify working\reports\<stem>_inventory.json
   ```
2. 名前集合（ファイル名・プロシージャ名）:
   ```powershell
   python -m tools verify-names --inventory working\reports\<stem>_inventory.json
   ```
   省略時は reports 下一意の `*_inventory.json` と `working/reports/**/*.{md,html,json}`（inventory 自身は除外）。
3. show_style（inventory 全文 vs deep-read ライブ Sub。どちらが正かは決めない）:
   ```powershell
   python -m tools verify-show --inventory working\reports\<stem>_inventory.json
   ```
   同じ行の食い違い / deep-read だけの Show は exit 1。inventory だけの Show（デッド Sub 等）と skeleton 欠は警告・exit 0。結果は `<stem>_verify_show.json`。
4. 矛盾があれば inventory 再生成 → レポート修正 → 参照元同期
5. 一時 `working/_verify_*.py` は作らない。足りなければ `tools/verify_report_names.py` / `tools/verify_show.py` を改定する
