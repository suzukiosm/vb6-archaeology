# source/ — protected VB6 originals

Put immutable `.vbp` trees here. Hooks deny writes into this directory
(and other names listed in `archaeology.config.json` → `protected_source_dirs`).

## Fixture

`mini_vbp/` is for kit smoke tests only (CP932, includes Japanese captions).

Regenerate with:

```powershell
python tools/make_fixture.py
```

Do not hand-edit the fixture; regenerate from the tool.
