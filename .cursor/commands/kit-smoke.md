# kit-smoke

キット自身の健全性をフィクスチャパイプラインと unittest で確認する。

```powershell
python tools/kit_smoke.py
```

成功条件:

- extract / inventory / verify（End 数・名前集合）/ deep-read / runtime_layout が例外なく終了
- `count mismatches: none` · `name mismatches: none`
- `python -m unittest discover -s tools -p "test_*.py"` 相当がすべて成功
- `working/reports/` と `working/skeletons/` に成果が出る

結果を短く報告する。失敗したらどのステップかを明示し、`tools/` を直して再実行する。
