# vb6-archaeology

[![CI](https://github.com/suzukiosm/vb6-archaeology/actions/workflows/ci.yml/badge.svg)](https://github.com/suzukiosm/vb6-archaeology/actions/workflows/ci.yml)

**VB6 を壊さず理解するオペレーティングシステム** — 読取専用正本のまま、抽出・棚卸し・深読み・証拠つき理解までを再現可能にするキット。

## 誰向けか

- レガシー VB6（`.vbp` / `.frm` / `.bas` / `.cls`）を調査する人・AI エージェント
- 将来の再実装（Next.js 等）の前に「事実の土台」を固めたいチーム

## 要件

- **Python 3.10+**（標準ライブラリのみ）

## 5 分で動かす

```powershell
cd <this-repo>
python -m tools fixture
python -m tools extract "source\mini_vbp\mini_vbp.vbp"
python -m tools inventory working\extracts\mini_vbp
python -m tools verify working\reports\mini_vbp_inventory.json
python -m tools deep-read Form1.frm --extract working\extracts\mini_vbp
python -m tools layout --extract working\extracts\mini_vbp
```

コマンド一覧は `python -m tools --help`（個々のツールは `python tools/<name>.py` でも動く）。

レポート閲覧:

```powershell
python -m tools serve
# http://127.0.0.1:8765/mini_vbp_inventory.html
```

自己点検（パイプライン + テスト）:

```powershell
python -m tools smoke
```

## AI エージェントへ

1. この README の次に **`AGENTS.md`** を Read
2. 続けて **`docs/ai-onboarding.md`** を Read（必須）
3. 作業は commands（`/vb6-extract` 等）または対応 skill から入る
4. 正本 `source/`（および設定された保護ディレクトリ）には書かない

## ドキュメント

索引: [`docs/README.md`](docs/README.md)  
採用: [`docs/adopting-in-a-project.md`](docs/adopting-in-a-project.md) · 貢献: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## レイアウト

```
source/                 # 読取専用 VB6 正本（hooks 保護）
working/extracts/       # 切り出しコピー
working/reports/        # 調査成果
working/skeletons/      # Form skeleton JSON
tools/                  # 再利用 CLI（python -m tools）
docs/                   # 方法論・採用ガイド・テンプレ
schema/                 # archaeology.config.json の JSON Schema
.cursor/                # rules / skills / commands / hooks
archaeology.config.json # 保護ディレクトリ・出力先
```

## 他リポへの採用

**事前許諾が必要**（[LICENSE](LICENSE)）。許諾後の手順は `docs/adopting-in-a-project.md`。  
最小セット: `tools/` + `.cursor/` + `schema/` + `archaeology.config.json` + `AGENTS.md` 雛形。  
グローバルな Cursor ルールには依存しない（Python 3.10+ とこのリポだけで完結）。

## License

See [LICENSE](LICENSE).
