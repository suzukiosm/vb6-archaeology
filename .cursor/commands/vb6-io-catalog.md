---
name: vb6-io-catalog
description: Catalog Open / Kill / Name / Get / Put statements across an extract (facts only) and attach existing GoTo-skip findings.
---

# vb6-io-catalog

extract 内のファイル I/O 文を **file:line** で列挙する。業務意味は書かない。

```powershell
python -m tools io-catalog
python -m tools io-catalog --extract working\extracts\<stem>
```

見るもの:

- `Open ... As #` / `Kill` / `Name … As`（リネーム。`Name =` は除外）/ `Get #` / `Put #`
- 任意の引用パス断片
- 既存 skeleton の `goto_skipped_stmts` との file+line 突合（無ければ `goto_skip` は空）

出力: `working/reports/<stem>_io_catalog.{json,md}`

`.bas` / `.cls` に skeleton が無い行は飛び越えフラグを付けない。呼び出し関係は推定しない。
