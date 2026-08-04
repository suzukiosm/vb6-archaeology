---
name: vb6-accurate-reports
description: >-
  Creates and corrects accurate VB6 investigation reports with fact/inference
  separation, primary evidence, canon cross-checks, and cascading fixes. Use
  when writing, updating, fixing, or auditing reports under working/reports/.
---

# vb6-accurate-reports

正確な調査報告書の **作成** と **修正** を同一の規律で行う。

## 不変条件

1. 事実と推定を分離。推定は証拠必須
2. 構成の正は `<stem>_inventory.*`
3. ソースは CP932。保護ディレクトリは読取専用
4. 検証なき公開禁止

## 新規作成

| 種類 | 書くこと | 書かないこと |
|---|---|---|
| 事実レポート | 一覧・行範囲・パス・件数 | 役割ラベル、推測グラフ |
| 証拠つき読解 | 精読した Sub の分岐・I/O | 未読 Sub の役割 |
| ギャップ／訂正 | 欠落と一次証拠 | 「たぶん埋まっている」 |

テンプレ骨子は `docs/methodology.md` と `docs/templates/comprehension-tick.md`。

## 修正（カスケード）

1. 一次ソースで再確認
2. 対象レポートを直す
3. 参照元（他レポート・AGENTS・flow・消費者 ai-dev-context / キット kit-dev-context）を同時更新
4. 名前集合を再照合:
   ```powershell
   python -m tools verify-names --inventory working\reports\<stem>_inventory.json
   ```
   （End 数は別途 `python -m tools verify`。一時 `working/_verify_*.py` は作らない）
