# vb6-verify-reports

`working/reports/` の既存レポートが `<stem>_inventory.json` の名前集合と矛盾していないか照合する。

1. End 文カウント（件数）:
   ```powershell
   python tools/verify_inventory.py working\reports\<stem>_inventory.json
   ```
2. 名前集合（ファイル名・プロシージャ名）:
   ```powershell
   python tools/verify_report_names.py --inventory working\reports\<stem>_inventory.json
   ```
   省略時は reports 下一意の `*_inventory.json` と `working/reports/**/*.{md,html,json}`（inventory 自身は除外）。
3. 矛盾があれば inventory 再生成 → レポート修正 → 参照元同期
4. 一時 `working/_verify_*.py` は作らない。足りなければ `tools/verify_report_names.py` を改定する
