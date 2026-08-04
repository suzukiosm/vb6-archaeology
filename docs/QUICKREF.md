# QUICKREF — エージェント早見

| 状況 | 最初に読む / 実行 |
|---|---|
| セッション開始 | `AGENTS.md` → `docs/ai-onboarding.md` |
| コマンドを忘れた | `python -m tools --help` |
| 新しい .vbp | `/vb6-extract` → `/vb6-inventory` |
| Form を知る | `/frm-deep-read` |
| 座標が合わない | `/runtime-layout`（デザイナ値だけで決めない） |
| 挙動を理解 | `/vb6-comprehend`（1 tick） |
| 報告書 | `/vb6-report` → `/vb6-verify-reports` |
| HTML を見る | `/serve-reports`（`file://` は不可） |
| 設定を変えた | `python -m tools config-check` |
| キット壊れてない？ | `/kit-smoke` |
| 他リポへ持ち出す | `docs/adopting-in-a-project.md`（**LICENSE 許諾後**） |
| キット自体の保守 | `docs/kit-dev-context.md` |

## 絶対ルール（短縮）

1. 正本に書かない（例外: `python -m tools fixture`）  
2. 事実と推定を混ぜない  
3. inventory が構成の正。無い名前は書かない  
4. 足りなければ `tools/` を直す  
5. 証拠のない「完了」を言わない  
