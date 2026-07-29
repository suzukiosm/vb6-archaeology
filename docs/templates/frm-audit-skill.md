---
name: vb6-frm-audit
description: >-
  Re-audit one VB6 .frm against the reimplementation with evidence.
  Updates working/reports/audit/*_frm_audit.md. Use for frm audit, 再監査,
  or gap checks. Consumer-optional — not a kit-required command.
---

# vb6-frm-audit（消費者向け雛形）

**このファイルはキットの必須 skill ではない。**  
再実装レーンを持つ消費者が、自リポの `.cursor/skills/vb6-frm-audit/SKILL.md` へ **コピーしてから** パス・成果物名・補助ツールを埋める。

監査 MD の型の正: キットの [`frm-audit.md`](frm-audit.md)  
→ 消費者では `working/reports/audit/〈name〉_frm_audit.md` に実体を置く。

## 前提（コピー後に埋める）

- 抽出: `working/extracts/〈stem〉/`
- ソース読取は CP932（`tools/`）。Cursor Read の日本語化けを根拠にしない
- 保護ディレクトリ（config の `protected_source_dirs`）へは書込しない
- キット必須ゴールは調査。再実装配線は任意レーン

## 再監査順（固定・変更しない）

1. **VB6 読解誤り** — Caption 誤認、到達不能の現役扱い、inventory 外の名前
2. **UI 位置** — ずれは保留可。ただし開時コード座標・親クリップ・背面完全被覆・`codeControlMoves` は対象
3. **機能取りこぼし** — 実行経路のイベントが再実装に無い（意図的未移植と区別）

## 手順（薄い）

1. 対象 `.frm` / Form 名を決める
2. `frm_deep_read.py` · inventory · `runtime_layout` を突合（不足ならツール再実行）
3. 再実装側の対応面を列挙（消費者のディレクトリ構成に合わせる）
4. [`frm-audit.md`](frm-audit.md) 骨子で audit MD を更新（事実のみ。推定はラベル + 証拠）
5. 取りこぼしがあれば次候補を 1〜3 件。広範囲実装はユーザーが依頼した範囲のみ

## 完了条件

- 対象 Form の差分が `working/reports/audit/〈name〉_frm_audit.md` に記録されている
- 意図的未移植と取りこぼしが混ざっていない

## 書かないこと（キット境界）

- 特定顧客 VBP・DAT 契約・外部バッチランナー手順をこの雛形にハードコードしない
- キットの `/vb6-*` 必須コマンドへ昇格させない（消費者任意の command は自リポで追加可）
