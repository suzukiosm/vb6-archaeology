---
name: vb6-inventory
description: >-
  Generates the canonical VBP→file→procedure inventory report for an extracted
  VB6 project, then mechanically verifies it. Use when the user asks for a
  project structure report, a list of subs/functions per file, or when other
  reports need a facts baseline.
---

# vb6-inventory

抽出済み VB6 プロジェクトから「VBP → ファイル → プロシージャ」の**確定事実のみ**のレポートを生成する。
役割ラベル・呼び出し関係など推定情報は一切含めない（それらは vb6-comprehension の領分）。
ただし Form の `MDIChild` / `Foo.Show [arg]` は**文面の事実**として `show_style` / `show_calls` に載せ、
再実装の見せ方候補（断定しない）の入口にする。

## 前提

- 対象は `working/extracts/<stem>/` に抽出済み（未抽出なら先に vb6-vbp-extract）。
- 保護ディレクトリには触れない。

## 手順

1. 実行:

   ```powershell
   python -m tools inventory working\extracts\<stem>
   python -m tools verify working\reports\<stem>_inventory.json
   ```

2. レポート上の次を確認する:
   - `missing_in_extract` / `not_in_vbp`
   - `warnings`（パス欠落の `Form=` / `Module=` / `Class=`）
   - Form の `show_style` / outbound Show（目次列・専用節）
   - 任意で `--skip-parent-common` を使った場合は `skipped_parent_common`
3. **機械検証必須**: `count mismatches: none` まで。
4. HTML はローカル HTTP（`/serve-reports`）。短い抜粋は `python -m tools excerpt` または `/excerpt`。

オプション詳細は `tools/README.md`（inventory 節）。VBP キーは `docs/reference/vbp-keys.md`。
Show 規約: `docs/reimplementation-handoff.md`。

## 位置づけ

このインベントリが構成把握の**正（canon）**。他レポートがファイル名・Sub 名に言及するときは、インベントリに存在する名前だけを使う。
