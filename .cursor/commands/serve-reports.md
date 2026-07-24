# serve-reports

`working/reports/` の HTML レポートをローカル HTTP で閲覧する。

1. ポート 8765 が既に使われていればそれを使う
2. 無ければ:

   ```powershell
   Set-Location -LiteralPath "<repo>\working\reports"
   python -m http.server 8765 --bind 127.0.0.1
   ```

3. `http://127.0.0.1:8765/<file>.html` を開く。`file://` は使わない。
