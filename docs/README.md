# docs — 索引

エージェントはまずリポ直下の [`AGENTS.md`](../AGENTS.md) → [`ai-onboarding.md`](ai-onboarding.md) を Read。  
ツール入口は `python -m tools --help`。

## 必読・入口

| 文書 | 用途 |
|---|---|
| [ai-onboarding.md](ai-onboarding.md) | AI 必読（起動・契約・アンチパターン） |
| [QUICKREF.md](QUICKREF.md) | 短い早見 |
| [flow/_master.md](flow/_master.md) | フェーズ・不変条件の正 |
| [workflow.md](workflow.md) | 標準パイプライン詳細 |

## 方法論・採用

| 文書 | 用途 |
|---|---|
| [methodology.md](methodology.md) | 事実 vs 推定・証拠ルール |
| [adopting-in-a-project.md](adopting-in-a-project.md) | 他リポへの採用手順 |
| [reimplementation-handoff.md](reimplementation-handoff.md) | 調査完了→製品 UI のチェックリスト · Show パターン |
| [directory-layout.md](directory-layout.md) | ディレクトリ契約 |
| [encoding-cp932.md](encoding-cp932.md) | CP932 前提 |

## テンプレ

| パス | 用途 |
|---|---|
| [templates/](templates/) | 消費者雛形（ai-dev-context · CURRENT · frm-audit · comprehension-tick · data-guards · project-local） |

## リファレンス

| 文書 | 用途 |
|---|---|
| [reference/glossary.md](reference/glossary.md) | 用語 |
| [reference/anti-patterns.md](reference/anti-patterns.md) | やってはいけないこと |
| [reference/vbp-keys.md](reference/vbp-keys.md) | VBP キー |
| [../schema/archaeology.config.schema.json](../schema/archaeology.config.schema.json) | 設定の正（`python -m tools config-check`） |

## キット保守

| 文書 | 用途 |
|---|---|
| [kit-dev-context.md](kit-dev-context.md) | キット自体の現状・公開方針（消費者 ai-dev-context ではない） |

ツール索引: [`../tools/README.md`](../tools/README.md) · 貢献: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
