# vb6-inventory

抽出済みプロジェクトの構成レポート（VBP→ファイル→プロシージャ、事実のみ）を生成・検証する。

手順は skill `vb6-inventory` を読み、それに従うこと。

- 引数: 抽出フォルダ（例: `working\extracts\mini_vbp`）。未指定なら `working/extracts/` を列挙して確認。
- 実行:
  ```powershell
  python tools/vb6_inventory.py <extract_dir>
  python tools/verify_inventory.py working\reports\<stem>_inventory.json
  ```
- 必須: `count mismatches: none`
- 出力: `working/reports/<stem>_inventory.{json,md,html}`
