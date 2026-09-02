---
name: serve-reports
description: Serve working/reports over loopback HTTP so report HTML renders correctly (file:// does not work).
---

# serve-reports

レポート HTML をローカル HTTP で閲覧する。`file://` は使わない。

```powershell
python -m tools serve
```

- ポートは `archaeology.config.json` の `reports_http_port`（既定 8765）。占有なら空きポートへフォールバックし、**印刷された URL が正**
- 事前確認だけしたいときは `python -m tools serve --check`（起動せず予定 URL を表示。実バインドはしない）
- `/` と `/excerpt` の live GET: `python -m tools serve --live-get`（一時ポート。200 以外は非ゼロ。長寿命サーバではない）
- 開く URL: 印刷された `http://127.0.0.1:<port>/`（ランディング: inventory · comprehension · excerpt · layout · io-catalog · deep-read + ディレクトリ一覧）
- 個別ファイル: `http://127.0.0.1:<port>/<file>.html`
- **再実装向け抜粋**: `http://127.0.0.1:<port>/excerpt`（Form · Module/Class · Show · 未 tick）。静的生成は `python -m tools excerpt`
- 5 分入口: `python -m tools demo`（extract → inventory → excerpt → このサーバ。tick しない）
