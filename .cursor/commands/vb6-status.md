---
name: vb6-status
description: Print facts-only pipeline status from existing extract, inventory, verify, verify-show, deep-read, tick, excerpt, layout, and io-catalog artifacts.
---

# vb6-status

調査パイプラインの **既存成果物** の有無と件数だけを出す。再実行しない。次に何をすべきかは書かない。

```powershell
python -m tools status
python -m tools status --extract working\extracts\<stem>
python -m tools status --json-only
```

見るもの:

- extract の有無（複数なら `default_extract`。無指定かつ複数なら `multiple`）
- inventory のファイル数 / プロシージャ数
- `verify` の永続結果（`<stem>_verify.json`。無ければ `not persisted`）
- `verify-show` の永続結果（`<stem>_verify_show.json`。警告は `show=warnings=N`）
- deep-read 数 / Form 数
- tick 数 / プロシージャ数
- excerpt / layout / io-catalog の有無

推定・優先順位は付けない。
