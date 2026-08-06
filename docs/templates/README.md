# docs/templates — 消費者向け雛形

キット必須ワークフローではない。採用時にコピーして埋める。

| ファイル | 用途 |
|---|---|
| [`ai-dev-context.md`](ai-dev-context.md) | セッション事実（→ 消費者 `docs/ai-dev-context.md`） |
| [`CURRENT.md`](CURRENT.md) | 長セッション手渡し正本（→ 消費者 `working/CURRENT.md`・上書き） |
| [`AGENTS.consumer.md`](AGENTS.consumer.md) | 消費者向け入口の短縮例 |
| [`project-local.mdc`](project-local.mdc) | → `.cursor/rules/project-local.mdc` |
| [`comprehension-tick.md`](comprehension-tick.md) | 理解 tick 1 件分の考え方（枠の生成は `python -m tools comprehend --add-tick`） |
| [`frm-audit.md`](frm-audit.md) | .frm 再監査 MD の骨子（再実装レーン任意） |
| [`frm-audit-skill.md`](frm-audit-skill.md) | 上記を skill 化するときの雛形（消費者 `.cursor/skills/` へコピー） |
| [`consumer-data-guards.example.md`](consumer-data-guards.example.md) | 本番データ書込抑止 hooks の例（プレースホルダ） |

採用手順: [`../adopting-in-a-project.md`](../adopting-in-a-project.md)  
製品面ハンドオフ: [`../reimplementation-handoff.md`](../reimplementation-handoff.md)
