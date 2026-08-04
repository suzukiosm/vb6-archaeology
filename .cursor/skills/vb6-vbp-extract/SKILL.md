---
name: vb6-vbp-extract
description: >-
  Copies a VB6 .vbp and the source files it references into working/extracts/
  without modifying protected source trees. Use when extracting a VB6 project,
  bundling VBP dependencies, or isolating a .vbp for analysis.
---

# vb6-vbp-extract

## 不変条件

- **保護ディレクトリには一切書かない**（`archaeology.config.json` の `protected_source_dirs`）。
- 出力先は常に `working/extracts/<vbp-stem>/`（設定で変更可）。
- 文字コードは **CP932**（フォールバックあり）。

## 手順

1. 対象 `.vbp` のパスを確定（例: `source/mini_vbp/mini_vbp.vbp`）。
2. ツールを実行:

   ```powershell
   python -m tools extract "source\<Name>\<Name>.vbp"
   python -m tools extract "source\<Name>\<Name>.vbp" --out "working\extracts\<Name>"
   ```

3. 終了コードとレポートを確認:
   - `copied` — コピー成功
   - `missing` — VBP が指すが正本に無い
   - `skipped_ref_count` — COM `Reference=`（対象外・正常）
4. 抽出結果の編集は `working/extracts/` 内のみ。正本へ戻さない。

## VBP から拾うキー

`docs/reference/vbp-keys.md` を参照。

## やってはいけないこと

- 正本内での整理・リネーム・削除
- 抽出先 VBP のパス書き換えを無断で本番扱いする
