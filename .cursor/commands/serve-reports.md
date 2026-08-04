---
name: serve-reports
description: Serve working/reports over loopback HTTP so report HTML renders correctly (file:// does not work).
---

# serve-reports

レポート HTML をローカル HTTP で閲覧する。`file://` は使わない。

```powershell
python -m tools serve
```

- ポートは `archaeology.config.json` の `reports_http_port`（既定 8765）。衝突したら `--port` で変える
- 事前確認だけしたいときは `python -m tools serve --check`（起動せず URL と対象ディレクトリを表示）
- 開く URL: `http://127.0.0.1:<port>/<file>.html`
