---
name: vb6-comprehend
description: Advance comprehension of an extracted VB6 project by one evidence-backed tick, anchored to the inventory name set.
---

# vb6-comprehend

抽出済み VB6 プロジェクトの理解を 1 tick 分進める。

手順は skill `vb6-comprehension` を読み、それに従うこと。

- 前提: `<stem>_inventory.*` が存在すること
- 骨格生成（初回のみ）: `python -m tools comprehend`
- tick 追加: `python -m tools comprehend --add-tick <Proc>[@<File>] --layer <A-E>`
  - inventory に無い名前は拒否される。拒否されたら名前を疑う（レポートを手で書き足さない）
  - 追記後に本文を Read し、CP932 で読んだ事実・証拠を埋める
- 1 回の実行で 1 tick。証拠のない加点は禁止
- テンプレの考え方: `docs/templates/comprehension-tick.md`
