# docs — 索引

**[English public docs](en/README.md)** · **日本語（本ページ）**

エージェントはまずリポ直下の [`AGENTS.md`](../AGENTS.md) → [`ai-onboarding.md`](ai-onboarding.md) を Read。  
人間向けランディング: [`README.md`](../README.md)（English）· [`README.ja.md`](../README.ja.md)（日本語）。  
ツール入口は `python -m tools --help`。

## 必読・入口

| 文書 | 用途 |
|---|---|
| [ai-onboarding.md](ai-onboarding.md) | AI 必読（起動・契約・アンチパターン） |
| [QUICKREF.md](QUICKREF.md) | 短い早見 |
| [flow/_master.md](flow/_master.md) | フェーズ・不変条件の正 |
| [workflow.md](workflow.md) | 標準パイプライン詳細 |

## 公開向け（VB6 ≠ VBA · 文字化け）

| 文書 | 用途 |
|---|---|
| [vb6-not-vba.md](vb6-not-vba.md) | VB6 / VBA / VB.NET / VBScript の対比（[English](en/vb6-not-vba.md)） |
| [encoding-cp932.md](encoding-cp932.md) | CP932 前提（[English](en/encoding-cp932.md)） |
| [en/adopting-in-a-project.md](en/adopting-in-a-project.md) | 採用手順の英語要約 |

## 方法論・採用

| 文書 | 用途 |
|---|---|
| [methodology.md](methodology.md) | 事実 vs 推定・証拠ルール |
| [adopting-in-a-project.md](adopting-in-a-project.md) | 他リポへの採用手順（[English](en/adopting-in-a-project.md)） |
| [reimplementation-handoff.md](reimplementation-handoff.md) | 調査完了→製品 UI のチェックリスト · Show パターン |
| [directory-layout.md](directory-layout.md) | ディレクトリ契約 |

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
| [kit-improvement-ideas.md](kit-improvement-ideas.md) | 未採用の改良提案（採用するまで実装しない） |

ツール索引: [`../tools/README.md`](../tools/README.md) · 貢献: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
