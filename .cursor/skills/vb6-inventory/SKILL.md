---
name: vb6-inventory
description: >-
  Generates the canonical VBP→file→procedure inventory report for an extracted
  VB6 project using tools/vb6_inventory.py, then mechanically verifies it. Use
  when the user asks for a project structure report, a list of subs/functions
  per file, or when other reports need a facts baseline.
---

# vb6-inventory

抽出済み VB6 プロジェクトから「VBP → ファイル → プロシージャ」の**確定事実のみ**のレポートを生成する。
役割ラベル・呼び出し関係など推定情報は一切含めない（それらは vb6-comprehension の領分）。

## 前提

- 対象は `working/extracts/<stem>/` に抽出済み（未抽出なら先に vb6-vbp-extract）。
- 保護ディレクトリには触れない。

## 手順

1. 実行:

   ```powershell
   python tools/vb6_inventory.py working\extracts\<stem>
   python tools/verify_inventory.py working\reports\<stem>_inventory.json
   ```

2. レポート上の次を確認する:
   - `missing_in_extract` / `not_in_vbp`
   - `warnings`（パス欠落の `Form=` / `Module=` / `Class=`）
   - 任意で `--skip-parent-common` を使った場合は `skipped_parent_common`
3. **機械検証必須**: `count mismatches: none` まで。
4. HTML はローカル HTTP（`/serve-reports`）。

オプション詳細は `tools/README.md`（inventory 節）。VBP キーは `docs/reference/vbp-keys.md`。

## 位置づけ

このインベントリが構成把握の**正（canon）**。他レポートがファイル名・Sub 名に言及するときは、インベントリに存在する名前だけを使う。
