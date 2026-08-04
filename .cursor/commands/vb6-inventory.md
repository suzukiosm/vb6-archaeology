---
name: vb6-inventory
description: Generate and verify the canonical VBP to file to procedure inventory (facts only) for an extracted VB6 project.
---

# vb6-inventory

抽出済みプロジェクトの構成レポート（VBP→ファイル→プロシージャ、事実のみ）を生成・検証する。

手順は skill `vb6-inventory` を読み、それに従うこと。

- 引数: 抽出フォルダ（例: `working\extracts\mini_vbp`）。未指定なら `working/extracts/` を列挙して確認。
- 実行:
  ```powershell
  python -m tools inventory <extract_dir>
  python -m tools verify working\reports\<stem>_inventory.json
  ```
- 必須: `count mismatches: none`
- 出力: `working/reports/<stem>_inventory.{json,md,html}`
