# vb6-verify-reports

`working/reports/` の既存レポートが `<stem>_inventory.json` の名前集合と矛盾していないか照合する。

1. inventory から (ファイル名, プロシージャ名) 集合を作る
2. 対象レポートが言及する名前を抽出し、集合外を列挙
3. 定型の件数検証は `python tools/verify_inventory.py`
4. 一時スクリプトが必要なら `working/_verify_*.py` に置き、確認後削除
5. 矛盾があれば inventory 再生成 → レポート修正 → 参照元同期
