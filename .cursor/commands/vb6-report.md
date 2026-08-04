---
name: vb6-report
description: Write or correct an investigation report with facts and inferences separated, every inference backed by primary evidence.
---

# vb6-report

正確な調査報告書の作成・修正を行う。

手順は skill `vb6-accurate-reports` を読み、それに従うこと。

- 事実と推定を分離。推定には証拠必須
- 正: `<stem>_inventory.*`
- 書いたら `/vb6-verify-reports` で名前集合を照合する
- 訂正時は参照元をカスケード更新
