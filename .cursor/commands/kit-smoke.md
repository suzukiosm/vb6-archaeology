# kit-smoke

キット自身の健全性をフィクスチャで確認する。

```powershell
python tools/make_fixture.py
python tools/extract_vbp.py "source\mini_vbp\mini_vbp.vbp"
python tools/vb6_inventory.py working\extracts\mini_vbp
python tools/verify_inventory.py working\reports\mini_vbp_inventory.json
python tools/frm_deep_read.py Form1.frm --extract working\extracts\mini_vbp
python tools/runtime_layout.py --extract working\extracts\mini_vbp
```

成功条件:

- extract `missing` が空
- `count mismatches: none`
- deep-read / runtime_layout が例外なく終了
- `working/reports/` と `working/skeletons/` に成果が出る

結果を短く報告する。失敗したらどのステップかを明示し、`tools/` を直して再実行する。
