---
name: kit-smoke
description: Run the kit self-check (fixture pipeline plus unit tests) and report which step failed.
---

# kit-smoke

キット自身の健全性をフィクスチャパイプラインと unittest で確認する。

```powershell
python -m tools smoke
```

成功条件:

- config-check / extract / inventory / verify（End 数・名前集合）/ deep-read / deep-read-all / layout / comprehend / scan-chars が例外なく終了
- `count mismatches: none` · `name mismatches: none`
- `python -m unittest discover -s tools -p "test_*.py"` 相当がすべて成功
- `working/reports/` と `working/skeletons/` に成果が出る

結果を短く報告する。失敗したらどのステップかを明示し、`tools/` を直して再実行する。
