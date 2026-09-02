# QUICKREF — エージェント早見

| 状況 | 最初に読む / 実行 |
|---|---|
| セッション開始 | `AGENTS.md` → `docs/ai-onboarding.md` |
| コマンドを忘れた | `python -m tools --help`（5 分デモは `python -m tools demo`） |
| 新しい .vbp | `/vb6-extract` → `/vb6-inventory` |
| Form / Module を知る | `/frm-deep-read`（`.frm` または `.bas`/`.cls`） |
| キットバックログ | `python -m tools ideas`（正は `docs/kit-improvement-ideas.md`） |
| 座標が合わない | `/runtime-layout`（デザイナ値だけで決めない。MDI chrome は config `mdi_chrome`） |
| 挙動を理解 | `/vb6-comprehend`（1 tick。未 tick は `--unticked` / `--suggest`） |
| 報告書 | `/vb6-report` → `/vb6-verify-reports`（End / 名前 / show_style） |
| HTML を見る | `/serve-reports`（印刷された URL。`file://` は不可。ポート占有時はフォールバック） |
| 再実装の短い抜粋 | `python -m tools excerpt` · serve `/excerpt` |
| 設定を変えた | `python -m tools config-check` |
| キット壊れてない？ | `/kit-smoke` |
| VB6 と VBA を混同しそう | `docs/vb6-not-vba.md`（English: `docs/en/vb6-not-vba.md`） |
| 他リポへ持ち出す | `docs/adopting-in-a-project.md`（**LICENSE 許諾後**） |
| 再実装の製品面 | `docs/reimplementation-handoff.md`（調査完了 ≠ UI 完了） |
| キット自体の保守 | `docs/kit-dev-context.md` |
| ファイル I/O の位置 | `python -m tools io-catalog`（Open / Kill / Name / Get / Put。業務意味は書かない） |
| パイプライン進捗 | `python -m tools status`（成果物の有無・件数。次手は出さない） |
| キット改良の未採用案 | `docs/kit-improvement-ideas.md`（採用指示があるまで実装しない） |

## 絶対ルール（短縮）

1. 正本に書かない（例外: `python -m tools fixture`）  
2. 事実と推定を混ぜない  
3. inventory が構成の正。無い名前は書かない  
4. 足りなければ `tools/` を直す  
5. 証拠のない「完了」を言わない  
