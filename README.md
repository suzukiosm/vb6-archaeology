# vb6-archaeology

**VB6 を壊さず理解するオペレーティングシステム** — 読取専用正本のまま、抽出・棚卸し・深読み・証拠つき理解までを再現可能にするキット。

## 誰向けか

- レガシー VB6（`.vbp` / `.frm` / `.bas` / `.cls`）を調査する人・AI エージェント
- 将来の再実装（Next.js 等）の前に「事実の土台」を固めたいチーム

## 5 分で動かす

```powershell
cd <this-repo>
python tools/make_fixture.py
python tools/extract_vbp.py "source\mini_vbp\mini_vbp.vbp"
python tools/vb6_inventory.py working\extracts\mini_vbp
python tools/verify_inventory.py working\reports\mini_vbp_inventory.json
python tools/frm_deep_read.py Form1.frm --extract working\extracts\mini_vbp
python tools/runtime_layout.py --extract working\extracts\mini_vbp
```

レポート閲覧:

```powershell
Set-Location working\reports
python -m http.server 8765 --bind 127.0.0.1
# http://127.0.0.1:8765/mini_vbp_inventory.html
```

## AI エージェントへ

1. この README の次に **`AGENTS.md`** を Read
2. 続けて **`docs/ai-onboarding.md`** を Read（必須）
3. 作業は commands（`/vb6-extract` 等）または対応 skill から入る
4. 正本 `source/`（および設定された保護ディレクトリ）には書かない

## レイアウト

```
source/                 # 読取専用 VB6 正本（hooks 保護）
working/extracts/       # 切り出しコピー
working/reports/        # 調査成果
working/skeletons/      # Form skeleton JSON
tools/                  # 再利用 CLI
docs/                   # 方法論・採用ガイド・テンプレ
.cursor/                # rules / skills / commands / hooks
archaeology.config.json # 保護ディレクトリ・出力先
```

## 他リポへの採用

**事前許諾が必要**（[LICENSE](LICENSE)）。許諾後の手順は `docs/adopting-in-a-project.md`。  
最小セット: `tools/` + `.cursor/` + `archaeology.config.json` + `AGENTS.md` 雛形。

## License

Copyright (c) 2026 [有限会社アイコー](https://www.aiko1123.com/). See [LICENSE](LICENSE).

source-available（OSS ではない）。閲覧・学習は歓迎。利用・複製・改変・組込は許諾が必要です。  
コア手順は VB6 資産調査の実務から抽出。アプリ固有ロジックは含みません。
